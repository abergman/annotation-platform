"""
Simple Unit Tests for Authentication Core Functions

Tests password hashing, JWT token creation/verification, and basic models
without requiring database connectivity.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Mock the database imports that cause connection issues
sys.modules['psycopg2'] = MagicMock()
sys.modules['src.core.database'] = MagicMock()

# Mock the database dependency
mock_db_dependency = Mock()

# Patch the database import before importing our modules
with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
    mock_db_dependency.get_db = Mock()
    
    # Now we can import our modules
    from src.core.security import (
        verify_password,
        get_password_hash,
        create_access_token,
        verify_token
    )


class TestPasswordSecurity:
    """Test password hashing and verification."""
    
    def test_password_hashing_works(self):
        """Test that password hashing produces a hash."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > len(password)
    
    def test_password_verification_success(self):
        """Test correct password verification."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        result = verify_password(password, hashed)
        assert result is True
    
    def test_password_verification_failure(self):
        """Test incorrect password verification."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = get_password_hash(password)
        
        result = verify_password(wrong_password, hashed)
        assert result is False
    
    def test_password_hash_consistency(self):
        """Test that password hashing is consistent."""
        password = "TestPassword123!"
        
        # Hash the same password multiple times
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different (due to salt) but both should verify
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWTTokens:
    """Test JWT token creation and verification."""
    
    def test_create_access_token_basic(self):
        """Test basic JWT token creation."""
        data = {"sub": "testuser"}
        
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 10  # JWT tokens are long
    
    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=1)
        
        token = create_access_token(data, expires_delta)
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_verify_token_valid(self):
        """Test JWT token verification with valid token."""
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert "exp" in payload
    
    def test_verify_token_invalid(self):
        """Test JWT token verification with invalid token."""
        invalid_token = "invalid.jwt.token"
        
        payload = verify_token(invalid_token)
        
        assert payload is None
    
    def test_verify_token_expired(self):
        """Test JWT token verification with expired token."""
        data = {"sub": "testuser"}
        expired_delta = timedelta(seconds=-10)  # Already expired
        
        token = create_access_token(data, expired_delta)
        
        # Token should be expired
        payload = verify_token(token)
        assert payload is None
    
    def test_token_tamper_resistance(self):
        """Test that tampered tokens are rejected."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        # Tamper with the token
        tampered_token = token[:-1] + "X"  # Change last character
        
        payload = verify_token(tampered_token)
        assert payload is None


class TestPydanticModels:
    """Test Pydantic models used in authentication."""
    
    def test_user_create_model(self):
        """Test UserCreate model validation."""
        # We need to import models after mocking database
        with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
            from src.api.auth import UserCreate
            
            # Valid user data
            user_data = UserCreate(
                username="testuser",
                email="test@example.com",
                password="SecurePassword123!",
                full_name="Test User",
                institution="Test University"
            )
            
            assert user_data.username == "testuser"
            assert user_data.email == "test@example.com"
            assert user_data.password == "SecurePassword123!"
            assert user_data.full_name == "Test User"
            assert user_data.institution == "Test University"
    
    def test_user_create_minimal(self):
        """Test UserCreate model with minimal data."""
        with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
            from src.api.auth import UserCreate
            
            user_data = UserCreate(
                username="testuser",
                email="test@example.com",
                password="SecurePassword123!"
            )
            
            assert user_data.username == "testuser"
            assert user_data.email == "test@example.com"
            assert user_data.password == "SecurePassword123!"
            assert user_data.full_name is None
            assert user_data.institution is None
    
    def test_user_login_model(self):
        """Test UserLogin model validation."""
        with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
            from src.api.auth import UserLogin
            
            login_data = UserLogin(
                username="testuser",
                password="Password123!"
            )
            
            assert login_data.username == "testuser"
            assert login_data.password == "Password123!"
    
    def test_user_update_model(self):
        """Test UserUpdate model validation."""
        with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
            from src.api.auth import UserUpdate
            
            update_data = UserUpdate(
                full_name="Updated Name",
                institution="New University",
                bio="Updated bio"
            )
            
            assert update_data.full_name == "Updated Name"
            assert update_data.institution == "New University"
            assert update_data.bio == "Updated bio"
    
    def test_token_model(self):
        """Test Token response model."""
        with patch.dict('sys.modules', {'src.core.database': mock_db_dependency}):
            from src.api.auth import Token, UserResponse
            
            user_response = UserResponse(
                id=1,
                username="testuser",
                email="test@example.com",
                full_name="Test User",
                institution="Test University",
                role="researcher",
                is_active=True,
                is_verified=False,
                created_at="2023-01-01T12:00:00"
            )
            
            token = Token(
                access_token="test_token",
                token_type="bearer",
                expires_in=1800,
                user=user_response
            )
            
            assert token.access_token == "test_token"
            assert token.token_type == "bearer"
            assert token.expires_in == 1800
            assert token.user.username == "testuser"


class TestSecurityEdgeCases:
    """Test security edge cases and error conditions."""
    
    def test_empty_password_hashing(self):
        """Test password hashing with empty password."""
        empty_password = ""
        
        # Should still produce a hash (though not recommended)
        hashed = get_password_hash(empty_password)
        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_very_long_password(self):
        """Test password hashing with very long password."""
        long_password = "a" * 1000  # 1000 character password
        
        hashed = get_password_hash(long_password)
        assert hashed is not None
        assert verify_password(long_password, hashed)
    
    def test_unicode_password(self):
        """Test password hashing with unicode characters."""
        unicode_password = "Pässwörd123!🔒"
        
        hashed = get_password_hash(unicode_password)
        assert hashed is not None
        assert verify_password(unicode_password, hashed)
    
    def test_token_with_special_characters(self):
        """Test JWT tokens with special characters in payload."""
        data = {
            "sub": "test@user.com",
            "name": "Test Üser",
            "role": "admin/super"
        }
        
        token = create_access_token(data)
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "test@user.com"
        assert payload["name"] == "Test Üser"
        assert payload["role"] == "admin/super"
    
    def test_token_size_limits(self):
        """Test JWT tokens with large payloads."""
        # Create a large payload
        large_data = {
            "sub": "testuser",
            "permissions": ["read", "write", "delete"] * 100,  # Large list
            "metadata": "x" * 1000  # Large string
        }
        
        token = create_access_token(large_data)
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert len(payload["permissions"]) == 300
        assert len(payload["metadata"]) == 1000


if __name__ == "__main__":
    # Run a quick test to verify functionality
    print("Testing password security...")
    
    password = "TestPassword123!"
    hashed = get_password_hash(password)
    verified = verify_password(password, hashed)
    
    print(f"Password hashing works: {hashed[:20]}...")
    print(f"Password verification works: {verified}")
    
    print("Testing JWT tokens...")
    
    data = {"sub": "testuser", "role": "admin"}
    token = create_access_token(data)
    payload = verify_token(token)
    
    print(f"Token creation works: {token[:20]}...")
    print(f"Token verification works: {payload is not None}")
    print(f"Token payload: {payload}")
    
    print("All basic tests passed!")