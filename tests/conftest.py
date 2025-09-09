"""
Pytest Configuration and Fixtures

Provides reusable fixtures for testing the text annotation system.
"""

import asyncio
import os
import pytest
import tempfile
from typing import Generator, AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import Mock

# Set test environment variables
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ALGORITHM"] = "HS256"

from src.main import app
from src.core.database import get_db, Base
from src.core.security import create_access_token
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.annotation import Annotation
from src.models.label import Label


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///test.db", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_client(test_db):
    """Create test client with database dependency override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Provide test user data."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User"
    }


@pytest.fixture
def test_user(test_db, test_user_data):
    """Create a test user in database."""
    from src.core.security import get_password_hash
    
    user = User(
        username=test_user_data["username"],
        email=test_user_data["email"],
        hashed_password=get_password_hash(test_user_data["password"]),
        full_name=test_user_data["full_name"],
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_admin_user(test_db):
    """Create a test admin user."""
    from src.core.security import get_password_hash
    
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPassword123!"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user."""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user):
    """Create authentication headers for admin user."""
    token = create_access_token(subject=test_admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_project_data():
    """Provide test project data."""
    return {
        "name": "Test Project",
        "description": "A test project for annotation",
        "annotation_guidelines": "Test guidelines for annotation"
    }


@pytest.fixture
def test_project(test_db, test_user, test_project_data):
    """Create a test project in database."""
    project = Project(
        name=test_project_data["name"],
        description=test_project_data["description"],
        annotation_guidelines=test_project_data["annotation_guidelines"],
        owner_id=test_user.id
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def test_text_data():
    """Provide test text data."""
    return {
        "title": "Test Document",
        "content": "This is a sample text document for testing annotation features. It contains multiple sentences and paragraphs for comprehensive testing.",
        "source_type": "manual"
    }


@pytest.fixture
def test_text(test_db, test_project, test_text_data):
    """Create a test text document in database."""
    text = Text(
        title=test_text_data["title"],
        content=test_text_data["content"],
        source_type=test_text_data["source_type"],
        project_id=test_project.id
    )
    test_db.add(text)
    test_db.commit()
    test_db.refresh(text)
    return text


@pytest.fixture
def test_label_data():
    """Provide test label data."""
    return {
        "name": "Important",
        "description": "Mark important passages",
        "color": "#FF5733"
    }


@pytest.fixture
def test_label(test_db, test_project, test_label_data):
    """Create a test label in database."""
    label = Label(
        name=test_label_data["name"],
        description=test_label_data["description"],
        color=test_label_data["color"],
        project_id=test_project.id
    )
    test_db.add(label)
    test_db.commit()
    test_db.refresh(label)
    return label


@pytest.fixture
def test_annotation_data():
    """Provide test annotation data."""
    return {
        "start_char": 10,
        "end_char": 25,
        "selected_text": "sample text",
        "comment": "This is a test annotation"
    }


@pytest.fixture
def test_annotation(test_db, test_text, test_user, test_label, test_annotation_data):
    """Create a test annotation in database."""
    annotation = Annotation(
        start_char=test_annotation_data["start_char"],
        end_char=test_annotation_data["end_char"],
        selected_text=test_annotation_data["selected_text"],
        comment=test_annotation_data["comment"],
        text_id=test_text.id,
        user_id=test_user.id,
        label_id=test_label.id
    )
    test_db.add(annotation)
    test_db.commit()
    test_db.refresh(annotation)
    return annotation


@pytest.fixture
def temp_file():
    """Create a temporary file for testing file operations."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
    temp_file.write("This is a temporary file for testing purposes.")
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    try:
        os.unlink(temp_file.name)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_file_upload():
    """Mock file upload for testing."""
    return Mock(
        filename="test_document.txt",
        content_type="text/plain",
        read=Mock(return_value=b"This is test file content for upload testing.")
    )


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Database cleanup fixture
@pytest.fixture(autouse=True)
def cleanup_database(test_db):
    """Clean up database after each test."""
    yield
    # Clean up all tables in reverse order of dependencies
    test_db.query(Annotation).delete()
    test_db.query(Label).delete()
    test_db.query(Text).delete()
    test_db.query(Project).delete()
    test_db.query(User).delete()
    test_db.commit()


# Performance testing fixture
@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Test data generators
@pytest.fixture
def generate_test_users():
    """Generate multiple test users."""
    def _generate_users(count=5):
        users = []
        for i in range(count):
            users.append({
                "username": f"testuser{i}",
                "email": f"test{i}@example.com",
                "password": f"Password{i}123!",
                "full_name": f"Test User {i}"
            })
        return users
    return _generate_users


@pytest.fixture
def generate_test_annotations():
    """Generate multiple test annotations."""
    def _generate_annotations(text_content, count=10):
        annotations = []
        content_len = len(text_content)
        step = max(1, content_len // count)
        
        for i in range(count):
            start = i * step
            end = min(start + 10, content_len)
            if start < end:
                annotations.append({
                    "start_char": start,
                    "end_char": end,
                    "selected_text": text_content[start:end],
                    "comment": f"Test annotation {i+1}"
                })
        return annotations
    return _generate_annotations