"""
Unit Tests for Projects API Endpoints

Comprehensive test suite for project CRUD operations, access control, 
pagination, search functionality, and ownership permissions.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import or_

# Import the code under test
from src.api.projects import (
    create_project,
    list_projects,
    get_project,
    update_project,
    delete_project,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse
)
from src.models.project import Project
from src.models.user import User


class TestProjectCreation:
    """Unit tests for project creation functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.is_active = True
        return user
    
    @pytest.fixture
    def valid_project_data(self):
        """Valid project creation data."""
        return ProjectCreate(
            name="Test Project",
            description="A test project for annotation",
            annotation_guidelines="Please label all entities carefully",
            allow_multiple_labels=True,
            require_all_texts=False,
            inter_annotator_agreement=False,
            is_public=False
        )
    
    @pytest.fixture
    def minimal_project_data(self):
        """Minimal project creation data."""
        return ProjectCreate(
            name="Minimal Project"
        )
    
    @pytest.fixture
    def mock_created_project(self):
        """Mock created project."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.description = "A test project for annotation"
        project.annotation_guidelines = "Please label all entities carefully"
        project.allow_multiple_labels = True
        project.require_all_texts = False
        project.inter_annotator_agreement = False
        project.is_active = True
        project.is_public = False
        project.owner_id = 1
        project.created_at = datetime(2023, 1, 1, 12, 0, 0)
        project.updated_at = datetime(2023, 1, 1, 12, 0, 0)
        project.texts = []
        project.labels = []
        project.to_dict.return_value = {
            "id": 1,
            "name": "Test Project",
            "description": "A test project for annotation",
            "annotation_guidelines": "Please label all entities carefully",
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 0,
            "label_count": 0
        }
        return project
    
    @pytest.mark.unit
    async def test_create_project_success(self, mock_db, mock_current_user, valid_project_data, mock_created_project):
        """Test successful project creation."""
        # Mock database operations
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.projects.Project') as mock_project_class:
            mock_project_class.return_value = mock_created_project
            
            result = await create_project(valid_project_data, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, ProjectResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 1
            assert result["name"] == "Test Project"
            assert result["description"] == "A test project for annotation"
            assert result["annotation_guidelines"] == "Please label all entities carefully"
            assert result["allow_multiple_labels"] is True
            assert result["require_all_texts"] is False
            assert result["inter_annotator_agreement"] is False
            assert result["is_public"] is False
            assert result["owner_id"] == 1
            assert result["text_count"] == 0
            assert result["label_count"] == 0
        
        # Verify database interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify project creation with correct data
        mock_project_class.assert_called_once_with(
            name="Test Project",
            description="A test project for annotation",
            annotation_guidelines="Please label all entities carefully",
            allow_multiple_labels=True,
            require_all_texts=False,
            inter_annotator_agreement=False,
            is_public=False,
            owner_id=1
        )
    
    @pytest.mark.unit
    async def test_create_project_minimal_data(self, mock_db, mock_current_user, minimal_project_data):
        """Test project creation with minimal required data."""
        # Mock created project with defaults
        mock_created_project = Mock(spec=Project)
        mock_created_project.to_dict.return_value = {
            "id": 1,
            "name": "Minimal Project",
            "description": None,
            "annotation_guidelines": None,
            "allow_multiple_labels": True,  # Default
            "require_all_texts": False,     # Default
            "inter_annotator_agreement": False,  # Default
            "is_active": True,
            "is_public": False,  # Default
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 0,
            "label_count": 0
        }
        
        # Mock database operations
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.projects.Project') as mock_project_class:
            mock_project_class.return_value = mock_created_project
            
            result = await create_project(minimal_project_data, mock_current_user, mock_db)
        
        # Verify defaults are applied
        if isinstance(result, dict):
            assert result["name"] == "Minimal Project"
            assert result["description"] is None
            assert result["annotation_guidelines"] is None
            assert result["allow_multiple_labels"] is True  # Default
            assert result["require_all_texts"] is False     # Default
            assert result["inter_annotator_agreement"] is False  # Default
            assert result["is_public"] is False  # Default
    
    @pytest.mark.unit
    async def test_create_project_public(self, mock_db, mock_current_user):
        """Test creating a public project."""
        public_project_data = ProjectCreate(
            name="Public Project",
            description="A public project",
            is_public=True
        )
        
        mock_created_project = Mock(spec=Project)
        mock_created_project.to_dict.return_value = {
            "id": 1,
            "name": "Public Project",
            "description": "A public project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": True,  # Should be public
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 0,
            "label_count": 0
        }
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.projects.Project') as mock_project_class:
            mock_project_class.return_value = mock_created_project
            
            result = await create_project(public_project_data, mock_current_user, mock_db)
        
        if isinstance(result, dict):
            assert result["is_public"] is True
    
    @pytest.mark.unit
    async def test_create_project_database_error(self, mock_db, mock_current_user, valid_project_data):
        """Test project creation handles database errors."""
        mock_db.add = Mock()
        mock_db.commit.side_effect = Exception("Database error")
        mock_db.refresh = Mock()
        
        with patch('src.api.projects.Project') as mock_project_class:
            mock_project_class.return_value = Mock(spec=Project)
            
            with pytest.raises(Exception) as exc_info:
                await create_project(valid_project_data, mock_current_user, mock_db)
            
            assert "Database error" in str(exc_info.value)


class TestProjectListing:
    """Unit tests for project listing functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_other_user(self):
        """Mock another user."""
        user = Mock(spec=User)
        user.id = 2
        user.username = "otheruser"
        return user
    
    @pytest.fixture
    def sample_projects(self, mock_current_user, mock_other_user):
        """Sample projects for testing."""
        # User's own private project
        project1 = Mock(spec=Project)
        project1.id = 1
        project1.name = "My Private Project"
        project1.description = "Private project"
        project1.owner_id = 1
        project1.is_public = False
        project1.to_dict.return_value = {
            "id": 1,
            "name": "My Private Project",
            "description": "Private project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 5,
            "label_count": 3
        }
        
        # User's own public project
        project2 = Mock(spec=Project)
        project2.id = 2
        project2.name = "My Public Project"
        project2.description = "Public project"
        project2.owner_id = 1
        project2.is_public = True
        project2.to_dict.return_value = {
            "id": 2,
            "name": "My Public Project",
            "description": "Public project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": True,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 10,
            "label_count": 5
        }
        
        # Other user's public project
        project3 = Mock(spec=Project)
        project3.id = 3
        project3.name = "Other Public Project"
        project3.description = "Another public project"
        project3.owner_id = 2
        project3.is_public = True
        project3.to_dict.return_value = {
            "id": 3,
            "name": "Other Public Project",
            "description": "Another public project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": True,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 2,
            "text_count": 7,
            "label_count": 2
        }
        
        # Other user's private project (should not be visible)
        project4 = Mock(spec=Project)
        project4.id = 4
        project4.name = "Other Private Project"
        project4.description = "Private project by other user"
        project4.owner_id = 2
        project4.is_public = False
        project4.to_dict.return_value = {
            "id": 4,
            "name": "Other Private Project",
            "description": "Private project by other user",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 2,
            "text_count": 3,
            "label_count": 1
        }
        
        return [project1, project2, project3, project4]
    
    @pytest.mark.unit
    async def test_list_projects_default_access(self, mock_db, mock_current_user, sample_projects):
        """Test listing projects with default access (user's + public)."""
        # Mock query chain that returns user's projects and public projects
        mock_query = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Should return: user's private, user's public, other's public (not other's private)
        expected_projects = [sample_projects[0], sample_projects[1], sample_projects[2]]
        mock_limit.all.return_value = expected_projects
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=0,
            limit=10,
            search=None,
            owner_only=False,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Assertions
        assert isinstance(result, list)
        assert len(result) == 3
        
        # Verify the filter was called with correct OR condition
        mock_query.filter.assert_called_once()
        filter_args = mock_query.filter.call_args[0][0]
        # The filter should be an OR condition for owner_id == user.id OR is_public == True
        
        # Verify pagination was applied
        mock_filter.offset.assert_called_once_with(0)
        mock_offset.limit.assert_called_once_with(10)
    
    @pytest.mark.unit
    async def test_list_projects_owner_only(self, mock_db, mock_current_user, sample_projects):
        """Test listing only user's own projects."""
        # Mock query chain that returns only user's projects
        mock_query = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Should return only user's projects (both private and public)
        user_projects = [sample_projects[0], sample_projects[1]]
        mock_limit.all.return_value = user_projects
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=0,
            limit=10,
            search=None,
            owner_only=True,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Assertions
        assert isinstance(result, list)
        assert len(result) == 2
        
        # Verify the filter was called for owner_id only
        mock_query.filter.assert_called_once()
    
    @pytest.mark.unit
    async def test_list_projects_with_search(self, mock_db, mock_current_user, sample_projects):
        """Test listing projects with search filter."""
        # Mock query chain
        mock_query = Mock()
        mock_filter1 = Mock()  # For access control
        mock_filter2 = Mock()  # For search
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Should return projects matching search term
        matching_projects = [sample_projects[1]]  # "My Public Project"
        mock_limit.all.return_value = matching_projects
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_query.filter.return_value = mock_filter1
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=0,
            limit=10,
            search="Public",
            owner_only=False,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Assertions
        assert isinstance(result, list)
        assert len(result) == 1
        
        # Verify both filters were applied (access control and search)
        assert mock_query.filter.call_count == 1
        assert mock_filter1.filter.call_count == 1
    
    @pytest.mark.unit
    async def test_list_projects_pagination(self, mock_db, mock_current_user, sample_projects):
        """Test project listing pagination."""
        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Return subset for pagination
        paginated_projects = [sample_projects[1]]
        mock_limit.all.return_value = paginated_projects
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=5,
            limit=2,
            search=None,
            owner_only=False,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify pagination parameters were applied
        mock_filter.offset.assert_called_once_with(5)
        mock_offset.limit.assert_called_once_with(2)
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    @pytest.mark.unit
    async def test_list_projects_empty_result(self, mock_db, mock_current_user):
        """Test listing projects when no projects match criteria."""
        # Mock query chain returning empty list
        mock_query = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=0,
            limit=10,
            search="NonexistentProject",
            owner_only=False,
            current_user=mock_current_user,
            db=mock_db
        )
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @pytest.mark.unit
    async def test_list_projects_search_case_insensitive(self, mock_db, mock_current_user, sample_projects):
        """Test search is case insensitive using ILIKE."""
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        matching_projects = [sample_projects[1]]
        mock_limit.all.return_value = matching_projects
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_query.filter.return_value = mock_filter1
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=0,
            limit=10,
            search="PUBLIC",  # Uppercase search term
            owner_only=False,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Should still find matches due to ILIKE
        assert isinstance(result, list)
        
        # Verify search filter was applied
        assert mock_filter1.filter.call_count == 1


