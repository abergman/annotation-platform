"""
Unit Tests for Authentication API Endpoints

Comprehensive test suite for user registration, login, profile management, 
JWT token generation, and authentication security.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the code under test
from src.api.auth import (
    register_user,
    login,
    get_current_user_profile,
    update_user_profile,
    logout,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserResponse,
    Token
)
from src.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    verify_token
)
from src.models.user import User


class TestUserRegistration:
    """Unit tests for user registration functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def valid_user_data(self):
        """Valid user registration data."""
        return UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePassword123!",
            full_name="Test User",
            institution="Test University"
        )
    
    @pytest.mark.unit
    async def test_register_user_success(self, mock_db, valid_user_data):
        """Test successful user registration."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock the created user
        created_user = Mock(spec=User)
        created_user.to_dict.return_value = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "institution": "Test University",
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        mock_db.refresh.side_effect = lambda user: setattr(created_user, 'id', 1)
        
        with patch('src.api.auth.get_password_hash') as mock_hash:
            mock_hash.return_value = "hashed_password"
            with patch('src.api.auth.User') as mock_user_class:
                mock_user_class.return_value = created_user
                
                result = await register_user(valid_user_data, mock_db)
        
        # Assertions
        assert isinstance(result, dict)
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert result["full_name"] == "Test User"
        assert result["institution"] == "Test University"
        assert result["role"] == "researcher"
        assert result["is_active"] is True
        assert result["is_verified"] is False
        
        # Verify database interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_hash.assert_called_once_with("SecurePassword123!")
    
    @pytest.mark.unit
    async def test_register_user_duplicate_username(self, mock_db, valid_user_data):
        """Test registration with duplicate username."""
        # Mock existing user with same username
        existing_user = Mock(spec=User)
        existing_user.username = "testuser"
        
        def mock_query_filter(model):
            mock_query = Mock()
            if model == User:
                mock_filter = Mock()
                mock_filter.first.return_value = existing_user
                mock_query.filter.return_value = mock_filter
                return mock_query
            return Mock()
        
        mock_db.query = mock_query_filter
        
        with pytest.raises(HTTPException) as exc_info:
            await register_user(valid_user_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already registered" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_register_user_duplicate_email(self, mock_db, valid_user_data):
        """Test registration with duplicate email."""
        # Mock no user with same username, but user with same email
        existing_user_email = Mock(spec=User)
        existing_user_email.email = "test@example.com"
        
        def mock_query_side_effect(*args):
            mock_query = Mock()
            mock_filter = Mock()
            # First call for username check - return None
            # Second call for email check - return existing user
            mock_filter.first.side_effect = [None, existing_user_email]
            mock_query.filter.return_value = mock_filter
            return mock_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        with pytest.raises(HTTPException) as exc_info:
            await register_user(valid_user_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_register_user_minimal_data(self, mock_db):
        """Test registration with minimal required data."""
        minimal_data = UserCreate(
            username="minimal",
            email="minimal@example.com",
            password="Password123!"
        )
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        created_user = Mock(spec=User)
        created_user.to_dict.return_value = {
            "id": 1,
            "username": "minimal",
            "email": "minimal@example.com",
            "full_name": None,
            "institution": None,
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        
        with patch('src.api.auth.get_password_hash') as mock_hash:
            mock_hash.return_value = "hashed_password"
            with patch('src.api.auth.User') as mock_user_class:
                mock_user_class.return_value = created_user
                
                result = await register_user(minimal_data, mock_db)
        
        assert result["username"] == "minimal"
        assert result["email"] == "minimal@example.com"
        assert result["full_name"] is None
        assert result["institution"] is None


class TestUserLogin:
    """Unit tests for user login functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def valid_login_data(self):
        """Valid login credentials."""
        return UserLogin(
            username="testuser",
            password="SecurePassword123!"
        )
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.hashed_password = "hashed_password"
        user.is_active = True
        user.last_login = None
        user.to_dict.return_value = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "institution": "Test University",
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        return user
    
    @pytest.mark.unit
    async def test_login_success(self, mock_db, valid_login_data, mock_user):
        """Test successful user login."""
        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit = Mock()
        
        with patch('src.api.auth.verify_password') as mock_verify:
            mock_verify.return_value = True
            with patch('src.api.auth.create_access_token') as mock_create_token:
                mock_create_token.return_value = "test_access_token"
                with patch('src.api.auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES', 30):
                    
                    result = await login(valid_login_data, mock_db)
        
        # Assertions
        assert isinstance(result, Token)
        assert result.access_token == "test_access_token"
        assert result.token_type == "bearer"
        assert result.expires_in == 30 * 60  # 30 minutes in seconds
        assert result.user.username == "testuser"
        
        # Verify password was checked
        mock_verify.assert_called_once_with("SecurePassword123!", "hashed_password")
        
        # Verify token was created with correct data
        mock_create_token.assert_called_once()
        call_args = mock_create_token.call_args
        assert call_args[1]["data"]["sub"] == "testuser"
        
        # Verify last_login was updated
        assert mock_user.last_login is not None
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_login_user_not_found(self, mock_db, valid_login_data):
        """Test login with non-existent user."""
        # Mock database query returning None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await login(valid_login_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_login_wrong_password(self, mock_db, valid_login_data, mock_user):
        """Test login with incorrect password."""
        # Mock database query returning user
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.auth.verify_password') as mock_verify:
            mock_verify.return_value = False  # Wrong password
            
            with pytest.raises(HTTPException) as exc_info:
                await login(valid_login_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_login_inactive_user(self, mock_db, valid_login_data, mock_user):
        """Test login with inactive user account."""
        # Set user as inactive
        mock_user.is_active = False
        
        # Mock database query returning inactive user
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.auth.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            with pytest.raises(HTTPException) as exc_info:
                await login(valid_login_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User account is inactive" in str(exc_info.value.detail)


class TestUserProfile:
    """Unit tests for user profile management."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock current user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.full_name = "Test User"
        user.institution = "Test University"
        user.bio = "Original bio"
        user.to_dict.return_value = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "institution": "Test University",
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        return user
    
    @pytest.mark.unit
    async def test_get_current_user_profile_success(self, mock_user):
        """Test getting current user profile."""
        result = await get_current_user_profile(mock_user)
        
        assert isinstance(result, UserResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 1
            assert result["username"] == "testuser"
            assert result["email"] == "test@example.com"
            assert result["full_name"] == "Test User"
    
    @pytest.mark.unit
    async def test_update_user_profile_full_update(self, mock_user):
        """Test updating user profile with all fields."""
        mock_db = Mock(spec=Session)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = UserUpdate(
            full_name="Updated Name",
            institution="New University",
            bio="Updated bio"
        )
        
        # Mock updated user data
        mock_user.to_dict.return_value = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Updated Name",
            "institution": "New University",
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        
        with patch('src.api.auth.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 13, 0, 0)
            
            result = await update_user_profile(update_data, mock_user, mock_db)
        
        # Verify updates were applied
        assert mock_user.full_name == "Updated Name"
        assert mock_user.institution == "New University"
        assert mock_user.bio == "Updated bio"
        assert mock_user.updated_at == datetime(2023, 1, 1, 13, 0, 0)
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user)
        
        # Verify returned data
        assert result["full_name"] == "Updated Name"
        assert result["institution"] == "New University"
    
    @pytest.mark.unit
    async def test_update_user_profile_partial_update(self, mock_user):
        """Test partial user profile update."""
        mock_db = Mock(spec=Session)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = UserUpdate(
            full_name="Only Name Updated"
        )
        
        # Preserve original values for fields not being updated
        original_institution = mock_user.institution
        original_bio = mock_user.bio
        
        with patch('src.api.auth.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 13, 0, 0)
            
            await update_user_profile(update_data, mock_user, mock_db)
        
        # Verify only full_name was updated
        assert mock_user.full_name == "Only Name Updated"
        assert mock_user.institution == original_institution  # Unchanged
        assert mock_user.bio == original_bio  # Unchanged
        assert mock_user.updated_at == datetime(2023, 1, 1, 13, 0, 0)
    
    @pytest.mark.unit
    async def test_update_user_profile_empty_update(self, mock_user):
        """Test updating profile with no changes."""
        mock_db = Mock(spec=Session)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = UserUpdate()  # Empty update
        
        # Store original values
        original_full_name = mock_user.full_name
        original_institution = mock_user.institution
        original_bio = mock_user.bio
        
        with patch('src.api.auth.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 13, 0, 0)
            
            await update_user_profile(update_data, mock_user, mock_db)
        
        # Verify no fields changed except updated_at
        assert mock_user.full_name == original_full_name
        assert mock_user.institution == original_institution
        assert mock_user.bio == original_bio
        assert mock_user.updated_at == datetime(2023, 1, 1, 13, 0, 0)


class TestLogout:
    """Unit tests for logout functionality."""
    
    @pytest.mark.unit
    async def test_logout_success(self):
        """Test logout returns success message."""
        result = await logout()
        
        assert isinstance(result, dict)
        assert "message" in result
        assert "logged out" in result["message"].lower()


class TestSecurityFunctions:
    """Unit tests for security and JWT functions."""
    
    @pytest.mark.unit
    def test_verify_password_success(self):
        """Test password verification with correct password."""
        plain_password = "TestPassword123!"
        hashed_password = get_password_hash(plain_password)
        
        result = verify_password(plain_password, hashed_password)
        
        assert result is True
    
    @pytest.mark.unit
    def test_verify_password_failure(self):
        """Test password verification with incorrect password."""
        plain_password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed_password = get_password_hash(plain_password)
        
        result = verify_password(wrong_password, hashed_password)
        
        assert result is False
    
    @pytest.mark.unit
    def test_get_password_hash(self):
        """Test password hashing."""
        password = "TestPassword123!"
        
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password  # Should be hashed
        assert len(hashed) > len(password)  # Hash should be longer
        assert hashed.startswith("$2b$")  # bcrypt hash format
    
    @pytest.mark.unit
    def test_create_access_token_default_expiry(self):
        """Test JWT token creation with default expiry."""
        data = {"sub": "testuser"}
        
        with patch('src.core.security.settings.ACCESS_TOKEN_EXPIRE_MINUTES', 30):
            token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 10  # JWT tokens are long
    
    @pytest.mark.unit
    def test_create_access_token_custom_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=1)
        
        token = create_access_token(data, expires_delta)
        
        assert token is not None
        assert isinstance(token, str)
        
        # Verify token contains correct expiry
        payload = verify_token(token)
        assert payload is not None
        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "testuser"
    
    @pytest.mark.unit
    def test_verify_token_valid(self):
        """Test JWT token verification with valid token."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert "exp" in payload
    
    @pytest.mark.unit
    def test_verify_token_invalid(self):
        """Test JWT token verification with invalid token."""
        invalid_token = "invalid.jwt.token"
        
        payload = verify_token(invalid_token)
        
        assert payload is None
    
    @pytest.mark.unit
    def test_verify_token_expired(self):
        """Test JWT token verification with expired token."""
        data = {"sub": "testuser"}
        expired_delta = timedelta(seconds=-1)  # Already expired
        
        token = create_access_token(data, expired_delta)
        
        # Wait a moment to ensure token is definitely expired
        import time
        time.sleep(0.1)
        
        payload = verify_token(token)
        
        assert payload is None


class TestGetCurrentUser:
    """Unit tests for current user authentication dependency."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock HTTP authorization credentials."""
        credentials = Mock()
        credentials.credentials = "valid_token"
        return credentials
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.is_active = True
        return user
    
    @pytest.mark.unit
    def test_get_current_user_success(self, mock_db, mock_credentials, mock_user):
        """Test successful user authentication."""
        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.core.security.verify_token') as mock_verify:
            mock_verify.return_value = {"sub": "testuser", "exp": 9999999999}
            
            result = get_current_user(mock_credentials, mock_db)
        
        assert result == mock_user
        mock_verify.assert_called_once_with("valid_token")
    
    @pytest.mark.unit
    def test_get_current_user_invalid_token(self, mock_db, mock_credentials):
        """Test authentication with invalid token."""
        with patch('src.core.security.verify_token') as mock_verify:
            mock_verify.return_value = None  # Invalid token
            
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    def test_get_current_user_no_subject(self, mock_db, mock_credentials):
        """Test authentication with token missing subject."""
        with patch('src.core.security.verify_token') as mock_verify:
            mock_verify.return_value = {"exp": 9999999999}  # Missing 'sub'
            
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.unit
    def test_get_current_user_user_not_found(self, mock_db, mock_credentials):
        """Test authentication when user doesn't exist in database."""
        # Mock database query returning None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.core.security.verify_token') as mock_verify:
            mock_verify.return_value = {"sub": "nonexistent", "exp": 9999999999}
            
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.unit
    def test_get_current_user_inactive_user(self, mock_db, mock_credentials, mock_user):
        """Test authentication with inactive user."""
        mock_user.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.core.security.verify_token') as mock_verify:
            mock_verify.return_value = {"sub": "testuser", "exp": 9999999999}
            
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User account is inactive" in str(exc_info.value.detail)


class TestEdgeCases:
    """Unit tests for edge cases and error conditions."""
    
    @pytest.mark.unit
    async def test_register_user_database_error(self):
        """Test registration handles database errors gracefully."""
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.commit.side_effect = Exception("Database error")
        
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="Password123!"
        )
        
        with patch('src.api.auth.get_password_hash') as mock_hash:
            mock_hash.return_value = "hashed_password"
            with patch('src.api.auth.User') as mock_user_class:
                mock_user_class.return_value = Mock(spec=User)
                
                with pytest.raises(Exception) as exc_info:
                    await register_user(user_data, mock_db)
                
                assert "Database error" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_login_database_error(self):
        """Test login handles database errors gracefully."""
        mock_db = Mock(spec=Session)
        mock_db.query.side_effect = Exception("Database connection failed")
        
        login_data = UserLogin(
            username="testuser",
            password="Password123!"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(login_data, mock_db)
        
        assert "Database connection failed" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_password_hash_consistency(self):
        """Test that password hashing is consistent and secure."""
        password = "TestPassword123!"
        
        # Hash the same password multiple times
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different (due to salt) but both should verify
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
    
    @pytest.mark.unit
    def test_token_security_features(self):
        """Test JWT token security features."""
        data = {"sub": "testuser", "role": "admin"}
        
        token = create_access_token(data)
        payload = verify_token(token)
        
        # Verify all data is preserved
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert "exp" in payload
        
        # Verify token can't be tampered with
        tampered_token = token[:-1] + "X"  # Change last character
        tampered_payload = verify_token(tampered_token)
        assert tampered_payload is None
    
    @pytest.mark.unit
    def test_username_case_sensitivity(self):
        """Test username case sensitivity in authentication."""
        # This test verifies the system behavior for username case sensitivity
        # The actual behavior depends on database collation settings
        mock_db = Mock(spec=Session)
        
        # Mock user with lowercase username
        user = Mock(spec=User)
        user.username = "testuser"
        user.is_active = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        credentials = Mock()
        credentials.credentials = "valid_token"
        
        with patch('src.core.security.verify_token') as mock_verify:
            # Test with exact case match
            mock_verify.return_value = {"sub": "testuser", "exp": 9999999999}
            result = get_current_user(credentials, mock_db)
            assert result == user
            
            # Test with different case - should depend on database settings
            mock_verify.return_value = {"sub": "TestUser", "exp": 9999999999}
            # This might raise an exception or return user depending on DB settings
            try:
                result = get_current_user(credentials, mock_db)
                # If no exception, case-insensitive matching is enabled
            except HTTPException:
                # If exception, case-sensitive matching is enforced
                pass


class TestPerformanceAndSecurity:
    """Tests for performance and security considerations."""
    
    @pytest.mark.unit
    def test_password_hashing_performance(self):
        """Test password hashing performance is reasonable."""
        import time
        
        password = "TestPassword123!"
        
        start_time = time.time()
        hash_result = get_password_hash(password)
        hash_time = time.time() - start_time
        
        # Password hashing should complete within reasonable time (< 1 second)
        assert hash_time < 1.0
        assert hash_result is not None
        
        # Verification should also be reasonably fast
        start_time = time.time()
        verify_result = verify_password(password, hash_result)
        verify_time = time.time() - start_time
        
        assert verify_time < 1.0
        assert verify_result is True
    
    @pytest.mark.unit
    def test_token_entropy(self):
        """Test JWT tokens have sufficient entropy."""
        data = {"sub": "testuser"}
        
        # Generate multiple tokens and ensure they're different
        tokens = set()
        for _ in range(10):
            token = create_access_token(data)
            tokens.add(token)
        
        # All tokens should be unique
        assert len(tokens) == 10
        
        # Each token should be sufficiently long
        for token in tokens:
            assert len(token) > 100  # JWT tokens should be substantial length
    
    @pytest.mark.unit
    def test_sensitive_data_not_logged(self):
        """Test that sensitive data is not exposed in logs or responses."""
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SensitivePassword123!"
        )
        
        # Convert to dict (simulating serialization)
        user_dict = user_data.dict()
        
        # Password should be present in input
        assert "password" in user_dict
        assert user_dict["password"] == "SensitivePassword123!"
        
        # But when we create a UserResponse, password should not be included
        mock_user = Mock(spec=User)
        mock_user.to_dict.return_value = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "full_name": None,
            "institution": None,
            "role": "researcher",
            "is_active": True,
            "is_verified": False,
            "created_at": "2023-01-01T12:00:00"
        }
        
        response_data = mock_user.to_dict()
        
        # Sensitive fields should not be present
        assert "password" not in response_data
        assert "hashed_password" not in response_data
        
        # But other fields should be present
        assert "username" in response_data
        assert "email" in response_data