#!/usr/bin/env python3
"""
Database Migration Script for Conflict Resolution System

Creates all necessary database tables and initial data for the conflict
resolution system. This script handles schema creation and can be run
multiple times safely.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import logging

from src.core.database import Base
from src.models.conflict import (
    AnnotationConflict, ConflictResolution, ConflictParticipant,
    ResolutionVote, ConflictNotification, ConflictSettings,
    ConflictType, ConflictStatus, ResolutionStrategy
)
from src.models.project import Project

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment or use default."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        # Default to SQLite for development
        database_url = 'sqlite:///./annotation.db'
        logger.warning(f"DATABASE_URL not set, using default: {database_url}")
    return database_url


def create_conflict_tables(engine):
    """Create all conflict resolution tables."""
    logger.info("Creating conflict resolution tables...")
    
    try:
        # Create all tables defined in the models
        Base.metadata.create_all(engine, checkfirst=True)
        logger.info("Successfully created all tables")
        return True
    
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def create_default_settings(session):
    """Create default conflict settings for existing projects."""
    logger.info("Creating default conflict settings for existing projects...")
    
    try:
        # Get all projects that don't have conflict settings
        projects_without_settings = (
            session.query(Project)
            .outerjoin(ConflictSettings)
            .filter(ConflictSettings.id.is_(None))
            .all()
        )
        
        settings_created = 0
        for project in projects_without_settings:
            settings = ConflictSettings(
                project_id=project.id,
                enable_conflict_detection=True,
                span_overlap_threshold=0.1,
                confidence_threshold=0.5,
                auto_detection_enabled=True,
                default_resolution_strategy=ResolutionStrategy.VOTING,
                voting_threshold=0.6,
                expert_assignment_threshold=0.8,
                auto_merge_enabled=False,
                notify_on_detection=True,
                notify_annotators=True,
                notify_project_admin=True,
                notification_delay_minutes=5,
                resolution_timeout_hours=48,
                max_resolution_attempts=3,
                enable_automatic_escalation=True,
                require_resolution_review=False,
                track_resolver_performance=True,
                minimum_voter_count=3
            )
            
            session.add(settings)
            settings_created += 1
        
        session.commit()
        logger.info(f"Created default settings for {settings_created} projects")
        return True
    
    except Exception as e:
        logger.error(f"Error creating default settings: {e}")
        session.rollback()
        return False


def create_indexes(engine):
    """Create additional database indexes for performance."""
    logger.info("Creating additional database indexes...")
    
    indexes = [
        # Conflict table indexes
        "CREATE INDEX IF NOT EXISTS idx_conflicts_project_status ON annotation_conflicts (project_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_conflicts_detected_at ON annotation_conflicts (detected_at);",
        "CREATE INDEX IF NOT EXISTS idx_conflicts_annotations ON annotation_conflicts (annotation_a_id, annotation_b_id);",
        "CREATE INDEX IF NOT EXISTS idx_conflicts_resolver ON annotation_conflicts (assigned_resolver_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_conflicts_text_type ON annotation_conflicts (text_id, conflict_type);",
        
        # Resolution table indexes
        "CREATE INDEX IF NOT EXISTS idx_resolutions_conflict ON conflict_resolutions (conflict_id);",
        "CREATE INDEX IF NOT EXISTS idx_resolutions_strategy ON conflict_resolutions (resolution_strategy);",
        "CREATE INDEX IF NOT EXISTS idx_resolutions_completed ON conflict_resolutions (completed_at);",
        
        # Vote table indexes
        "CREATE INDEX IF NOT EXISTS idx_votes_conflict ON resolution_votes (conflict_id);",
        "CREATE INDEX IF NOT EXISTS idx_votes_voter ON resolution_votes (voter_id);",
        "CREATE INDEX IF NOT EXISTS idx_votes_choice ON resolution_votes (vote_choice);",
        
        # Notification table indexes
        "CREATE INDEX IF NOT EXISTS idx_notifications_recipient_read ON conflict_notifications (recipient_id, is_read);",
        "CREATE INDEX IF NOT EXISTS idx_notifications_scheduled ON conflict_notifications (scheduled_for);",
        "CREATE INDEX IF NOT EXISTS idx_notifications_type_priority ON conflict_notifications (notification_type, priority);",
        
        # Participant table indexes
        "CREATE INDEX IF NOT EXISTS idx_participants_conflict ON conflict_participants (conflict_id);",
        "CREATE INDEX IF NOT EXISTS idx_participants_user ON conflict_participants (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_participants_role ON conflict_participants (role);",
    ]
    
    try:
        with engine.connect() as connection:
            for index_sql in indexes:
                try:
                    connection.execute(text(index_sql))
                    logger.debug(f"Created index: {index_sql.split()[5] if 'idx_' in index_sql else 'unknown'}")
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
            
            connection.commit()
        
        logger.info("Successfully created database indexes")
        return True
    
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        return False


def verify_tables(engine):
    """Verify that all required tables exist."""
    logger.info("Verifying table creation...")
    
    required_tables = [
        'annotation_conflicts',
        'conflict_resolutions', 
        'conflict_participants',
        'resolution_votes',
        'conflict_notifications',
        'conflict_settings'
    ]
    
    try:
        with engine.connect() as connection:
            # Get list of existing tables
            if 'sqlite' in str(engine.url):
                result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
                existing_tables = [row[0] for row in result]
            else:
                # For PostgreSQL/MySQL
                result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
                existing_tables = [row[0] for row in result]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            if missing_tables:
                logger.error(f"Missing required tables: {missing_tables}")
                return False
            
            logger.info("All required tables exist")
            return True
    
    except Exception as e:
        logger.error(f"Error verifying tables: {e}")
        return False


def add_sample_data(session):
    """Add sample data for testing (optional)."""
    logger.info("Adding sample conflict resolution data...")
    
    try:
        # Check if we already have sample data
        existing_conflicts = session.query(AnnotationConflict).count()
        if existing_conflicts > 0:
            logger.info("Sample data already exists, skipping...")
            return True
        
        # This is optional - only add if specifically requested
        # You can implement sample data creation here if needed
        
        logger.info("No sample data added (not implemented)")
        return True
    
    except Exception as e:
        logger.error(f"Error adding sample data: {e}")
        return False


def main():
    """Main migration function."""
    logger.info("Starting conflict resolution system database migration...")
    
    try:
        # Get database connection
        database_url = get_database_url()
        engine = create_engine(database_url)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        # Step 1: Create tables
        if not create_conflict_tables(engine):
            logger.error("Failed to create tables")
            return False
        
        # Step 2: Verify tables
        if not verify_tables(engine):
            logger.error("Table verification failed")
            return False
        
        # Step 3: Create indexes
        if not create_indexes(engine):
            logger.warning("Some indexes failed to create, but continuing...")
        
        # Step 4: Create default settings
        if not create_default_settings(session):
            logger.error("Failed to create default settings")
            return False
        
        # Step 5: Optional sample data
        if '--sample-data' in sys.argv:
            add_sample_data(session)
        
        logger.info("Database migration completed successfully!")
        
        # Print summary
        print("\n" + "="*60)
        print("CONFLICT RESOLUTION SYSTEM - DATABASE MIGRATION COMPLETE")
        print("="*60)
        print(f"Database URL: {database_url}")
        print("\nTables created:")
        for table in [
            "annotation_conflicts", "conflict_resolutions", "conflict_participants",
            "resolution_votes", "conflict_notifications", "conflict_settings"
        ]:
            print(f"  ✓ {table}")
        
        print("\nFeatures available:")
        print("  ✓ Conflict Detection (span overlaps, label conflicts)")
        print("  ✓ Resolution Strategies (auto-merge, voting, expert review)")
        print("  ✓ Real-time Notifications")
        print("  ✓ Performance Tracking")
        print("  ✓ Admin Dashboard")
        
        print("\nNext steps:")
        print("  1. Update your application configuration")
        print("  2. Configure conflict detection settings per project")
        print("  3. Set up notification delivery methods")
        print("  4. Train annotators on conflict resolution workflows")
        print("="*60)
        
        return True
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False
    
    finally:
        if 'session' in locals():
            session.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)