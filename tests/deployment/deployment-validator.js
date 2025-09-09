/**
 * Deployment Validation Runner
 * Orchestrates all deployment validation tests and provides comprehensive reporting
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class DeploymentValidator {
  constructor(config = {}) {
    this.config = {
      baseUrl: config.baseUrl || process.env.DEPLOY_URL || 'http://localhost:8080',
      timeout: config.timeout || 300000, // 5 minutes
      retries: config.retries || 3,
      parallel: config.parallel || true,
      environment: config.environment || process.env.NODE_ENV || 'production',
      skipTests: config.skipTests || [],
      includeTests: config.includeTests || null,
      ...config
    };
    
    this.results = {
      startTime: new Date(),
      endTime: null,
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      skippedTests: 0,
      testSuites: {},
      criticalFailures: [],
      warnings: [],
      summary: {}
    };
  }

  async validateDeployment() {
    console.log('🚀 Starting Deployment Validation...');
    console.log(`📍 Target URL: ${this.config.baseUrl}`);
    console.log(`🏗️  Environment: ${this.config.environment}`);
    console.log('─'.repeat(80));

    try {
      // Pre-validation checks
      await this.preValidationChecks();

      // Run test suites
      const testSuites = this.getTestSuites();
      
      if (this.config.parallel) {
        await this.runTestSuitesParallel(testSuites);
      } else {
        await this.runTestSuitesSequential(testSuites);
      }

      // Post-validation analysis
      await this.postValidationAnalysis();

      // Generate comprehensive report
      this.generateReport();

      return this.results;
    } catch (error) {
      console.error('❌ Deployment validation failed:', error.message);
      this.results.criticalFailures.push({
        type: 'VALIDATION_ERROR',
        message: error.message,
        timestamp: new Date()
      });
      throw error;
    } finally {
      this.results.endTime = new Date();
    }
  }

  async preValidationChecks() {
    console.log('🔍 Running pre-validation checks...');
    
    // Check target URL accessibility
    try {
      const response = await fetch(this.config.baseUrl);
      if (!response.ok) {
        throw new Error(`Target URL returned ${response.status}`);
      }
      console.log('✅ Target URL is accessible');
    } catch (error) {
      throw new Error(`Cannot reach target URL: ${error.message}`);
    }

    // Validate test environment
    if (!fs.existsSync(path.join(__dirname))) {
      throw new Error('Test directory not found');
    }

    console.log('✅ Pre-validation checks completed');
  }

  getTestSuites() {
    const allSuites = {
      'health-checks': {
        file: 'health-checks.test.js',
        priority: 1,
        critical: true,
        description: 'Health check and liveness validation'
      },
      'environment-validation': {
        file: 'environment-validation.test.js',
        priority: 2,
        critical: true,
        description: 'Environment variable and configuration validation'
      },
      'service-connectivity': {
        file: 'service-connectivity.test.js',
        priority: 3,
        critical: true,
        description: 'Service dependencies and connectivity validation'
      },
      'digital-ocean-platform': {
        file: 'digital-ocean-platform.test.js',
        priority: 4,
        critical: false,
        description: 'Digital Ocean App Platform specific validation'
      },
      'performance-validation': {
        file: 'performance-validation.test.js',
        priority: 5,
        critical: false,
        description: 'Performance and load validation'
      },
      'rollback-recovery': {
        file: 'rollback-recovery.test.js',
        priority: 6,
        critical: false,
        description: 'Rollback and recovery procedures validation'
      }
    };

    // Filter based on configuration
    let testSuites = allSuites;
    
    if (this.config.includeTests) {
      testSuites = Object.fromEntries(
        Object.entries(allSuites).filter(([key]) => 
          this.config.includeTests.includes(key)
        )
      );
    }

    if (this.config.skipTests.length > 0) {
      testSuites = Object.fromEntries(
        Object.entries(testSuites).filter(([key]) => 
          !this.config.skipTests.includes(key)
        )
      );
    }

    return testSuites;
  }

  async runTestSuitesParallel(testSuites) {
    console.log('🔄 Running test suites in parallel...');
    
    // Separate critical and non-critical tests
    const criticalSuites = Object.entries(testSuites)
      .filter(([, suite]) => suite.critical)
      .sort(([, a], [, b]) => a.priority - b.priority);
      
    const nonCriticalSuites = Object.entries(testSuites)
      .filter(([, suite]) => !suite.critical)
      .sort(([, a], [, b]) => a.priority - b.priority);

    // Run critical tests first (sequential)
    for (const [suiteName, suite] of criticalSuites) {
      await this.runTestSuite(suiteName, suite);
      
      // Stop if critical test fails
      if (this.results.testSuites[suiteName]?.status === 'failed') {
        throw new Error(`Critical test suite failed: ${suiteName}`);
      }
    }

    // Run non-critical tests in parallel
    if (nonCriticalSuites.length > 0) {
      const promises = nonCriticalSuites.map(([suiteName, suite]) =>
        this.runTestSuite(suiteName, suite)
      );
      
      await Promise.allSettled(promises);
    }
  }

  async runTestSuitesSequential(testSuites) {
    console.log('🔄 Running test suites sequentially...');
    
    const sortedSuites = Object.entries(testSuites)
      .sort(([, a], [, b]) => a.priority - b.priority);

    for (const [suiteName, suite] of sortedSuites) {
      await this.runTestSuite(suiteName, suite);
      
      // Stop on critical failures if configured
      if (suite.critical && this.results.testSuites[suiteName]?.status === 'failed') {
        if (this.config.stopOnCriticalFailure) {
          throw new Error(`Critical test suite failed: ${suiteName}`);
        }
      }
    }
  }

  async runTestSuite(suiteName, suite) {
    const startTime = Date.now();
    console.log(`📋 Running test suite: ${suiteName}`);
    console.log(`   Description: ${suite.description}`);

    try {
      const testFile = path.join(__dirname, suite.file);
      
      if (!fs.existsSync(testFile)) {
        throw new Error(`Test file not found: ${suite.file}`);
      }

      // Run Jest for specific test file
      const jestCommand = [
        'npx jest',
        `"${testFile}"`,
        '--testTimeout', this.config.timeout,
        '--verbose',
        '--json',
        '--outputFile', `/tmp/jest-${suiteName}.json`
      ].join(' ');

      const result = execSync(jestCommand, {
        cwd: path.dirname(path.dirname(__dirname)),
        env: {
          ...process.env,
          DEPLOY_URL: this.config.baseUrl,
          NODE_ENV: this.config.environment
        },
        stdio: 'pipe',
        timeout: this.config.timeout
      });

      // Parse Jest output
      const jestOutput = JSON.parse(
        fs.readFileSync(`/tmp/jest-${suiteName}.json`, 'utf8')
      );

      this.results.testSuites[suiteName] = {
        status: jestOutput.success ? 'passed' : 'failed',
        duration: Date.now() - startTime,
        tests: jestOutput.numTotalTests,
        passed: jestOutput.numPassedTests,
        failed: jestOutput.numFailedTests,
        skipped: jestOutput.numPendingTests,
        details: jestOutput.testResults[0],
        critical: suite.critical
      };

      this.results.totalTests += jestOutput.numTotalTests;
      this.results.passedTests += jestOutput.numPassedTests;
      this.results.failedTests += jestOutput.numFailedTests;
      this.results.skippedTests += jestOutput.numPendingTests;

      if (jestOutput.success) {
        console.log(`✅ ${suiteName}: All tests passed (${jestOutput.numPassedTests}/${jestOutput.numTotalTests})`);
      } else {
        console.log(`❌ ${suiteName}: ${jestOutput.numFailedTests} test(s) failed`);
        
        if (suite.critical) {
          this.results.criticalFailures.push({
            type: 'CRITICAL_TEST_FAILURE',
            suite: suiteName,
            failures: jestOutput.numFailedTests,
            timestamp: new Date()
          });
        }
      }

    } catch (error) {
      console.log(`❌ ${suiteName}: Test suite execution failed - ${error.message}`);
      
      this.results.testSuites[suiteName] = {
        status: 'error',
        duration: Date.now() - startTime,
        error: error.message,
        critical: suite.critical
      };

      if (suite.critical) {
        this.results.criticalFailures.push({
          type: 'TEST_EXECUTION_ERROR',
          suite: suiteName,
          error: error.message,
          timestamp: new Date()
        });
      }
    } finally {
      // Cleanup temporary files
      try {
        fs.unlinkSync(`/tmp/jest-${suiteName}.json`);
      } catch (e) {
        // Ignore cleanup errors
      }
    }
  }

  async postValidationAnalysis() {
    console.log('📊 Performing post-validation analysis...');

    // Calculate success rate
    const totalTests = this.results.totalTests;
    const passedTests = this.results.passedTests;
    const successRate = totalTests > 0 ? (passedTests / totalTests * 100).toFixed(2) : 0;

    // Determine overall status
    let overallStatus = 'passed';
    if (this.results.criticalFailures.length > 0) {
      overallStatus = 'critical_failure';
    } else if (this.results.failedTests > 0) {
      overallStatus = 'failed';
    } else if (this.results.passedTests === 0) {
      overallStatus = 'no_tests_run';
    }

    // Generate recommendations
    const recommendations = this.generateRecommendations();

    this.results.summary = {
      overallStatus,
      successRate: parseFloat(successRate),
      duration: this.results.endTime - this.results.startTime,
      recommendations,
      deploymentReady: overallStatus === 'passed',
      criticalIssuesCount: this.results.criticalFailures.length,
      warningsCount: this.results.warnings.length
    };

    console.log(`📈 Success Rate: ${successRate}%`);
    console.log(`⏱️  Total Duration: ${this.formatDuration(this.results.summary.duration)}`);
    console.log(`🎯 Overall Status: ${overallStatus.toUpperCase()}`);
  }

  generateRecommendations() {
    const recommendations = [];

    // Check for critical failures
    if (this.results.criticalFailures.length > 0) {
      recommendations.push({
        priority: 'critical',
        message: 'Critical test failures detected. Deployment should not proceed.',
        actions: ['Fix critical issues before deploying', 'Run validation again']
      });
    }

    // Check success rate
    if (this.results.summary?.successRate < 90) {
      recommendations.push({
        priority: 'high',
        message: 'Success rate below 90%. Consider investigating failures.',
        actions: ['Review failed tests', 'Fix identified issues']
      });
    }

    // Check for warnings
    if (this.results.warnings.length > 0) {
      recommendations.push({
        priority: 'medium',
        message: `${this.results.warnings.length} warnings detected.`,
        actions: ['Review warnings', 'Consider addressing before production']
      });
    }

    return recommendations;
  }

  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      environment: this.config.environment,
      targetUrl: this.config.baseUrl,
      summary: this.results.summary,
      testResults: this.results.testSuites,
      criticalFailures: this.results.criticalFailures,
      warnings: this.results.warnings,
      statistics: {
        totalTests: this.results.totalTests,
        passedTests: this.results.passedTests,
        failedTests: this.results.failedTests,
        skippedTests: this.results.skippedTests,
        successRate: this.results.summary.successRate
      }
    };

    // Write detailed report to file
    const reportPath = path.join(__dirname, `validation-report-${Date.now()}.json`);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    // Console summary
    this.printConsoleSummary();

    console.log(`\n📄 Detailed report saved to: ${reportPath}`);
  }

  printConsoleSummary() {
    console.log('\n' + '='.repeat(80));
    console.log('🚀 DEPLOYMENT VALIDATION SUMMARY');
    console.log('='.repeat(80));
    
    console.log(`Target URL: ${this.config.baseUrl}`);
    console.log(`Environment: ${this.config.environment}`);
    console.log(`Duration: ${this.formatDuration(this.results.summary.duration)}`);
    console.log(`Overall Status: ${this.results.summary.overallStatus.toUpperCase()}`);
    
    console.log('\n📊 Test Statistics:');
    console.log(`Total Tests: ${this.results.totalTests}`);
    console.log(`Passed: ${this.results.passedTests}`);
    console.log(`Failed: ${this.results.failedTests}`);
    console.log(`Skipped: ${this.results.skippedTests}`);
    console.log(`Success Rate: ${this.results.summary.successRate}%`);

    console.log('\n📋 Test Suites:');
    Object.entries(this.results.testSuites).forEach(([name, result]) => {
      const status = result.status === 'passed' ? '✅' : result.status === 'failed' ? '❌' : '⚠️';
      const duration = this.formatDuration(result.duration);
      console.log(`  ${status} ${name}: ${result.status.toUpperCase()} (${duration})`);
    });

    if (this.results.criticalFailures.length > 0) {
      console.log('\n🚨 Critical Failures:');
      this.results.criticalFailures.forEach(failure => {
        console.log(`  - ${failure.type}: ${failure.message || failure.suite}`);
      });
    }

    if (this.results.summary.recommendations.length > 0) {
      console.log('\n💡 Recommendations:');
      this.results.summary.recommendations.forEach(rec => {
        const priority = rec.priority === 'critical' ? '🚨' : rec.priority === 'high' ? '⚠️' : 'ℹ️';
        console.log(`  ${priority} ${rec.message}`);
      });
    }

    const readyIcon = this.results.summary.deploymentReady ? '✅' : '❌';
    console.log(`\n${readyIcon} Deployment Ready: ${this.results.summary.deploymentReady ? 'YES' : 'NO'}`);
    console.log('='.repeat(80));
  }

  formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  }
}

module.exports = { DeploymentValidator };

// CLI usage
if (require.main === module) {
  const config = {
    baseUrl: process.argv[2] || process.env.DEPLOY_URL || 'http://localhost:8080',
    environment: process.argv[3] || process.env.NODE_ENV || 'production'
  };

  const validator = new DeploymentValidator(config);
  
  validator.validateDeployment()
    .then(results => {
      console.log('\n✅ Validation completed successfully');
      process.exit(results.summary.deploymentReady ? 0 : 1);
    })
    .catch(error => {
      console.error('\n❌ Validation failed:', error.message);
      process.exit(1);
    });
}