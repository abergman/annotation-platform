#!/usr/bin/env python3
"""
Setup script for monitoring and logging system

This script initializes the monitoring infrastructure, creates necessary
directories, sets up log rotation, and validates the monitoring configuration.
"""

import os
import sys
import yaml
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any

def create_directories():
    """Create necessary directories for logging and monitoring."""
    directories = [
        'logs',
        'exports',
        'backups',
        'monitoring/data',
        'monitoring/alerts',
        'config',
    ]
    
    print("Creating monitoring directories...")
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created {directory}")
    
    # Set appropriate permissions for log directories
    if os.name != 'nt':  # Unix/Linux systems
        try:
            os.chmod('logs', 0o755)
            os.chmod('exports', 0o755)
            print("  ✓ Set directory permissions")
        except OSError as e:
            print(f"  ⚠ Could not set permissions: {e}")


def setup_logrotate():
    """Setup logrotate configuration for log files."""
    logrotate_config = """
# Log rotation for Text Annotation System
/path/to/annotation/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    copytruncate
    notifempty
    create 644 www-data www-data
    
    postrotate
        # Send USR1 signal to application to reopen log files
        /bin/kill -USR1 `cat /var/run/annotation-system.pid 2> /dev/null` 2> /dev/null || true
    endscript
}

# Security logs - longer retention
/path/to/annotation/logs/security.log {
    daily
    missingok
    rotate 90
    compress
    delaycompress
    copytruncate
    notifempty
    create 644 www-data www-data
}

# Audit logs - longest retention
/path/to/annotation/logs/audit_trail.log {
    daily
    missingok
    rotate 365
    compress
    delaycompress
    copytruncate
    notifempty
    create 644 www-data www-data
}
"""
    
    logrotate_file = Path('config/logrotate.conf')
    try:
        with open(logrotate_file, 'w') as f:
            f.write(logrotate_config.replace('/path/to/annotation', str(Path.cwd())))
        
        print("✓ Created logrotate configuration")
        print(f"  To enable logrotate, copy {logrotate_file} to /etc/logrotate.d/annotation-system")
        
    except IOError as e:
        print(f"⚠ Could not create logrotate config: {e}")


def validate_config():
    """Validate monitoring configuration files."""
    config_files = [
        'config/logging.yaml',
        'config/monitoring.yaml'
    ]
    
    print("Validating configuration files...")
    
    for config_file in config_files:
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"  ⚠ Missing config file: {config_file}")
            continue
            
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Basic validation
            if not isinstance(config, dict):
                print(f"  ✗ Invalid YAML structure in {config_file}")
                continue
                
            print(f"  ✓ Valid configuration: {config_file}")
            
        except yaml.YAMLError as e:
            print(f"  ✗ YAML syntax error in {config_file}: {e}")
        except IOError as e:
            print(f"  ⚠ Could not read {config_file}: {e}")


def install_dependencies():
    """Install monitoring dependencies."""
    dependencies = [
        'structlog',
        'psutil',
        'colorama',
        'python-json-logger',
        'pyyaml'
    ]
    
    print("Checking monitoring dependencies...")
    
    missing_deps = []
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            print(f"  ✓ {dep}")
        except ImportError:
            missing_deps.append(dep)
            print(f"  ✗ {dep} (missing)")
    
    if missing_deps:
        print(f"\nInstalling missing dependencies: {' '.join(missing_deps)}")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_deps)
            print("✓ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install dependencies: {e}")
            return False
    
    return True


