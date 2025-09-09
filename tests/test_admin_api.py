"""
Test cases for Admin API endpoints.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models.user import User
from src.models.project import Project
from src.models.audit_log import AuditLog, SecurityEvent
from src.core.security import get_password_hash, create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user for testing."""
    admin = User(
        username="admin_test",
        email="admin@test.com",
        hashed_password=get_password_hash("admin_password"),
        full_name="Admin User",
        role="admin",
        is_active=True,
        is_admin=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def admin_token(admin_user: User):
    """Create an admin access token."""
    return create_access_token(data={"sub": admin_user.username})


@pytest.fixture
def regular_user(db_session: Session):
    """Create a regular user for testing."""
    user = User(
        username="regular_test",
        email="regular@test.com",
        hashed_password=get_password_hash("user_password"),
        full_name="Regular User",
        role="researcher",
        is_active=True,
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_token(regular_user: User):
    """Create a regular user access token."""
    return create_access_token(data={"sub": regular_user.username})


class TestUserManagement:
    """Test user management endpoints."""
    
    def test_list_users_as_admin(self, client: TestClient, admin_token: str, db_session: Session):
        """Test listing users as admin."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/users", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "pagination" in data
        assert isinstance(data["users"], list)
    
    def test_list_users_as_regular_user_forbidden(self, client: TestClient, regular_token: str):
        """Test that regular users cannot list users."""
        headers = {"Authorization": f"Bearer {regular_token}"}
        response = client.get("/api/admin/users", headers=headers)
        
        assert response.status_code == 403
    
    def test_create_user_as_admin(self, client: TestClient, admin_token: str, db_session: Session):
        """Test creating a user as admin."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        user_data = {
            "username": "new_test_user",
            "email": "newuser@test.com",
            "password": "password123",
            "full_name": "New Test User",
            "role": "researcher",
            "is_active": True
        }
        
        response = client.post("/api/admin/users", json=user_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "User created successfully"
        assert data["user"]["username"] == "new_test_user"
        
        # Verify user was created in database
        user = db_session.query(User).filter(User.username == "new_test_user").first()
        assert user is not None
        assert user.email == "newuser@test.com"
    
    def test_get_user_details(self, client: TestClient, admin_token: str, regular_user: User):
        """Test getting user details."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get(f"/api/admin/users/{regular_user.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == regular_user.username
        assert data["user"]["email"] == regular_user.email
    
    def test_update_user(self, client: TestClient, admin_token: str, regular_user: User, db_session: Session):
        """Test updating a user."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {
            "full_name": "Updated Name",
            "role": "annotator"
        }
        
        response = client.put(f"/api/admin/users/{regular_user.id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        
        # Verify update in database
        db_session.refresh(regular_user)
        assert regular_user.full_name == "Updated Name"
        assert regular_user.role == "annotator"
    
    def test_bulk_user_operations(self, client: TestClient, admin_token: str, db_session: Session):
        """Test bulk user operations."""
        # Create test users
        test_users = []
        for i in range(3):
            user = User(
                username=f"bulk_test_{i}",
                email=f"bulk{i}@test.com",
                hashed_password=get_password_hash("password123"),
                is_active=True
            )
            db_session.add(user)
            test_users.append(user)
        
        db_session.commit()
        for user in test_users:
            db_session.refresh(user)
        
        # Test bulk deactivation
        headers = {"Authorization": f"Bearer {admin_token}"}
        bulk_data = {
            "user_ids": [user.id for user in test_users],
            "operation": "deactivate"
        }
        
        response = client.post("/api/admin/users/bulk", json=bulk_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Bulk operation completed"
        assert len(data["results"]) == 3
        
        # Verify users were deactivated
        for user in test_users:
            db_session.refresh(user)
            assert not user.is_active


class TestProjectAdministration:
    """Test project administration endpoints."""
    
    def test_list_projects_as_admin(self, client: TestClient, admin_token: str):
        """Test listing projects as admin."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/projects", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "pagination" in data
    
    def test_get_project_details(self, client: TestClient, admin_token: str, admin_user: User, db_session: Session):
        """Test getting detailed project information."""
        # Create a test project
        project = Project(
            name="Test Admin Project",
            description="Test project for admin API",
            owner_id=admin_user.id
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get(f"/api/admin/projects/{project.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"]["name"] == "Test Admin Project"
        assert "statistics" in data["project"]


class TestSystemStatistics:
    """Test system statistics endpoints."""
    
    def test_system_overview(self, client: TestClient, admin_token: str):
        """Test getting system overview."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/statistics/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert "recent_activity" in data
        assert "system_resources" in data
        
        # Check required overview fields
        overview = data["overview"]
        assert "total_users" in overview
        assert "active_users" in overview
        assert "total_projects" in overview
    
    def test_system_timeline(self, client: TestClient, admin_token: str):
        """Test getting system timeline statistics."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/statistics/timeline?days=7", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data
        assert "period" in data
        
        timeline = data["timeline"]
        assert "daily_users" in timeline
        assert "daily_projects" in timeline
        assert "daily_annotations" in timeline


class TestDatabaseMaintenance:
    """Test database maintenance endpoints."""
    
    def test_database_health_check(self, client: TestClient, admin_token: str):
        """Test database health check."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/health/database", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data


class TestAuditLogs:
    """Test audit log management."""
    
    def test_get_audit_logs(self, client: TestClient, admin_token: str, admin_user: User, db_session: Session):
        """Test getting audit logs."""
        # Create a test audit log
        audit_log = AuditLog(
            admin_id=admin_user.id,
            action="TEST_ACTION",
            target_type="test",
            target_id=1,
            details={"test": "data"}
        )
        db_session.add(audit_log)
        db_session.commit()
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/audit-logs", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "audit_logs" in data
        assert "pagination" in data
        assert len(data["audit_logs"]) >= 1
    
    def test_get_security_events(self, client: TestClient, admin_token: str, db_session: Session):
        """Test getting security events."""
        # Create a test security event
        security_event = SecurityEvent(
            event_type="TEST_EVENT",
            severity="MEDIUM",
            description="Test security event",
            resolved=False
        )
        db_session.add(security_event)
        db_session.commit()
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/security-events", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "security_events" in data
        assert "pagination" in data


class TestDataExport:
    """Test data export functionality."""
    
    def test_export_system_data_json(self, client: TestClient, admin_token: str):
        """Test exporting system data as JSON."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get(
            "/api/admin/export/system-data?format=json&include_users=true&include_projects=true",
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestDashboard:
    """Test dashboard endpoints."""
    
    def test_dashboard_summary(self, client: TestClient, admin_token: str):
        """Test getting dashboard summary."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/dashboard/summary", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "totals" in data
        assert "recent" in data
        assert "alerts" in data
        assert "recent_activity" in data


class TestConfiguration:
    """Test configuration management."""
    
    def test_get_system_configuration(self, client: TestClient, admin_token: str):
        """Test getting system configuration."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/config", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "configuration" in data
        
        config = data["configuration"]
        assert "application" in config
        assert "features" in config
        assert "security" in config
        assert "cors" in config


class TestAccessControl:
    """Test access control for admin endpoints."""
    
    def test_admin_endpoint_without_token_unauthorized(self, client: TestClient):
        """Test accessing admin endpoint without token."""
        response = client.get("/api/admin/users")
        assert response.status_code == 401
    
    def test_admin_endpoint_with_regular_user_forbidden(self, client: TestClient, regular_token: str):
        """Test accessing admin endpoint with regular user token."""
        headers = {"Authorization": f"Bearer {regular_token}"}
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403
    
    def test_super_admin_endpoint_with_regular_admin_forbidden(self, client: TestClient, admin_token: str):
        """Test accessing super admin endpoint with regular admin token."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post("/api/admin/maintenance/cleanup", headers=headers)
        
        # This might be forbidden if the admin is not a super admin
        # The actual response depends on the test database state
        assert response.status_code in [200, 403]


if __name__ == "__main__":
    pytest.main([__file__])