"""
Unit Tests for User Model

Tests the User model functionality including validation, relationships, and methods.
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.models.user import User
from src.core.security import get_password_hash, verify_password


class TestUserModel:
    """Test cases for User model."""

    @pytest.mark.unit
    def test_create_user(self, test_db):
        """Test creating a new user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Test User"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.role == "researcher"  # Default value
        assert user.is_active is True  # Default value
        assert user.is_verified is False  # Default value
        assert user.is_admin is False  # Default value
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)

    @pytest.mark.unit
    def test_user_unique_constraints(self, test_db):
        """Test unique constraints on username and email."""
        # Create first user
        user1 = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user1)
        test_db.commit()

        # Try to create user with same username
        user2 = User(
            username="testuser",
            email="test2@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
        
        test_db.rollback()

        # Try to create user with same email
        user3 = User(
            username="testuser2",
            email="test@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user3)
        
        with pytest.raises(IntegrityError):
            test_db.commit()

    @pytest.mark.unit
    def test_user_password_hashing(self):
        """Test password hashing functionality."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    @pytest.mark.unit
    def test_user_to_dict(self, test_user):
        """Test user to_dict method."""
        user_dict = test_user.to_dict()
        
        required_fields = [
            "id", "username", "email", "full_name", "institution", 
            "role", "bio", "is_active", "is_verified", "created_at"
        ]
        
        for field in required_fields:
            assert field in user_dict
        
        # Ensure sensitive data is not included
        assert "hashed_password" not in user_dict
        
        # Check data types
        assert isinstance(user_dict["id"], int)
        assert isinstance(user_dict["is_active"], bool)

    @pytest.mark.unit
    def test_user_repr(self, test_user):
        """Test user string representation."""
        repr_str = repr(test_user)
        assert "User" in repr_str
        assert str(test_user.id) in repr_str
        assert test_user.username in repr_str
        assert test_user.email in repr_str

    @pytest.mark.unit
    def test_user_optional_fields(self, test_db):
        """Test user with optional fields."""
        user = User(
            username="researcher",
            email="researcher@university.edu",
            hashed_password=get_password_hash("password123"),
            full_name="Dr. Jane Smith",
            institution="University of Science",
            role="professor",
            bio="Researcher in computational linguistics"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.institution == "University of Science"
        assert user.role == "professor"
        assert user.bio == "Researcher in computational linguistics"

    @pytest.mark.unit
    def test_user_timestamps(self, test_db):
        """Test user timestamp functionality."""
        user = User(
            username="timetest",
            email="time@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        created_at = user.created_at
        updated_at = user.updated_at

        # Update user
        user.full_name = "Updated Name"
        test_db.commit()
        test_db.refresh(user)

        assert user.created_at == created_at  # Should not change
        assert user.updated_at > updated_at  # Should be updated

    @pytest.mark.unit
    def test_user_default_values(self, test_db):
        """Test default values for user fields."""
        user = User(
            username="defaultuser",
            email="default@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()

        assert user.role == "researcher"
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_admin is False
        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.unit
    def test_user_admin_flag(self, test_db):
        """Test admin user functionality."""
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass123"),
            is_admin=True
        )
        test_db.add(admin_user)
        test_db.commit()

        assert admin_user.is_admin is True

    @pytest.mark.unit
    def test_user_validation_states(self, test_db):
        """Test user verification states."""
        user = User(
            username="unverified",
            email="unverified@example.com",
            hashed_password=get_password_hash("password123"),
            is_verified=False
        )
        test_db.add(user)
        test_db.commit()

        assert user.is_verified is False
        
        # Verify user
        user.is_verified = True
        test_db.commit()
        test_db.refresh(user)
        
        assert user.is_verified is True

    @pytest.mark.unit
    def test_user_last_login_tracking(self, test_db):
        """Test last login timestamp tracking."""
        user = User(
            username="logintest",
            email="login@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.last_login is None

        # Simulate login
        login_time = datetime.utcnow()
        user.last_login = login_time
        test_db.commit()
        test_db.refresh(user)

        assert user.last_login == login_time

    @pytest.mark.unit
    def test_user_active_status(self, test_db):
        """Test user active/inactive status."""
        user = User(
            username="activetest",
            email="active@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()

        assert user.is_active is True

        # Deactivate user
        user.is_active = False
        test_db.commit()
        test_db.refresh(user)

        assert user.is_active is False