def setup_systemd_service():
    """Create systemd service file template."""
    service_config = """
[Unit]
Description=Text Annotation System
After=network.target postgresql.service

[Service]
Type=exec
User=annotation-user
Group=annotation-group
WorkingDirectory=/path/to/annotation
Environment=PATH=/path/to/annotation/venv/bin
Environment=PYTHONPATH=/path/to/annotation
ExecStart=/path/to/annotation/venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -USR1 $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=annotation-system

# Security
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/path/to/annotation/logs /path/to/annotation/uploads /path/to/annotation/exports

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path('config/annotation-system.service')
    try:
        with open(service_file, 'w') as f:
            f.write(service_config.replace('/path/to/annotation', str(Path.cwd())))
        
        print("✓ Created systemd service file template")
        print(f"  To enable service, copy {service_file} to /etc/systemd/system/")
        
    except IOError as e:
        print(f"⚠ Could not create systemd service file: {e}")


def create_monitoring_scripts():
    """Create monitoring and maintenance scripts."""
    
    # Health check script
    health_check_script = '''#!/usr/bin/env python3
"""Health check script for monitoring systems."""

import requests
import sys
import json
from datetime import datetime

def check_health():
    """Check application health."""
    try:
        response = requests.get('http://localhost:8000/api/monitoring/health', timeout=10)
        response.raise_for_status()
        
        health_data = response.json()
        
        if health_data.get('status') == 'healthy':
            print(f"✓ System healthy at {datetime.now()}")
            return 0
        else:
            print(f"⚠ System degraded: {health_data.get('status')}")
            print(json.dumps(health_data, indent=2))
            return 1
            
    except requests.RequestException as e:
        print(f"✗ Health check failed: {e}")
        return 2

if __name__ == '__main__':
    sys.exit(check_health())
'''
    
    # Log analyzer script  
    log_analyzer_script = '''#!/usr/bin/env python3
"""Log analysis script for monitoring."""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_logs(log_file, hours=24):
    """Analyze log file for errors and patterns."""
    if not Path(log_file).exists():
        print(f"Log file not found: {log_file}")
        return
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    error_count = 0
    warning_count = 0
    request_count = 0
    slow_requests = []
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                log_entry = json.loads(line.strip())
                
                # Parse timestamp
                timestamp_str = log_entry.get('timestamp', '')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if timestamp < cutoff_time:
                        continue
                
                event = log_entry.get('event', '').lower()
                
                if 'error' in event:
                    error_count += 1
                elif 'warning' in event:
                    warning_count += 1
                elif 'request' in event:
                    request_count += 1
                    
                    response_time = log_entry.get('response_time_ms')
                    if response_time and response_time > 5000:
                        slow_requests.append({
                            'endpoint': log_entry.get('endpoint'),
                            'response_time_ms': response_time,
                            'timestamp': timestamp_str
                        })
                        
            except (json.JSONDecodeError, ValueError):
                continue
    
    print(f"Log Analysis Report - Last {hours} hours")
    print(f"Errors: {error_count}")
    print(f"Warnings: {warning_count}")  
    print(f"Requests: {request_count}")
    print(f"Slow requests: {len(slow_requests)}")
    
    if slow_requests:
        print("\\nTop slow requests:")
        for req in sorted(slow_requests, key=lambda x: x['response_time_ms'], reverse=True)[:5]:
            print(f"  {req['endpoint']}: {req['response_time_ms']}ms at {req['timestamp']}")

if __name__ == '__main__':
    log_file = sys.argv[1] if len(sys.argv) > 1 else 'logs/application.log'
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    analyze_logs(log_file, hours)
'''
    
    scripts = {
        'scripts/health_check.py': health_check_script,
        'scripts/analyze_logs.py': log_analyzer_script
    }
    
    # Create scripts directory
    Path('scripts').mkdir(exist_ok=True)
    
    for script_path, script_content in scripts.items():
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable on Unix systems
            if os.name != 'nt':
                os.chmod(script_path, 0o755)
            
            print(f"✓ Created {script_path}")
            
        except IOError as e:
            print(f"⚠ Could not create {script_path}: {e}")


def setup_cron_jobs():
    """Create cron job templates for monitoring tasks."""
    cron_template = """
# Text Annotation System Monitoring Cron Jobs
# Add these to your crontab with: crontab -e

# Health check every 5 minutes
*/5 * * * * /path/to/annotation/scripts/health_check.py >> /path/to/annotation/logs/health_check.log 2>&1

# Log analysis every hour
0 * * * * /path/to/annotation/scripts/analyze_logs.py logs/application.log 1 >> /path/to/annotation/logs/log_analysis.log 2>&1

# Daily log cleanup and analysis
0 2 * * * find /path/to/annotation/logs -name "*.log.[0-9]*" -mtime +30 -delete

# Weekly metrics export
0 3 * * 0 curl -s http://localhost:8000/api/monitoring/export/metrics?hours=168 > /dev/null

# Monthly system report
0 4 1 * * /path/to/annotation/scripts/analyze_logs.py logs/application.log 720 > /path/to/annotation/reports/monthly_report_$(date +%Y%m).txt
"""
    
    cron_file = Path('config/monitoring.cron')
    try:
        with open(cron_file, 'w') as f:
            f.write(cron_template.replace('/path/to/annotation', str(Path.cwd())))
        
        print("✓ Created cron job template")
        print(f"  To enable cron jobs, add contents of {cron_file} to your crontab")
        
    except IOError as e:
        print(f"⚠ Could not create cron template: {e}")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description='Setup monitoring system for Text Annotation Platform')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency installation')
    parser.add_argument('--minimal', action='store_true', help='Minimal setup (directories and configs only)')
    
    args = parser.parse_args()
    
    print("Setting up Text Annotation System Monitoring")
    print("=" * 50)
    
    # Always create directories and validate config
    create_directories()
    validate_config()
    
    if not args.minimal:
        if not args.skip_deps:
            if not install_dependencies():
                print("⚠ Dependency installation failed, continuing with setup...")
        
        setup_logrotate()
        setup_systemd_service()
        create_monitoring_scripts()
        setup_cron_jobs()
    
    print("\n" + "=" * 50)
    print("Monitoring setup complete!")
    print("\nNext steps:")
    print("1. Review configuration files in config/")
    print("2. Install system dependencies if needed")
    print("3. Set up logrotate and systemd service")
    print("4. Configure cron jobs for automated monitoring")
    print("5. Test the monitoring endpoints")
    
    print("\nTest monitoring with:")
    print("  python -m uvicorn src.main:app --reload")
    print("  curl http://localhost:8000/api/monitoring/health")


if __name__ == '__main__':
    main()