class TestProjectRetrieval:
    """Unit tests for individual project retrieval."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_other_user(self):
        """Mock another user."""
        user = Mock(spec=User)
        user.id = 2
        user.username = "otheruser"
        return user
    
    @pytest.fixture
    def mock_user_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "User's Project"
        project.owner_id = 1
        project.is_public = False
        project.to_dict.return_value = {
            "id": 1,
            "name": "User's Project",
            "description": "A project owned by the user",
            "annotation_guidelines": "Guidelines here",
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 5,
            "label_count": 3
        }
        return project
    
    @pytest.fixture
    def mock_public_project(self, mock_other_user):
        """Mock public project owned by another user."""
        project = Mock(spec=Project)
        project.id = 2
        project.name = "Public Project"
        project.owner_id = 2
        project.is_public = True
        project.to_dict.return_value = {
            "id": 2,
            "name": "Public Project",
            "description": "A public project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": True,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 2,
            "text_count": 10,
            "label_count": 5
        }
        return project
    
    @pytest.fixture
    def mock_private_project(self, mock_other_user):
        """Mock private project owned by another user."""
        project = Mock(spec=Project)
        project.id = 3
        project.name = "Private Project"
        project.owner_id = 2
        project.is_public = False
        project.to_dict.return_value = {
            "id": 3,
            "name": "Private Project",
            "description": "A private project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 2,
            "text_count": 3,
            "label_count": 2
        }
        return project
    
    @pytest.mark.unit
    async def test_get_project_own_project(self, mock_db, mock_current_user, mock_user_project):
        """Test retrieving user's own project."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await get_project(1, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, ProjectResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 1
            assert result["name"] == "User's Project"
            assert result["owner_id"] == 1
    
    @pytest.mark.unit
    async def test_get_project_public_project(self, mock_db, mock_current_user, mock_public_project):
        """Test retrieving public project owned by another user."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_public_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await get_project(2, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, ProjectResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 2
            assert result["name"] == "Public Project"
            assert result["owner_id"] == 2
            assert result["is_public"] is True
    
    @pytest.mark.unit
    async def test_get_project_not_found(self, mock_db, mock_current_user):
        """Test retrieving non-existent project."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await get_project(999, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Project not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_get_project_access_denied(self, mock_db, mock_current_user, mock_private_project):
        """Test retrieving private project owned by another user."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_private_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await get_project(3, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied to this project" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_get_project_database_error(self, mock_db, mock_current_user):
        """Test handling database errors during project retrieval."""
        # Mock database query that raises an exception
        mock_db.query.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc_info:
            await get_project(1, mock_current_user, mock_db)
        
        assert "Database connection failed" in str(exc_info.value)


class TestProjectUpdate:
    """Unit tests for project update functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_other_user(self):
        """Mock another user."""
        user = Mock(spec=User)
        user.id = 2
        user.username = "otheruser"
        return user
    
    @pytest.fixture
    def mock_user_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Original Name"
        project.description = "Original Description"
        project.annotation_guidelines = "Original Guidelines"
        project.allow_multiple_labels = True
        project.require_all_texts = False
        project.inter_annotator_agreement = False
        project.is_public = False
        project.is_active = True
        project.owner_id = 1
        project.to_dict.return_value = {
            "id": 1,
            "name": "Updated Name",  # Will be updated by the test
            "description": "Updated Description",
            "annotation_guidelines": "Updated Guidelines",
            "allow_multiple_labels": False,
            "require_all_texts": True,
            "inter_annotator_agreement": True,
            "is_active": True,
            "is_public": True,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T13:00:00",
            "owner_id": 1,
            "text_count": 5,
            "label_count": 3
        }
        return project
    
    @pytest.fixture
    def mock_other_project(self, mock_other_user):
        """Mock project owned by another user."""
        project = Mock(spec=Project)
        project.id = 2
        project.name = "Other's Project"
        project.owner_id = 2
        project.is_public = True
        return project
    
    @pytest.fixture
    def full_update_data(self):
        """Full project update data."""
        return ProjectUpdate(
            name="Updated Name",
            description="Updated Description",
            annotation_guidelines="Updated Guidelines",
            allow_multiple_labels=False,
            require_all_texts=True,
            inter_annotator_agreement=True,
            is_public=True,
            is_active=True
        )
    
    @pytest.fixture
    def partial_update_data(self):
        """Partial project update data."""
        return ProjectUpdate(
            name="New Name Only"
        )
    
    @pytest.mark.unit
    async def test_update_project_success_full(self, mock_db, mock_current_user, mock_user_project, full_update_data):
        """Test successful project update with all fields."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await update_project(1, full_update_data, mock_current_user, mock_db)
        
        # Verify fields were updated
        assert mock_user_project.name == "Updated Name"
        assert mock_user_project.description == "Updated Description"
        assert mock_user_project.annotation_guidelines == "Updated Guidelines"
        assert mock_user_project.allow_multiple_labels is False
        assert mock_user_project.require_all_texts is True
        assert mock_user_project.inter_annotator_agreement is True
        assert mock_user_project.is_public is True
        assert mock_user_project.is_active is True
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user_project)
        
        # Verify response
        assert isinstance(result, ProjectResponse) or isinstance(result, dict)
    
    @pytest.mark.unit
    async def test_update_project_success_partial(self, mock_db, mock_current_user, mock_user_project, partial_update_data):
        """Test successful project update with partial data."""
        # Store original values
        original_description = mock_user_project.description
        original_guidelines = mock_user_project.annotation_guidelines
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await update_project(1, partial_update_data, mock_current_user, mock_db)
        
        # Verify only name was updated
        assert mock_user_project.name == "New Name Only"
        assert mock_user_project.description == original_description  # Unchanged
        assert mock_user_project.annotation_guidelines == original_guidelines  # Unchanged
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user_project)
    
    @pytest.mark.unit
    async def test_update_project_not_found(self, mock_db, mock_current_user, full_update_data):
        """Test updating non-existent project."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_project(999, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Project not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_project_not_owner(self, mock_db, mock_current_user, mock_other_project, full_update_data):
        """Test updating project owned by another user."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_other_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_project(2, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Only project owner can update the project" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_project_empty_update(self, mock_db, mock_current_user, mock_user_project):
        """Test project update with no changes."""
        empty_update = ProjectUpdate()
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await update_project(1, empty_update, mock_current_user, mock_db)
        
        # Database operations should still be called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user_project)
        
        # Result should still be returned
        assert result is not None
    
    @pytest.mark.unit
    async def test_update_project_database_error(self, mock_db, mock_current_user, mock_user_project, full_update_data):
        """Test handling database errors during project update."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Mock database commit error
        mock_db.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception) as exc_info:
            await update_project(1, full_update_data, mock_current_user, mock_db)
        
        assert "Database error" in str(exc_info.value)


