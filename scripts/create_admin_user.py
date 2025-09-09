#!/usr/bin/env python3
"""
Create Admin User Script

Script to create the first admin user for the text annotation system.
Run this script after setting up the database to create your first administrator.
"""

import sys
import os
import asyncio
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.user import User
from src.core.security import get_password_hash
from src.core.config import settings
from src.core.database import Base


def create_admin_user():
    """Create the first admin user interactively."""
    
    print("=" * 60)
    print("Text Annotation System - Admin User Creation")
    print("=" * 60)
    print()
    
    # Get user input
    username = input("Enter admin username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return False
    
    email = input("Enter admin email: ").strip()
    if not email:
        print("Error: Email cannot be empty.")
        return False
    
    full_name = input("Enter full name (optional): ").strip()
    institution = input("Enter institution (optional): ").strip()
    
    # Get password securely
    password = getpass("Enter admin password: ")
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        return False
    
    password_confirm = getpass("Confirm admin password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        return False
    
    print()
    print(f"Creating admin user '{username}' with email '{email}'...")
    
    try:
        # Create database engine and session
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if user already exists
        existing_user = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print(f"Error: User with username '{username}' or email '{email}' already exists.")
            session.close()
            return False
        
        # Create admin user
        admin_user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name if full_name else None,
            institution=institution if institution else None,
            role="super_admin",
            is_active=True,
            is_verified=True,
            is_admin=True
        )
        
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        print()
        print("✅ Admin user created successfully!")
        print(f"   ID: {admin_user.id}")
        print(f"   Username: {admin_user.username}")
        print(f"   Email: {admin_user.email}")
        print(f"   Role: {admin_user.role}")
        print()
        print("You can now log in to the system using these credentials.")
        print("Access the admin interface at: http://localhost:8000/api/docs")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        return False


def check_existing_admins():
    """Check if there are existing admin users."""
    
    try:
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        admin_count = session.query(User).filter(User.is_admin == True).count()
        
        if admin_count > 0:
            print(f"Warning: There are already {admin_count} admin user(s) in the system.")
            response = input("Do you want to create another admin user? (y/N): ").strip().lower()
            
            if response not in ['y', 'yes']:
                print("Admin user creation cancelled.")
                session.close()
                return False
        
        session.close()
        return True
        
    except Exception as e:
        print(f"Error checking existing admins: {str(e)}")
        return False


def main():
    """Main function."""
    
    try:
        # Check database connection
        print("Checking database connection...")
        engine = create_engine(settings.DATABASE_URL)
        engine.execute("SELECT 1")
        print("✅ Database connection successful.")
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        print()
        print("Please ensure:")
        print("1. Database server is running")
        print("2. DATABASE_URL in .env is correct")
        print("3. Database exists and is accessible")
        return
    
    print()
    
    # Check for existing admins
    if not check_existing_admins():
        return
    
    print()
    
    # Create admin user
    if create_admin_user():
        print("Admin user creation completed successfully!")
    else:
        print("Admin user creation failed.")


if __name__ == "__main__":
    main()