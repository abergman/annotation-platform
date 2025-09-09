"""
Integration Tests for Authentication API Endpoints

Tests user registration, login, profile management, and authentication flow.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timedelta

from src.core.security import create_access_token


class TestUserRegistration:
    """Test cases for user registration endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_success(self, test_client):
        """Test successful user registration."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "full_name": "New User",
            "institution": "Test University"
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["institution"] == "Test University"
        assert data["role"] == "researcher"
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        assert "created_at" in data
        # Ensure password is not returned
        assert "password" not in data
        assert "hashed_password" not in data

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_minimal_data(self, test_client):
        """Test user registration with minimal required data."""
        user_data = {
            "username": "minimaluser",
            "email": "minimal@example.com",
            "password": "SecurePassword123!"
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "minimaluser"
        assert data["email"] == "minimal@example.com"
        assert data["full_name"] is None
        assert data["institution"] is None

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_duplicate_username(self, test_client, test_user):
        """Test registration with existing username."""
        user_data = {
            "username": test_user.username,  # Already exists
            "email": "different@example.com",
            "password": "SecurePassword123!"
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_duplicate_email(self, test_client, test_user):
        """Test registration with existing email."""
        user_data = {
            "username": "differentuser",
            "email": test_user.email,  # Already exists
            "password": "SecurePassword123!"
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_invalid_email(self, test_client):
        """Test registration with invalid email format."""
        user_data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "SecurePassword123!"
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_missing_fields(self, test_client):
        """Test registration with missing required fields."""
        user_data = {
            "username": "testuser"
            # Missing email and password
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    @pytest.mark.api
    def test_register_user_empty_strings(self, test_client):
        """Test registration with empty string values."""
        user_data = {
            "username": "",
            "email": "",
            "password": ""
        }
        
        response = test_client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test cases for user login endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_success(self, test_client, test_user_data, test_user):
        """Test successful user login."""
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "user" in data
        assert data["user"]["username"] == test_user.username
        assert data["user"]["email"] == test_user.email

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_wrong_username(self, test_client):
        """Test login with wrong username."""
        login_data = {
            "username": "nonexistentuser",
            "password": "anypassword"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_wrong_password(self, test_client, test_user_data):
        """Test login with wrong password."""
        login_data = {
            "username": test_user_data["username"],
            "password": "wrongpassword"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_inactive_user(self, test_client, test_user_data, test_user, test_db):
        """Test login with inactive user account."""
        # Deactivate user
        test_user.is_active = False
        test_db.commit()
        
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "User account is inactive" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_updates_last_login(self, test_client, test_user_data, test_user, test_db):
        """Test that login updates last_login timestamp."""
        # Ensure last_login is initially None
        assert test_user.last_login is None
        
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        
        # Refresh user from database
        test_db.refresh(test_user)
        assert test_user.last_login is not None
        assert isinstance(test_user.last_login, datetime)

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_missing_fields(self, test_client):
        """Test login with missing fields."""
        login_data = {
            "username": "testuser"
            # Missing password
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    @pytest.mark.api
    def test_login_empty_credentials(self, test_client):
        """Test login with empty credentials."""
        login_data = {
            "username": "",
            "password": ""
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401


class TestUserProfile:
    """Test cases for user profile endpoints."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_current_user_success(self, test_client, auth_headers):
        """Test getting current user profile."""
        response = test_client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "full_name" in data
        assert "institution" in data
        assert "role" in data
        assert "is_active" in data
        assert "is_verified" in data
        assert "created_at" in data

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_current_user_no_auth(self, test_client):
        """Test getting current user without authentication."""
        response = test_client.get("/api/auth/me")
        
        assert response.status_code == 403  # No authorization header

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_current_user_invalid_token(self, test_client):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = test_client.get("/api/auth/me", headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_user_profile_success(self, test_client, auth_headers):
        """Test updating user profile."""
        update_data = {
            "full_name": "Updated Name",
            "institution": "New University",
            "bio": "Updated bio information"
        }
        
        response = test_client.put("/api/auth/me", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["institution"] == "New University"
        # Bio is not returned in UserResponse, but update should work

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_user_profile_partial(self, test_client, auth_headers):
        """Test partial user profile update."""
        update_data = {
            "full_name": "Only Name Updated"
        }
        
        response = test_client.put("/api/auth/me", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Only Name Updated"

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_user_profile_empty_data(self, test_client, auth_headers):
        """Test updating profile with empty data."""
        update_data = {}
        
        response = test_client.put("/api/auth/me", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200  # Should still work with no changes

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_user_profile_no_auth(self, test_client):
        """Test updating profile without authentication."""
        update_data = {
            "full_name": "Updated Name"
        }
        
        response = test_client.put("/api/auth/me", json=update_data)
        
        assert response.status_code == 403


class TestLogout:
    """Test cases for logout endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_logout_success(self, test_client):
        """Test logout endpoint."""
        response = test_client.post("/api/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logged out" in data["message"].lower()

    @pytest.mark.integration
    @pytest.mark.api
    def test_logout_with_auth(self, test_client, auth_headers):
        """Test logout with authentication headers."""
        response = test_client.post("/api/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200


class TestAuthenticationFlow:
    """Test cases for complete authentication flow."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_complete_auth_flow(self, test_client):
        """Test complete authentication flow: register -> login -> profile -> update."""
        # 1. Register user
        user_data = {
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "FlowPassword123!"
        }
        
        register_response = test_client.post("/api/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # 2. Login
        login_data = {
            "username": "flowuser",
            "password": "FlowPassword123!"
        }
        
        login_response = test_client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == 200
        
        token_data = login_response.json()
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        
        # 3. Get profile
        profile_response = test_client.get("/api/auth/me", headers=headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["username"] == "flowuser"
        
        # 4. Update profile
        update_data = {
            "full_name": "Flow User Updated",
            "institution": "Flow University"
        }
        
        update_response = test_client.put("/api/auth/me", json=update_data, headers=headers)
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["full_name"] == "Flow User Updated"
        assert updated_data["institution"] == "Flow University"
        
        # 5. Logout
        logout_response = test_client.post("/api/auth/logout", headers=headers)
        assert logout_response.status_code == 200

    @pytest.mark.integration
    @pytest.mark.api
    def test_token_expiration_simulation(self, test_client, test_user):
        """Test behavior with expired token."""
        # Create an expired token
        expired_token_data = {"sub": test_user.username}
        expired_delta = timedelta(seconds=-1)  # Already expired
        
        with patch('src.core.security.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            expired_token = create_access_token(expired_token_data, expired_delta)
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = test_client.get("/api/auth/me", headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.api
    def test_concurrent_user_registration(self, test_client):
        """Test concurrent registration attempts with same username."""
        user_data1 = {
            "username": "concurrent",
            "email": "concurrent1@example.com",
            "password": "Password123!"
        }
        
        user_data2 = {
            "username": "concurrent",  # Same username
            "email": "concurrent2@example.com",
            "password": "Password123!"
        }
        
        # First registration should succeed
        response1 = test_client.post("/api/auth/register", json=user_data1)
        assert response1.status_code == 201
        
        # Second registration should fail
        response2 = test_client.post("/api/auth/register", json=user_data2)
        assert response2.status_code == 400
        assert "Username already registered" in response2.json()["detail"]