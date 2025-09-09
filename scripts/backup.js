#!/usr/bin/env node

/**
 * Database Backup Script for Annotation Platform
 * Creates backups of MongoDB database with rotation and cloud storage
 */

import { MongoClient } from 'mongodb';
import fs from 'fs/promises';
import { createWriteStream, createReadStream } from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const BACKUP_DIR = process.env.BACKUP_DIR || './backups';
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/annotation_platform';
const BACKUP_RETENTION_DAYS = parseInt(process.env.BACKUP_RETENTION_DAYS || '7', 10);
const COMPRESS_BACKUPS = process.env.COMPRESS_BACKUPS !== 'false';

class BackupManager {
    constructor() {
        this.backupDir = BACKUP_DIR;
        this.mongoUri = MONGODB_URI;
        this.retentionDays = BACKUP_RETENTION_DAYS;
        this.compress = COMPRESS_BACKUPS;
    }

    log(message, level = 'info') {
        const timestamp = new Date().toISOString();
        console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}`);
    }

    async ensureBackupDirectory() {
        try {
            await fs.mkdir(this.backupDir, { recursive: true });
            this.log(`Backup directory ensured: ${this.backupDir}`);
        } catch (error) {
            throw new Error(`Failed to create backup directory: ${error.message}`);
        }
    }

    async createDatabaseBackup() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const backupName = `annotation_backup_${timestamp}`;
        const backupPath = path.join(this.backupDir, backupName);

        this.log(`Starting database backup: ${backupName}`);

        try {
            // Use mongodump to create backup
            const mongodumpCmd = `mongodump --uri="${this.mongoUri}" --out="${backupPath}"`;
            
            this.log('Executing mongodump...');
            execSync(mongodumpCmd, { stdio: 'inherit' });

            // Compress if enabled
            if (this.compress) {
                await this.compressBackup(backupPath, `${backupPath}.tar.gz`);
                
                // Remove uncompressed backup
                await fs.rm(backupPath, { recursive: true, force: true });
                
                return `${backupPath}.tar.gz`;
            }

            return backupPath;
        } catch (error) {
            this.log(`Backup failed: ${error.message}`, 'error');
            throw error;
        }
    }

    async compressBackup(sourcePath, targetPath) {
        this.log(`Compressing backup: ${sourcePath} -> ${targetPath}`);
        
        try {
            const tarCmd = `tar -czf "${targetPath}" -C "${this.backupDir}" "${path.basename(sourcePath)}"`;
            execSync(tarCmd, { stdio: 'inherit' });
            this.log('Compression completed');
        } catch (error) {
            throw new Error(`Compression failed: ${error.message}`);
        }
    }

    async uploadToCloud(backupPath) {
        // Digital Ocean Spaces upload (if configured)
        const doSpacesKey = process.env.DO_SPACES_KEY;
        const doSpacesSecret = process.env.DO_SPACES_SECRET;
        const doSpacesRegion = process.env.DO_SPACES_REGION;
        const doSpacesBucket = process.env.DO_SPACES_BUCKET;

        if (doSpacesKey && doSpacesSecret && doSpacesRegion && doSpacesBucket) {
            this.log('Uploading backup to Digital Ocean Spaces...');
            
            try {
                // Use s3cmd for Digital Ocean Spaces upload
                const fileName = path.basename(backupPath);
                const s3Url = `s3://${doSpacesBucket}/backups/${fileName}`;
                
                const s3Cmd = `s3cmd put "${backupPath}" "${s3Url}" --access_key="${doSpacesKey}" --secret_key="${doSpacesSecret}" --host="${doSpacesRegion}.digitaloceanspaces.com" --host-bucket="%(bucket)s.${doSpacesRegion}.digitaloceanspaces.com"`;
                
                execSync(s3Cmd, { stdio: 'inherit' });
                this.log(`Backup uploaded to cloud: ${s3Url}`);
                