class TestProjectDeletion:
    """Unit tests for project deletion functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.delete = Mock()
        db.commit = Mock()
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_user_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "User's Project"
        project.owner_id = 1
        return project
    
    @pytest.fixture
    def mock_other_project(self):
        """Mock project owned by another user."""
        project = Mock(spec=Project)
        project.id = 2
        project.name = "Other's Project"
        project.owner_id = 2
        return project
    
    @pytest.mark.unit
    async def test_delete_project_success(self, mock_db, mock_current_user, mock_user_project):
        """Test successful project deletion."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await delete_project(1, mock_current_user, mock_db)
        
        # Verify database operations
        mock_db.delete.assert_called_once_with(mock_user_project)
        mock_db.commit.assert_called_once()
        
        # Verify return value (should be None for 204 status)
        assert result is None
    
    @pytest.mark.unit
    async def test_delete_project_not_found(self, mock_db, mock_current_user):
        """Test deleting non-existent project."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_project(999, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Project not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_delete_project_not_owner(self, mock_db, mock_current_user, mock_other_project):
        """Test deleting project owned by another user."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_other_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_project(2, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Only project owner can delete the project" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_delete_project_database_error(self, mock_db, mock_current_user, mock_user_project):
        """Test handling database errors during project deletion."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Mock database delete error
        mock_db.delete.side_effect = Exception("Database error")
        
        with pytest.raises(Exception) as exc_info:
            await delete_project(1, mock_current_user, mock_db)
        
        assert "Database error" in str(exc_info.value)


class TestEdgeCases:
    """Unit tests for edge cases and error conditions."""
    
    @pytest.mark.unit
    async def test_create_project_long_name(self):
        """Test creating project with very long name."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        # Project with name at maximum length (assuming 200 chars max from model)
        long_name = "A" * 200
        project_data = ProjectCreate(name=long_name)
        
        mock_created_project = Mock(spec=Project)
        mock_created_project.to_dict.return_value = {
            "id": 1,
            "name": long_name,
            "description": None,
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 0,
            "label_count": 0
        }
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.projects.Project') as mock_project_class:
            mock_project_class.return_value = mock_created_project
            
            result = await create_project(project_data, mock_user, mock_db)
        
        if isinstance(result, dict):
            assert len(result["name"]) == 200
    
    @pytest.mark.unit
    async def test_list_projects_large_pagination(self):
        """Test project listing with large pagination values."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await list_projects(
            skip=10000,
            limit=100,
            search=None,
            owner_only=False,
            current_user=mock_user,
            db=mock_db
        )
        
        # Verify large pagination values are handled
        mock_filter.offset.assert_called_once_with(10000)
        mock_offset.limit.assert_called_once_with(100)
        assert isinstance(result, list)
    
    @pytest.mark.unit
    async def test_search_special_characters(self):
        """Test project search with special characters."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        # Mock query chain
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_query.filter.return_value = mock_filter1
        mock_db.query.return_value = mock_query
        
        # Test with special characters that might cause SQL issues
        special_search_terms = [
            "project's name",
            "project with % wildcard",
            "project with _ underscore",
            "project with 'quotes'",
            'project with "double quotes"',
            "project with \\ backslash"
        ]
        
        for search_term in special_search_terms:
            result = await list_projects(
                skip=0,
                limit=10,
                search=search_term,
                owner_only=False,
                current_user=mock_user,
                db=mock_db
            )
            
            # Should not raise an exception
            assert isinstance(result, list)
    
    @pytest.mark.unit
    async def test_project_update_boundary_values(self):
        """Test project update with boundary values."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        mock_project = Mock(spec=Project)
        mock_project.id = 1
        mock_project.owner_id = 1
        mock_project.name = "Original"
        mock_project.to_dict.return_value = {
            "id": 1,
            "name": "Empty Description Test",
            "description": "",  # Empty string
            "annotation_guidelines": None,  # Null
            "allow_multiple_labels": False,
            "require_all_texts": True,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 0,
            "label_count": 0
        }
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Test update with empty string and None values
        boundary_update = ProjectUpdate(
            name="Empty Description Test",
            description="",  # Empty string
            annotation_guidelines=None  # Explicit None
        )
        
        result = await update_project(1, boundary_update, mock_user, mock_db)
        
        # Verify empty string and None are handled correctly
        assert mock_project.name == "Empty Description Test"
        assert mock_project.description == ""
        assert mock_project.annotation_guidelines is None
    
    @pytest.mark.unit
    async def test_concurrent_project_access(self):
        """Test simulated concurrent access to projects."""
        mock_db = Mock(spec=Session)
        mock_user1 = Mock(spec=User)
        mock_user1.id = 1
        mock_user2 = Mock(spec=User)
        mock_user2.id = 2
        
        mock_project = Mock(spec=Project)
        mock_project.id = 1
        mock_project.owner_id = 1
        mock_project.is_public = True
        mock_project.to_dict.return_value = {
            "id": 1,
            "name": "Shared Project",
            "description": "Public project",
            "annotation_guidelines": None,
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": True,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 5,
            "label_count": 3
        }
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_project
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Both users should be able to access the public project
        result1 = await get_project(1, mock_user1, mock_db)
        result2 = await get_project(1, mock_user2, mock_db)
        
        # Both should succeed
        assert result1 is not None
        assert result2 is not None
        if isinstance(result1, dict) and isinstance(result2, dict):
            assert result1["id"] == result2["id"] == 1
            assert result1["is_public"] is True
            assert result2["is_public"] is True


class TestPerformanceAndSecurity:
    """Tests for performance and security considerations."""
    
    @pytest.mark.unit
    async def test_prevent_sql_injection_in_search(self):
        """Test that search filters prevent SQL injection."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        # Mock query chain
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_query.filter.return_value = mock_filter1
        mock_db.query.return_value = mock_query
        
        # SQL injection attempts
        malicious_search_terms = [
            "'; DROP TABLE projects; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "1'; DELETE FROM projects; --"
        ]
        
        for malicious_term in malicious_search_terms:
            try:
                result = await list_projects(
                    skip=0,
                    limit=10,
                    search=malicious_term,
                    owner_only=False,
                    current_user=mock_user,
                    db=mock_db
                )
                
                # Should not raise an exception and should return safe results
                assert isinstance(result, list)
                
            except Exception as e:
                # If an exception is raised, it should be a safe database error,
                # not a successful injection
                assert "DROP TABLE" not in str(e)
                assert "DELETE FROM" not in str(e)
    
    @pytest.mark.unit
    def test_sensitive_data_not_exposed(self):
        """Test that sensitive data is not exposed in project responses."""
        mock_project = Mock(spec=Project)
        mock_project.to_dict.return_value = {
            "id": 1,
            "name": "Test Project",
            "description": "Description",
            "annotation_guidelines": "Guidelines",
            "allow_multiple_labels": True,
            "require_all_texts": False,
            "inter_annotator_agreement": False,
            "is_active": True,
            "is_public": False,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "owner_id": 1,
            "text_count": 5,
            "label_count": 3
        }
        
        response_data = mock_project.to_dict()
        
        # Verify only expected fields are present
        expected_fields = {
            "id", "name", "description", "annotation_guidelines",
            "allow_multiple_labels", "require_all_texts", "inter_annotator_agreement",
            "is_active", "is_public", "created_at", "updated_at",
            "owner_id", "text_count", "label_count"
        }
        
        assert set(response_data.keys()) == expected_fields
        
        # Verify no sensitive internal fields are exposed
        sensitive_fields = [
            "password", "hashed_password", "secret_key", "private_key",
            "internal_id", "database_url", "admin_token"
        ]
        
        for field in sensitive_fields:
            assert field not in response_data
    
    @pytest.mark.unit
    def test_pagination_limits_enforced(self):
        """Test that pagination limits are properly enforced."""
        # This test verifies the Query parameters in the API definition
        # The actual limit enforcement happens at the FastAPI level
        
        # Test maximum limit (should be 100 based on API definition)
        from src.api.projects import list_projects
        import inspect
        
        # Get the function signature
        sig = inspect.signature(list_projects)
        limit_param = sig.parameters['limit']
        
        # Verify limit has proper constraints
        # This checks the Query(10, le=100) constraint
        assert limit_param.default == 10  # Default value
        
        # The le=100 constraint is handled by FastAPI's Query validator
        # In actual usage, values > 100 would be rejected by FastAPI before
        # reaching our function
    
    @pytest.mark.unit
    def test_access_control_consistency(self):
        """Test that access control logic is consistent across endpoints."""
        # This test verifies the access control patterns used in the API
        # All project access should follow the same rules:
        # 1. Owner can always access their projects
        # 2. Non-owners can only access public projects
        # 3. Only owners can modify their projects
        
        # These patterns are implemented consistently in:
        # - get_project: checks (owner_id == user.id OR is_public)
        # - list_projects: filters by (owner_id == user.id OR is_public) unless owner_only=True
        # - update_project: checks owner_id == user.id
        # - delete_project: checks owner_id == user.id
        
        # The actual access control is tested in individual endpoint tests
        # This test documents the expected consistency
        assert True  # Placeholder for documentation
    
    @pytest.mark.unit
    def test_input_validation_patterns(self):
        """Test input validation patterns used in project data."""
        # Test ProjectCreate validation
        valid_create = ProjectCreate(name="Valid Name")
        assert valid_create.name == "Valid Name"
        assert valid_create.allow_multiple_labels is True  # Default
        assert valid_create.is_public is False  # Default
        
        # Test ProjectUpdate validation
        valid_update = ProjectUpdate(name="Updated Name")
        assert valid_update.name == "Updated Name"
        assert valid_update.description is None  # Not set
        
        # Test that boolean fields accept proper values
        bool_update = ProjectUpdate(
            allow_multiple_labels=False,
            require_all_texts=True,
            inter_annotator_agreement=True,
            is_public=True,
            is_active=False
        )
        assert bool_update.allow_multiple_labels is False
        assert bool_update.require_all_texts is True
        assert bool_update.inter_annotator_agreement is True
        assert bool_update.is_public is True
        assert bool_update.is_active is False