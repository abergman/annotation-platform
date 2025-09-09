"""
Unit Tests for Security Module

Tests authentication, password hashing, JWT tokens, and security dependencies.
"""

import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from unittest.mock import Mock, patch

from src.core.security import (
    verify_password, get_password_hash, create_access_token, verify_token,
    get_current_user, get_current_active_admin
)


class TestPasswordHandling:
    """Test cases for password hashing and verification."""

    @pytest.mark.unit
    @pytest.mark.security
    def test_password_hashing(self):
        """Test password hashing functionality."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed.startswith("$2b$")  # Bcrypt prefix

    @pytest.mark.unit
    @pytest.mark.security
    def test_password_verification(self):
        """Test password verification."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        # Correct password should verify
        assert verify_password(password, hashed) is True
        
        # Wrong password should not verify
        assert verify_password("WrongPassword", hashed) is False
        assert verify_password("", hashed) is False

    @pytest.mark.unit
    @pytest.mark.security
    def test_password_case_sensitivity(self):
        """Test password case sensitivity."""
        password = "CaseSensitive123"
        hashed = get_password_hash(password)
        
        assert verify_password("CaseSensitive123", hashed) is True
        assert verify_password("casesensitive123", hashed) is False
        assert verify_password("CASESENSITIVE123", hashed) is False

    @pytest.mark.unit
    @pytest.mark.security
    def test_empty_password_handling(self):
        """Test handling of empty passwords."""
        empty_password = ""
        hashed = get_password_hash(empty_password)
        
        assert verify_password("", hashed) is True
        assert verify_password("anything", hashed) is False

    @pytest.mark.unit
    @pytest.mark.security
    def test_unicode_password_handling(self):
        """Test handling of Unicode passwords."""
        unicode_password = "测试密码123🔒"
        hashed = get_password_hash(unicode_password)
        
        assert verify_password(unicode_password, hashed) is True
        assert verify_password("测试密码123", hashed) is False


class TestJWTTokens:
    """Test cases for JWT token creation and verification."""

    @pytest.mark.unit
    @pytest.mark.security
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "testuser", "role": "student"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are reasonably long
        assert token.count('.') == 2  # JWT has 3 parts separated by dots

    @pytest.mark.unit
    @pytest.mark.security
    def test_verify_valid_token(self):
        """Test verification of valid JWT token."""
        data = {"sub": "testuser", "role": "student"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "student"
        assert "exp" in payload  # Expiration should be added

    @pytest.mark.unit
    @pytest.mark.security
    def test_verify_invalid_token(self):
        """Test verification of invalid JWT token."""
        invalid_tokens = [
            "invalid.token.here",
            "not-a-jwt-token",
            "",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature"
        ]
        
        for token in invalid_tokens:
            payload = verify_token(token)
            assert payload is None

    @pytest.mark.unit
    @pytest.mark.security
    def test_token_expiration(self):
        """Test token expiration handling."""
        # Create token that expires immediately
        data = {"sub": "testuser"}
        expired_delta = timedelta(seconds=-1)  # Already expired
        
        with patch('src.core.security.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            token = create_access_token(data, expired_delta)
        
        # Token should be invalid when verified
        payload = verify_token(token)
        assert payload is None

    @pytest.mark.unit
    @pytest.mark.security
    def test_token_custom_expiration(self):
        """Test token with custom expiration time."""
        data = {"sub": "testuser"}
        custom_delta = timedelta(hours=24)
        
        token = create_access_token(data, custom_delta)
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "testuser"

    @pytest.mark.unit
    @pytest.mark.security
    def test_token_subject_integer(self):
        """Test token creation with integer subject (user ID)."""
        data = {"sub": 12345}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == 12345


class TestAuthenticationDependencies:
    """Test cases for FastAPI authentication dependencies."""

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_user_valid_token(self, test_db, test_user):
        """Test getting current user with valid token."""
        # Create token for test user
        token_data = {"sub": test_user.username}
        token = create_access_token(token_data)
        
        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        user = get_current_user(mock_credentials, test_db)
        assert user.id == test_user.id
        assert user.username == test_user.username

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_user_invalid_token(self, test_db):
        """Test getting current user with invalid token."""
        mock_credentials = Mock()
        mock_credentials.credentials = "invalid-token"
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_credentials, test_db)
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_user_nonexistent_user(self, test_db):
        """Test getting current user for non-existent user."""
        # Create token for non-existent user
        token_data = {"sub": "nonexistent_user"}
        token = create_access_token(token_data)
        
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_credentials, test_db)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_user_inactive_user(self, test_db, test_user):
        """Test getting current user when user is inactive."""
        # Deactivate user
        test_user.is_active = False
        test_db.commit()
        
        # Create token for inactive user
        token_data = {"sub": test_user.username}
        token = create_access_token(token_data)
        
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_credentials, test_db)
        
        assert exc_info.value.status_code == 401
        assert "User account is inactive" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_user_token_without_subject(self, test_db):
        """Test getting current user with token missing subject."""
        # Create token without subject
        token_data = {"role": "user"}  # No 'sub' field
        token = create_access_token(token_data)
        
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_credentials, test_db)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_active_admin_valid_admin(self, test_admin_user):
        """Test getting current admin user."""
        admin = get_current_active_admin(test_admin_user)
        assert admin.id == test_admin_user.id
        assert admin.is_admin is True

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_active_admin_non_admin(self, test_user):
        """Test getting current admin with non-admin user."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_active_admin(test_user)
        
        assert exc_info.value.status_code == 403
        assert "Not enough permissions" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_current_active_admin_inactive_admin(self, test_admin_user):
        """Test getting current admin when admin is inactive."""
        # This should still work since get_current_user handles inactive users
        # The admin check only verifies admin permissions
        admin = get_current_active_admin(test_admin_user)
        assert admin.is_admin is True


class TestSecurityEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    @pytest.mark.security
    def test_very_long_password(self):
        """Test handling of very long passwords."""
        long_password = "a" * 1000
        hashed = get_password_hash(long_password)
        
        assert verify_password(long_password, hashed) is True
        assert verify_password(long_password[:-1], hashed) is False

    @pytest.mark.unit
    @pytest.mark.security
    def test_special_characters_password(self):
        """Test passwords with special characters."""
        special_password = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        hashed = get_password_hash(special_password)
        
        assert verify_password(special_password, hashed) is True

    @pytest.mark.unit
    @pytest.mark.security
    def test_token_with_extra_claims(self):
        """Test token with additional custom claims."""
        data = {
            "sub": "testuser",
            "role": "admin",
            "permissions": ["read", "write", "delete"],
            "department": "research"
        }
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write", "delete"]
        assert payload["department"] == "research"

    @pytest.mark.unit
    @pytest.mark.security
    def test_malformed_token_parts(self):
        """Test handling of malformed tokens."""
        malformed_tokens = [
            "header.payload",  # Missing signature
            "header.payload.signature.extra",  # Too many parts
            "header.",  # Missing payload
            ".payload.signature",  # Missing header
            "header..signature",  # Empty payload
        ]
        
        for token in malformed_tokens:
            payload = verify_token(token)
            assert payload is None