                return s3Url;
            } catch (error) {
                this.log(`Cloud upload failed: ${error.message}`, 'error');
                // Don't throw error - local backup is still valid
            }
        } else {
            this.log('Cloud storage not configured, skipping upload');
        }

        return null;
    }

    async cleanupOldBackups() {
        this.log('Cleaning up old backups...');
        
        try {
            const files = await fs.readdir(this.backupDir);
            const now = new Date();
            const cutoffTime = new Date(now.getTime() - (this.retentionDays * 24 * 60 * 60 * 1000));
            
            let deletedCount = 0;
            
            for (const file of files) {
                const filePath = path.join(this.backupDir, file);
                const stats = await fs.stat(filePath);
                
                if (stats.mtime < cutoffTime) {
                    await fs.rm(filePath, { recursive: true, force: true });
                    this.log(`Deleted old backup: ${file}`);
                    deletedCount++;
                }
            }
            
            this.log(`Cleanup completed. Deleted ${deletedCount} old backups.`);
        } catch (error) {
            this.log(`Cleanup failed: ${error.message}`, 'error');
        }
    }

    async verifyBackup(backupPath) {
        this.log(`Verifying backup: ${backupPath}`);
        
        try {
            const stats = await fs.stat(backupPath);
            
            if (stats.size === 0) {
                throw new Error('Backup file is empty');
            }
            
            // Additional verification for compressed backups
            if (backupPath.endsWith('.tar.gz')) {
                const tarCmd = `tar -tzf "${backupPath}" | head -1`;
                execSync(tarCmd, { stdio: 'pipe' });
            }
            
            this.log(`Backup verification successful. Size: ${Math.round(stats.size / 1024 / 1024)}MB`);
            return true;
        } catch (error) {
            this.log(`Backup verification failed: ${error.message}`, 'error');
            return false;
        }
    }

    async createBackupManifest(backupPath, cloudUrl = null) {
        const manifest = {
            timestamp: new Date().toISOString(),
            backupPath,
            cloudUrl,
            databaseUri: this.mongoUri.replace(/\/\/.*@/, '//***:***@'), // Hide credentials
            compressed: this.compress,
            size: (await fs.stat(backupPath)).size,
            retention: this.retentionDays
        };

        const manifestPath = `${backupPath}.manifest.json`;
        await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
        
        this.log(`Backup manifest created: ${manifestPath}`);
        return manifestPath;
    }

    async performBackup() {
        this.log('=== Starting Backup Process ===');
        
        try {
            await this.ensureBackupDirectory();
            
            const backupPath = await this.createDatabaseBackup();
            
            const isValid = await this.verifyBackup(backupPath);
            if (!isValid) {
                throw new Error('Backup verification failed');
            }
            
            const cloudUrl = await this.uploadToCloud(backupPath);
            
            await this.createBackupManifest(backupPath, cloudUrl);
            
            await this.cleanupOldBackups();
            
            this.log('=== Backup Process Completed Successfully ===');
            
            return {
                success: true,
                backupPath,
                cloudUrl,
                size: (await fs.stat(backupPath)).size
            };
        } catch (error) {
            this.log(`=== Backup Process Failed ===`, 'error');
            this.log(`Error: ${error.message}`, 'error');
            
            return {
                success: false,
                error: error.message
            };
        }
    }

    async listBackups() {
        try {
            const files = await fs.readdir(this.backupDir);
            const backups = [];
            
            for (const file of files) {
                if (file.includes('annotation_backup_') && !file.endsWith('.manifest.json')) {
                    const filePath = path.join(this.backupDir, file);
                    const stats = await fs.stat(filePath);
                    const manifestPath = `${filePath}.manifest.json`;
                    
                    let manifest = {};
                    try {
                        const manifestContent = await fs.readFile(manifestPath, 'utf8');
                        manifest = JSON.parse(manifestContent);
                    } catch (e) {
                        // Manifest not found or invalid
                    }
                    
                    backups.push({
                        name: file,
                        path: filePath,
                        size: stats.size,
                        created: stats.mtime,
                        ...manifest
                    });
                }
            }
            
            // Sort by creation time (newest first)
            backups.sort((a, b) => new Date(b.created) - new Date(a.created));
            
            return backups;
        } catch (error) {
            this.log(`Failed to list backups: ${error.message}`, 'error');
            return [];
        }
    }

    async restore(backupPath, targetUri = null) {
        const uri = targetUri || this.mongoUri;
        
        this.log(`Starting restore from: ${backupPath}`);
        this.log(`Target URI: ${uri.replace(/\/\/.*@/, '//***:***@')}`);
        
        try {
            let restorePath = backupPath;
            
            // Decompress if needed
            if (backupPath.endsWith('.tar.gz')) {
                this.log('Decompressing backup...');
                const tempDir = path.join(this.backupDir, 'temp_restore');
                await fs.mkdir(tempDir, { recursive: true });
                
                const tarCmd = `tar -xzf "${backupPath}" -C "${tempDir}"`;
                execSync(tarCmd, { stdio: 'inherit' });
                
                // Find the backup directory in the extracted files
                const extracted = await fs.readdir(tempDir);
                restorePath = path.join(tempDir, extracted[0]);
            }
            
            // Use mongorestore
            const mongorestoreCmd = `mongorestore --uri="${uri}" --dir="${restorePath}" --drop`;
            
            this.log('Executing mongorestore...');
            execSync(mongorestoreCmd, { stdio: 'inherit' });
            
            // Cleanup temp directory if we created one
            if (backupPath.endsWith('.tar.gz')) {
                await fs.rm(path.dirname(restorePath), { recursive: true, force: true });
            }
            
            this.log('Restore completed successfully');
            return true;
        } catch (error) {
            this.log(`Restore failed: ${error.message}`, 'error');
            return false;
        }
    }
}

