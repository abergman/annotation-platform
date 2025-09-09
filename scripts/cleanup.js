#!/usr/bin/env node

/**
 * Cleanup Script for Annotation Platform
 * Handles database cleanup, file cleanup, and system maintenance
 */

import { MongoClient } from 'mongodb';
import fs from 'fs/promises';
import path from 'path';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/annotation_platform';
const CLEANUP_LOGS_DAYS = parseInt(process.env.CLEANUP_LOGS_DAYS || '30', 10);
const CLEANUP_TEMP_FILES_DAYS = parseInt(process.env.CLEANUP_TEMP_FILES_DAYS || '7', 10);
const CLEANUP_UPLOADS_DAYS = parseInt(process.env.CLEANUP_UPLOADS_DAYS || '90', 10);

class CleanupManager {
    constructor() {
        this.mongoUri = MONGODB_URI;
        this.logsRetentionDays = CLEANUP_LOGS_DAYS;
        this.tempFilesRetentionDays = CLEANUP_TEMP_FILES_DAYS;
        this.uploadsRetentionDays = CLEANUP_UPLOADS_DAYS;
    }

    log(message, level = 'info') {
        const timestamp = new Date().toISOString();
        console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}`);
    }

    async connectToDatabase() {
        try {
            this.client = new MongoClient(this.mongoUri);
            await this.client.connect();
            this.db = this.client.db();
            this.log('Connected to MongoDB');
        } catch (error) {
            throw new Error(`Failed to connect to database: ${error.message}`);
        }
    }

    async disconnectFromDatabase() {
        if (this.client) {
            await this.client.close();
            this.log('Disconnected from MongoDB');
        }
    }

    async cleanupExpiredSessions() {
        this.log('Cleaning up expired sessions...');
        
        try {
            const result = await this.db.collection('sessions').deleteMany({
                expiresAt: { $lt: new Date() }
            });
            
            this.log(`Deleted ${result.deletedCount} expired sessions`);
            return result.deletedCount;
        } catch (error) {
            this.log(`Session cleanup failed: ${error.message}`, 'error');
            return 0;
        }
    }

    async cleanupOldNotifications() {
        const cutoffDate = new Date(Date.now() - (30 * 24 * 60 * 60 * 1000)); // 30 days
        this.log(`Cleaning up notifications older than ${cutoffDate.toISOString()}...`);
        
        try {
            const result = await this.db.collection('notifications').deleteMany({
                createdAt: { $lt: cutoffDate },
                read: true
            });
            
            this.log(`Deleted ${result.deletedCount} old read notifications`);
            return result.deletedCount;
        } catch (error) {
            this.log(`Notification cleanup failed: ${error.message}`, 'error');
            return 0;
        }
    }

    async cleanupOrphanedDocuments() {
        this.log('Cleaning up orphaned annotation documents...');
        
        try {
            // Find annotations that reference non-existent documents
            const orphanedAnnotations = await this.db.collection('annotations').aggregate([
                {
                    $lookup: {
                        from: 'documents',
                        localField: 'documentId',
                        foreignField: '_id',
                        as: 'document'
                    }
                },
                {
                    $match: { document: { $size: 0 } }
                },
                {
                    $project: { _id: 1 }
                }
            ]).toArray();

            if (orphanedAnnotations.length > 0) {
                const orphanedIds = orphanedAnnotations.map(a => a._id);
                const result = await this.db.collection('annotations').deleteMany({
                    _id: { $in: orphanedIds }
                });
                
                this.log(`Deleted ${result.deletedCount} orphaned annotations`);
                return result.deletedCount;
            } else {
                this.log('No orphaned annotations found');
                return 0;
            }
        } catch (error) {
            this.log(`Orphaned document cleanup failed: ${error.message}`, 'error');
            return 0;
        }
    }

    async cleanupOldAuditLogs() {
        const cutoffDate = new Date(Date.now() - (90 * 24 * 60 * 60 * 1000)); // 90 days
        this.log(`Cleaning up audit logs older than ${cutoffDate.toISOString()}...`);
        
        try {
            const result = await this.db.collection('audit_logs').deleteMany({
                timestamp: { $lt: cutoffDate }
            });
            
            this.log(`Deleted ${result.deletedCount} old audit log entries`);
            return result.deletedCount;
        } catch (error) {
            this.log(`Audit log cleanup failed: ${error.message}`, 'error');
            return 0;
        }
    }

    async optimizeDatabase() {
        this.log('Optimizing database indexes and collections...');
        
        try {
            const collections = await this.db.listCollections().toArray();
            
            for (const collection of collections) {
                const collName = collection.name;
                
                // Reindex collection
                await this.db.collection(collName).reIndex();
                this.log(`Reindexed collection: ${collName}`);
                
                // Get collection stats
                const stats = await this.db.collection(collName).stats();
                this.log(`Collection ${collName}: ${stats.count} documents, ${Math.round(stats.storageSize / 1024 / 1024)}MB`);
            }
        } catch (error) {
            this.log(`Database optimization failed: ${error.message}`, 'error');
        }
    }

    async cleanupLogFiles() {
        this.log(`Cleaning up log files older than ${this.logsRetentionDays} days...`);
        
        const logDirs = ['./logs', '/var/log/annotation'];
        let deletedCount = 0;
        
        for (const logDir of logDirs) {
            try {
                const files = await fs.readdir(logDir).catch(() => []);
                const cutoffTime = new Date(Date.now() - (this.logsRetentionDays * 24 * 60 * 60 * 1000));
                
                for (const file of files) {
                    const filePath = path.join(logDir, file);
                    
                    try {
                        const stats = await fs.stat(filePath);
                        
                        if (stats.isFile() && stats.mtime < cutoffTime) {
                            await fs.unlink(filePath);
                            this.log(`Deleted old log file: ${filePath}`);
                            deletedCount++;
                        }
                    } catch (error) {
                        // File might not exist or be inaccessible
                        continue;
                    }
                }
            } catch (error) {
                this.log(`Failed to clean log directory ${logDir}: ${error.message}`, 'error');
            }
        }
        
        this.log(`Deleted ${deletedCount} old log files`);
        return deletedCount;
    }

    async cleanupTempFiles() {
        this.log(`Cleaning up temporary files older than ${this.tempFilesRetentionDays} days...`);
        
        const tempDirs = ['./tmp', '/tmp/annotation', './uploads/temp'];
        let deletedCount = 0;
        
        for (const tempDir of tempDirs) {
            try {
                const files = await fs.readdir(tempDir).catch(() => []);
                const cutoffTime = new Date(Date.now() - (this.tempFilesRetentionDays * 24 * 60 * 60 * 1000));
                
                for (const file of files) {
                    const filePath = path.join(tempDir, file);
                    
                    try {
                        const stats = await fs.stat(filePath);
                        
                        if (stats.mtime < cutoffTime) {
                            await fs.rm(filePath, { recursive: true, force: true });
                            this.log(`Deleted temp file/directory: ${filePath}`);
                            deletedCount++;
                        }
                    } catch (error) {
                        continue;
                    }
                }
            } catch (error) {
                this.log(`Failed to clean temp directory ${tempDir}: ${error.message}`, 'error');
            }
        }
        
        this.log(`Deleted ${deletedCount} temporary files/directories`);
        return deletedCount;
    }

    async cleanupOldUploads() {
        this.log(`Cleaning up unreferenced uploads older than ${this.uploadsRetentionDays} days...`);
        
        try {
            const uploadsDir = './uploads';
            const files = await fs.readdir(uploadsDir).catch(() => []);
            const cutoffTime = new Date(Date.now() - (this.uploadsRetentionDays * 24 * 60 * 60 * 1000));
            let deletedCount = 0;
            
            for (const file of files) {
                const filePath = path.join(uploadsDir, file);
                
                try {
                    const stats = await fs.stat(filePath);
                    
                    if (stats.isFile() && stats.mtime < cutoffTime) {
                        // Check if file is referenced in database
                        const isReferenced = await this.db.collection('documents').findOne({
                            $or: [
                                { filePath: filePath },
                                { filePath: file },
                                { originalName: file }
                            ]
                        });
                        
                        if (!isReferenced) {
                            await fs.unlink(filePath);
                            this.log(`Deleted unreferenced upload: ${filePath}`);
                            deletedCount++;
                        }
                    }
                } catch (error) {
                    continue;
                }
            }
            
            this.log(`Deleted ${deletedCount} unreferenced upload files`);
            return deletedCount;
        } catch (error) {
            this.log(`Upload cleanup failed: ${error.message}`, 'error');
            return 0;
        }
    }

    async generateCleanupReport() {
        this.log('Generating cleanup report...');
        
        try {
            const collections = await this.db.listCollections().toArray();
            const report = {
                timestamp: new Date().toISOString(),
                database: {
                    collections: []
                },
                fileSystem: {
                    logFiles: await this.getDirectoryInfo('./logs'),
                    tempFiles: await this.getDirectoryInfo('./tmp'),
                    uploads: await this.getDirectoryInfo('./uploads')
                }
            };
            
            for (const collection of collections) {
                const stats = await this.db.collection(collection.name).stats().catch(() => null);
                if (stats) {
                    report.database.collections.push({
                        name: collection.name,
                        count: stats.count,
                        size: stats.size,
                        storageSize: stats.storageSize,
                        avgObjSize: stats.avgObjSize
                    });
                }
            }
            
            const reportPath = `./reports/cleanup-report-${Date.now()}.json`;
            await fs.mkdir('./reports', { recursive: true });
            await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
            
            this.log(`Cleanup report generated: ${reportPath}`);
            return report;
        } catch (error) {
            this.log(`Report generation failed: ${error.message}`, 'error');
            return null;
        }
    }

    async getDirectoryInfo(dirPath) {
        try {
            const files = await fs.readdir(dirPath);
            let totalSize = 0;
            let fileCount = 0;
            
            for (const file of files) {
                const filePath = path.join(dirPath, file);
                const stats = await fs.stat(filePath);
                if (stats.isFile()) {
                    totalSize += stats.size;
                    fileCount++;
                }
            }
            
            return {
                path: dirPath,
                fileCount,
                totalSize,
                totalSizeMB: Math.round(totalSize / 1024 / 1024)
            };
        } catch (error) {
            return {
                path: dirPath,
                error: error.message
            };
        }
    }

    async performFullCleanup() {
        this.log('=== Starting Full Cleanup Process ===');
        
        const results = {
            database: {},
            files: {},
            startTime: new Date(),
            success: true
        };
        
        try {
            await this.connectToDatabase();
            
            // Database cleanup
            results.database.expiredSessions = await this.cleanupExpiredSessions();
            results.database.oldNotifications = await this.cleanupOldNotifications();
            results.database.orphanedDocuments = await this.cleanupOrphanedDocuments();
            results.database.oldAuditLogs = await this.cleanupOldAuditLogs();
            
            await this.optimizeDatabase();
            
            // File system cleanup
            results.files.logFiles = await this.cleanupLogFiles();
            results.files.tempFiles = await this.cleanupTempFiles();
            results.files.uploads = await this.cleanupOldUploads();
            
            // Generate report
            const report = await this.generateCleanupReport();
            
            results.endTime = new Date();
            results.duration = results.endTime - results.startTime;
            
            this.log('=== Cleanup Process Completed Successfully ===');
            this.log(`Total duration: ${Math.round(results.duration / 1000)}s`);
            
            return results;
        } catch (error) {
            this.log(`=== Cleanup Process Failed ===`, 'error');
            this.log(`Error: ${error.message}`, 'error');
            
            results.success = false;
            results.error = error.message;
            results.endTime = new Date();
            
            return results;
        } finally {
            await this.disconnectFromDatabase();
        }
    }
}

// Command line interface
async function main() {
    const args = process.argv.slice(2);
    const command = args[0] || 'full';
    
    const cleanupManager = new CleanupManager();
    
    try {
        switch (command) {
            case 'database':
                await cleanupManager.connectToDatabase();
                await cleanupManager.cleanupExpiredSessions();
                await cleanupManager.cleanupOldNotifications();
                await cleanupManager.cleanupOrphanedDocuments();
                await cleanupManager.cleanupOldAuditLogs();
                await cleanupManager.optimizeDatabase();
                await cleanupManager.disconnectFromDatabase();
                console.log('✅ Database cleanup completed');
                break;
                
            case 'files':
                await cleanupManager.cleanupLogFiles();
                await cleanupManager.cleanupTempFiles();
                await cleanupManager.cleanupOldUploads();
                console.log('✅ File cleanup completed');
                break;
                
            case 'full':
                {
                    const results = await cleanupManager.performFullCleanup();
                    if (results.success) {
                        console.log('✅ Full cleanup completed successfully');
                        console.log(`Duration: ${Math.round(results.duration / 1000)}s`);
                    } else {
                        console.error(`❌ Cleanup failed: ${results.error}`);
                        process.exit(1);
                    }
                }
                break;
                
            case 'report':
                await cleanupManager.connectToDatabase();
                const report = await cleanupManager.generateCleanupReport();
                await cleanupManager.disconnectFromDatabase();
                if (report) {
                    console.log('✅ Report generated successfully');
                    console.log(`Database collections: ${report.database.collections.length}`);
                    console.log(`Log files: ${report.fileSystem.logFiles.fileCount || 0}`);
                    console.log(`Temp files: ${report.fileSystem.tempFiles.fileCount || 0}`);
                    console.log(`Upload files: ${report.fileSystem.uploads.fileCount || 0}`);
                } else {
                    console.error('❌ Report generation failed');
                    process.exit(1);
                }
                break;
                
            default:
                console.log(`
Cleanup Manager for Annotation Platform

Usage:
  node cleanup.js [command]

Commands:
  full         # Complete cleanup (database + files)
  database     # Database cleanup only
  files        # File cleanup only  
  report       # Generate cleanup report only

Environment Variables:
  MONGODB_URI                  # Database connection string
  CLEANUP_LOGS_DAYS           # Log retention days (default: 30)
  CLEANUP_TEMP_FILES_DAYS     # Temp file retention days (default: 7)
  CLEANUP_UPLOADS_DAYS        # Upload retention days (default: 90)

Examples:
  node cleanup.js              # Full cleanup
  node cleanup.js database     # Database only
  node cleanup.js files        # Files only
  node cleanup.js report       # Generate report
                `);
                break;
        }
    } catch (error) {
        console.error(`❌ Cleanup failed: ${error.message}`);
        process.exit(1);
    }
}

// Export for use as a module
export { CleanupManager };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(console.error);
}