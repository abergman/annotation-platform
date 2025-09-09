"""
Integration Tests for Projects API Endpoints

Tests project creation, management, permissions, and search functionality.
"""

import pytest
from fastapi.testclient import TestClient


class TestProjectCreation:
    """Test cases for project creation endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_success(self, test_client, auth_headers):
        """Test successful project creation."""
        project_data = {
            "name": "New Research Project",
            "description": "A comprehensive research project",
            "annotation_guidelines": "Please follow these guidelines...",
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": True,
            "is_public": False
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Research Project"
        assert data["description"] == "A comprehensive research project"
        assert data["annotation_guidelines"] == "Please follow these guidelines..."
        assert data["allow_multiple_labels"] is True
        assert data["require_all_texts"] is False
        assert data["inter_annotator_agreement"] is True
        assert data["is_public"] is False
        assert data["is_active"] is True
        assert "id" in data
        assert "owner_id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["text_count"] == 0
        assert data["label_count"] == 0

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_minimal_data(self, test_client, auth_headers):
        """Test project creation with minimal required data."""
        project_data = {
            "name": "Minimal Project"
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["description"] is None
        assert data["annotation_guidelines"] is None
        assert data["allow_multiple_labels"] is True  # Default
        assert data["require_all_texts"] is False  # Default
        assert data["inter_annotator_agreement"] is False  # Default
        assert data["is_public"] is False  # Default

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_public(self, test_client, auth_headers):
        """Test creating a public project."""
        project_data = {
            "name": "Public Project",
            "description": "This is a public project",
            "is_public": True
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["is_public"] is True

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_no_auth(self, test_client):
        """Test project creation without authentication."""
        project_data = {
            "name": "Unauthorized Project"
        }
        
        response = test_client.post("/api/projects/", json=project_data)
        
        assert response.status_code == 403

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_invalid_token(self, test_client):
        """Test project creation with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        project_data = {
            "name": "Invalid Token Project"
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_missing_name(self, test_client, auth_headers):
        """Test project creation without required name field."""
        project_data = {
            "description": "Project without name"
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    @pytest.mark.api
    def test_create_project_empty_name(self, test_client, auth_headers):
        """Test project creation with empty name."""
        project_data = {
            "name": ""
        }
        
        response = test_client.post("/api/projects/", json=project_data, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error


class TestProjectListing:
    """Test cases for project listing endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_owner_only(self, test_client, auth_headers, test_project):
        """Test listing only owner's projects."""
        response = test_client.get("/api/projects/?owner_only=true", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # All projects should belong to the authenticated user
        for project in data:
            assert project["owner_id"] == test_project.owner_id

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_include_public(self, test_client, auth_headers, test_user, test_db):
        """Test listing projects including public ones."""
        # Create a public project owned by another user
        from src.models.project import Project
        from src.models.user import User
        from src.core.security import get_password_hash
        
        # Create another user
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)
        
        # Create public project
        public_project = Project(
            name="Public Project by Other",
            is_public=True,
            owner_id=other_user.id
        )
        test_db.add(public_project)
        test_db.commit()
        
        response = test_client.get("/api/projects/?owner_only=false", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Should include both owned and public projects
        owner_ids = [project["owner_id"] for project in data]
        assert test_user.id in owner_ids  # User's own projects
        assert other_user.id in owner_ids  # Public project from other user

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_pagination(self, test_client, auth_headers, test_user, test_db):
        """Test project listing pagination."""
        from src.models.project import Project
        
        # Create multiple projects
        for i in range(15):
            project = Project(
                name=f"Test Project {i}",
                owner_id=test_user.id
            )
            test_db.add(project)
        test_db.commit()
        
        # Test first page
        response = test_client.get("/api/projects/?skip=0&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        
        # Test second page
        response = test_client.get("/api/projects/?skip=5&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_search(self, test_client, auth_headers, test_user, test_db):
        """Test project search functionality."""
        from src.models.project import Project
        
        # Create projects with specific names
        projects = [
            Project(name="Machine Learning Project", description="ML research", owner_id=test_user.id),
            Project(name="Natural Language Processing", description="NLP studies", owner_id=test_user.id),
            Project(name="Computer Vision", description="CV research", owner_id=test_user.id),
        ]
        
        for project in projects:
            test_db.add(project)
        test_db.commit()
        
        # Search by name
        response = test_client.get("/api/projects/?search=Machine", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any("Machine" in project["name"] for project in data)
        
        # Search by description
        response = test_client.get("/api/projects/?search=NLP", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any("NLP" in project["description"] for project in data)

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_no_auth(self, test_client):
        """Test listing projects without authentication."""
        response = test_client.get("/api/projects/")
        assert response.status_code == 403

    @pytest.mark.integration
    @pytest.mark.api
    def test_list_projects_invalid_pagination(self, test_client, auth_headers):
        """Test listing projects with invalid pagination parameters."""
        # Negative skip
        response = test_client.get("/api/projects/?skip=-1", headers=auth_headers)
        assert response.status_code == 422
        
        # Limit too high
        response = test_client.get("/api/projects/?limit=101", headers=auth_headers)
        assert response.status_code == 422


class TestProjectRetrieval:
    """Test cases for individual project retrieval."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_project_success(self, test_client, auth_headers, test_project):
        """Test retrieving an existing project."""
        response = test_client.get(f"/api/projects/{test_project.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_project.id
        assert data["name"] == test_project.name
        assert data["owner_id"] == test_project.owner_id

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_project_not_found(self, test_client, auth_headers):
        """Test retrieving non-existent project."""
        response = test_client.get("/api/projects/99999", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_project_access_denied(self, test_client, test_db):
        """Test accessing private project owned by another user."""
        from src.models.project import Project
        from src.models.user import User
        from src.core.security import get_password_hash, create_access_token
        
        # Create another user
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)
        
        # Create private project
        private_project = Project(
            name="Private Project",
            is_public=False,
            owner_id=other_user.id
        )
        test_db.add(private_project)
        test_db.commit()
        test_db.refresh(private_project)
        
        # Create requesting user
        requesting_user = User(
            username="requester",
            email="requester@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(requesting_user)
        test_db.commit()
        test_db.refresh(requesting_user)
        
        # Create token for requesting user
        token = create_access_token({"sub": requesting_user.username})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = test_client.get(f"/api/projects/{private_project.id}", headers=headers)
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_public_project_by_non_owner(self, test_client, test_db):
        """Test accessing public project owned by another user."""
        from src.models.project import Project
        from src.models.user import User
        from src.core.security import get_password_hash, create_access_token
        
        # Create project owner
        owner = User(
            username="owner",
            email="owner@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(owner)
        test_db.commit()
        test_db.refresh(owner)
        
        # Create public project
        public_project = Project(
            name="Public Project",
            is_public=True,
            owner_id=owner.id
        )
        test_db.add(public_project)
        test_db.commit()
        test_db.refresh(public_project)
        
        # Create requesting user
        requester = User(
            username="requester",
            email="requester@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(requester)
        test_db.commit()
        test_db.refresh(requester)
        
        # Create token for requesting user
        token = create_access_token({"sub": requester.username})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = test_client.get(f"/api/projects/{public_project.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == public_project.id
        assert data["is_public"] is True

    @pytest.mark.integration
    @pytest.mark.api
    def test_get_project_no_auth(self, test_client, test_project):
        """Test retrieving project without authentication."""
        response = test_client.get(f"/api/projects/{test_project.id}")
        assert response.status_code == 403


class TestProjectUpdate:
    """Test cases for project update endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_project_success(self, test_client, auth_headers, test_project):
        """Test successful project update."""
        update_data = {
            "name": "Updated Project Name",
            "description": "Updated description",
            "annotation_guidelines": "Updated guidelines",
            "allow_multiple_labels": False,
            "is_public": True
        }
        
        response = test_client.put(
            f"/api/projects/{test_project.id}", 
            json=update_data, 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["description"] == "Updated description"
        assert data["annotation_guidelines"] == "Updated guidelines"
        assert data["allow_multiple_labels"] is False
        assert data["is_public"] is True

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_project_partial(self, test_client, auth_headers, test_project):
        """Test partial project update."""
        original_name = test_project.name
        update_data = {
            "description": "Only description updated"
        }
        
        response = test_client.put(
            f"/api/projects/{test_project.id}", 
            json=update_data, 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == original_name  # Should remain unchanged
        assert data["description"] == "Only description updated"

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_project_not_owner(self, test_client, test_db, test_project):
        """Test updating project by non-owner."""
        from src.models.user import User
        from src.core.security import get_password_hash, create_access_token
        
        # Create another user
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)
        
        # Create token for other user
        token = create_access_token({"sub": other_user.username})
        headers = {"Authorization": f"Bearer {token}"}
        
        update_data = {
            "name": "Unauthorized Update"
        }
        
        response = test_client.put(
            f"/api/projects/{test_project.id}", 
            json=update_data, 
            headers=headers
        )
        
        assert response.status_code == 403
        assert "Only project owner" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_project_not_found(self, test_client, auth_headers):
        """Test updating non-existent project."""
        update_data = {
            "name": "Non-existent Project"
        }
        
        response = test_client.put("/api/projects/99999", json=update_data, headers=auth_headers)
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_update_project_no_auth(self, test_client, test_project):
        """Test updating project without authentication."""
        update_data = {
            "name": "Unauthorized Update"
        }
        
        response = test_client.put(f"/api/projects/{test_project.id}", json=update_data)
        assert response.status_code == 403


class TestProjectDeletion:
    """Test cases for project deletion endpoint."""

    @pytest.mark.integration
    @pytest.mark.api
    def test_delete_project_success(self, test_client, auth_headers, test_user, test_db):
        """Test successful project deletion."""
        from src.models.project import Project
        
        # Create a project to delete
        project = Project(
            name="Project to Delete",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        
        response = test_client.delete(f"/api/projects/{project.id}", headers=auth_headers)
        
        assert response.status_code == 204
        
        # Verify project is deleted
        deleted_project = test_db.query(Project).filter(Project.id == project.id).first()
        assert deleted_project is None

    @pytest.mark.integration
    @pytest.mark.api
    def test_delete_project_not_owner(self, test_client, test_db, test_project):
        """Test deleting project by non-owner."""
        from src.models.user import User
        from src.core.security import get_password_hash, create_access_token
        
        # Create another user
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)
        
        # Create token for other user
        token = create_access_token({"sub": other_user.username})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = test_client.delete(f"/api/projects/{test_project.id}", headers=headers)
        
        assert response.status_code == 403
        assert "Only project owner" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_delete_project_not_found(self, test_client, auth_headers):
        """Test deleting non-existent project."""
        response = test_client.delete("/api/projects/99999", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.api
    def test_delete_project_no_auth(self, test_client, test_project):
        """Test deleting project without authentication."""
        response = test_client.delete(f"/api/projects/{test_project.id}")
        assert response.status_code == 403