// Command line interface
async function main() {
    const args = process.argv.slice(2);
    const command = args[0];
    
    const backupManager = new BackupManager();
    
    switch (command) {
        case 'create':
            {
                const result = await backupManager.performBackup();
                if (result.success) {
                    console.log(`✅ Backup created successfully: ${result.backupPath}`);
                    if (result.cloudUrl) {
                        console.log(`☁️  Cloud backup: ${result.cloudUrl}`);
                    }
                    console.log(`📊 Size: ${Math.round(result.size / 1024 / 1024)}MB`);
                } else {
                    console.error(`❌ Backup failed: ${result.error}`);
                    process.exit(1);
                }
            }
            break;
            
        case 'list':
            {
                const backups = await backupManager.listBackups();
                console.log(`\n=== Available Backups (${backups.length}) ===`);
                
                backups.forEach((backup, index) => {
                    const size = Math.round(backup.size / 1024 / 1024);
                    const date = new Date(backup.created).toLocaleString();
                    console.log(`${index + 1}. ${backup.name}`);
                    console.log(`   Created: ${date}`);
                    console.log(`   Size: ${size}MB`);
                    if (backup.cloudUrl) {
                        console.log(`   Cloud: ${backup.cloudUrl}`);
                    }
                    console.log('');
                });
            }
            break;
            
        case 'restore':
            {
                const backupPath = args[1];
                const targetUri = args[2];
                
                if (!backupPath) {
                    console.error('❌ Please provide backup path');
                    console.log('Usage: node backup.js restore <backup-path> [target-uri]');
                    process.exit(1);
                }
                
                const success = await backupManager.restore(backupPath, targetUri);
                if (success) {
                    console.log('✅ Restore completed successfully');
                } else {
                    console.error('❌ Restore failed');
                    process.exit(1);
                }
            }
            break;
            
        case 'cleanup':
            await backupManager.cleanupOldBackups();
            console.log('✅ Cleanup completed');
            break;
            
        default:
            console.log(`
Database Backup Manager for Annotation Platform

Usage:
  node backup.js create                     # Create a new backup
  node backup.js list                       # List available backups
  node backup.js restore <path> [target]    # Restore from backup
  node backup.js cleanup                    # Remove old backups

Environment Variables:
  MONGODB_URI              # Database connection string
  BACKUP_DIR               # Backup directory (default: ./backups)
  BACKUP_RETENTION_DAYS    # Days to keep backups (default: 7)
  COMPRESS_BACKUPS         # Compress backups (default: true)
  
  # Digital Ocean Spaces (optional)
  DO_SPACES_KEY            # Access key
  DO_SPACES_SECRET         # Secret key
  DO_SPACES_REGION         # Region (e.g., nyc3)
  DO_SPACES_BUCKET         # Bucket name

Examples:
  node backup.js create
  node backup.js restore ./backups/annotation_backup_2023-11-15T10-30-00-000Z.tar.gz
  node backup.js restore ./backups/backup1.tar.gz mongodb://localhost:27017/test_db
            `);
            break;
    }
}

// Export for use as a module
export { BackupManager };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(console.error);
}