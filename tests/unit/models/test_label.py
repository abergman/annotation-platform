"""
Unit Tests for Label Model

Tests the Label model functionality including validation, relationships, hierarchical structure, and methods.
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.models.label import Label


class TestLabelModel:
    """Test cases for Label model."""

    @pytest.mark.unit
    def test_create_label(self, test_db, test_project):
        """Test creating a new label."""
        label = Label(
            name="Important",
            description="Mark important passages",
            color="#FF5733",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.id is not None
        assert label.name == "Important"
        assert label.description == "Mark important passages"
        assert label.color == "#FF5733"
        assert label.project_id == test_project.id
        assert label.is_active is True  # Default value
        assert label.order_index == 0  # Default value
        assert label.usage_count == 0  # Default value
        assert label.created_at is not None
        assert isinstance(label.created_at, datetime)

    @pytest.mark.unit
    def test_label_required_fields(self, test_db, test_project):
        """Test label with only required fields."""
        label = Label(
            name="Minimal Label",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.name == "Minimal Label"
        assert label.description is None
        assert label.color == "#007bff"  # Default color
        assert label.project_id == test_project.id

    @pytest.mark.unit
    def test_label_project_relationship(self, test_db, test_project):
        """Test label-project relationship."""
        label = Label(
            name="Relationship Test",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        # Test forward relationship
        assert label.project.id == test_project.id
        assert label.project.name == test_project.name

        # Test backward relationship
        assert label in test_project.labels

    @pytest.mark.unit
    def test_label_to_dict_basic(self, test_label):
        """Test label to_dict method without children."""
        label_dict = test_label.to_dict(include_children=False)
        
        required_fields = [
            "id", "name", "description", "color", "icon", "parent_id",
            "order_index", "is_active", "shortcut_key", "metadata",
            "usage_count", "created_at", "updated_at", "project_id",
            "annotation_count"
        ]
        
        for field in required_fields:
            assert field in label_dict
        
        assert isinstance(label_dict["id"], int)
        assert isinstance(label_dict["is_active"], bool)
        assert isinstance(label_dict["order_index"], int)
        assert isinstance(label_dict["usage_count"], int)
        assert isinstance(label_dict["annotation_count"], int)

    @pytest.mark.unit
    def test_label_repr(self, test_label):
        """Test label string representation."""
        repr_str = repr(test_label)
        assert "Label" in repr_str
        assert str(test_label.id) in repr_str
        assert test_label.name in repr_str
        assert str(test_label.project_id) in repr_str

    @pytest.mark.unit
    def test_label_hierarchical_structure(self, test_db, test_project):
        """Test hierarchical label structure."""
        # Create parent label
        parent_label = Label(
            name="Category",
            description="Main category",
            project_id=test_project.id
        )
        test_db.add(parent_label)
        test_db.commit()
        test_db.refresh(parent_label)

        # Create child label
        child_label = Label(
            name="Subcategory",
            description="Sub category",
            parent_id=parent_label.id,
            project_id=test_project.id
        )
        test_db.add(child_label)
        test_db.commit()
        test_db.refresh(child_label)

        # Test relationships
        assert child_label.parent.id == parent_label.id
        assert child_label in parent_label.children

    @pytest.mark.unit
    def test_label_to_dict_with_children(self, test_db, test_project):
        """Test label to_dict method with children included."""
        # Create parent with children
        parent = Label(
            name="Parent Category",
            project_id=test_project.id
        )
        test_db.add(parent)
        test_db.commit()
        test_db.refresh(parent)

        child = Label(
            name="Child Category",
            parent_id=parent.id,
            project_id=test_project.id
        )
        test_db.add(child)
        test_db.commit()
        test_db.refresh(parent)  # Refresh to get children

        parent_dict = parent.to_dict(include_children=True)
        
        assert "children" in parent_dict
        assert isinstance(parent_dict["children"], list)
        assert len(parent_dict["children"]) == 1
        assert parent_dict["children"][0]["name"] == "Child Category"

    @pytest.mark.unit
    def test_label_color_validation(self, test_db, test_project):
        """Test label color formats."""
        # Valid hex colors
        valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#000000"]
        
        for color in valid_colors:
            label = Label(
                name=f"Color {color}",
                color=color,
                project_id=test_project.id
            )
            test_db.add(label)
            test_db.commit()
            test_db.refresh(label)
            
            assert label.color == color

    @pytest.mark.unit
    def test_label_shortcut_key(self, test_db, test_project):
        """Test label shortcut key functionality."""
        label = Label(
            name="Shortcut Label",
            shortcut_key="Ctrl+I",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.shortcut_key == "Ctrl+I"

    @pytest.mark.unit
    def test_label_icon(self, test_db, test_project):
        """Test label icon functionality."""
        label = Label(
            name="Icon Label",
            icon="star",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.icon == "star"

    @pytest.mark.unit
    def test_label_order_index(self, test_db, test_project):
        """Test label ordering functionality."""
        labels = []
        for i in range(5):
            label = Label(
                name=f"Label {i}",
                order_index=i,
                project_id=test_project.id
            )
            test_db.add(label)
            labels.append(label)
        
        test_db.commit()
        
        for i, label in enumerate(labels):
            test_db.refresh(label)
            assert label.order_index == i

    @pytest.mark.unit
    def test_label_metadata(self, test_db, test_project):
        """Test label metadata functionality."""
        metadata = {
            "category_type": "entity",
            "confidence_threshold": 0.8,
            "auto_suggest": True
        }
        
        label = Label(
            name="Metadata Label",
            metadata=metadata,
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.metadata == metadata
        assert label.metadata["category_type"] == "entity"

    @pytest.mark.unit
    def test_label_usage_tracking(self, test_db, test_project):
        """Test label usage count tracking."""
        label = Label(
            name="Usage Label",
            usage_count=0,
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.usage_count == 0

        # Simulate usage
        label.usage_count += 1
        test_db.commit()
        test_db.refresh(label)

        assert label.usage_count == 1

    @pytest.mark.unit
    def test_label_active_status(self, test_db, test_project):
        """Test label active/inactive status."""
        label = Label(
            name="Status Label",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()

        assert label.is_active is True

        # Deactivate label
        label.is_active = False
        test_db.commit()
        test_db.refresh(label)

        assert label.is_active is False

    @pytest.mark.unit
    def test_label_timestamps(self, test_db, test_project):
        """Test label timestamp functionality."""
        label = Label(
            name="Timestamp Label",
            description="Original description",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)
        
        created_at = label.created_at
        updated_at = label.updated_at

        # Update label
        label.description = "Updated description"
        test_db.commit()
        test_db.refresh(label)

        assert label.created_at == created_at  # Should not change
        assert label.updated_at > updated_at  # Should be updated

    @pytest.mark.unit
    def test_label_foreign_key_constraint(self, test_db):
        """Test foreign key constraint for project_id."""
        label = Label(
            name="Invalid Project Label",
            project_id=99999  # Non-existent project ID
        )
        test_db.add(label)
        
        with pytest.raises(IntegrityError):
            test_db.commit()

    @pytest.mark.unit
    def test_label_hierarchical_foreign_key(self, test_db, test_project):
        """Test hierarchical foreign key constraint."""
        # Test with invalid parent_id
        label = Label(
            name="Invalid Parent Label",
            parent_id=99999,  # Non-existent parent ID
            project_id=test_project.id
        )
        test_db.add(label)
        
        with pytest.raises(IntegrityError):
            test_db.commit()

    @pytest.mark.unit
    def test_label_deep_hierarchy(self, test_db, test_project):
        """Test deep hierarchical structure."""
        # Create 3-level hierarchy
        level1 = Label(name="Level 1", project_id=test_project.id)
        test_db.add(level1)
        test_db.commit()
        test_db.refresh(level1)

        level2 = Label(name="Level 2", parent_id=level1.id, project_id=test_project.id)
        test_db.add(level2)
        test_db.commit()
        test_db.refresh(level2)

        level3 = Label(name="Level 3", parent_id=level2.id, project_id=test_project.id)
        test_db.add(level3)
        test_db.commit()
        test_db.refresh(level3)

        # Test relationships
        assert level3.parent.id == level2.id
        assert level2.parent.id == level1.id
        assert level1.parent is None

    @pytest.mark.unit
    def test_label_default_values(self, test_db, test_project):
        """Test default values for label fields."""
        label = Label(
            name="Default Label",
            project_id=test_project.id
        )
        test_db.add(label)
        test_db.commit()
        test_db.refresh(label)

        assert label.color == "#007bff"
        assert label.is_active is True
        assert label.order_index == 0
        assert label.usage_count == 0
        assert label.metadata == {}
        assert label.created_at is not None
        assert label.updated_at is not None

    @pytest.mark.unit
    def test_label_name_uniqueness_per_project(self, test_db, test_user, test_project):
        """Test label name uniqueness within a project."""
        # Create first label
        label1 = Label(
            name="Duplicate Name",
            project_id=test_project.id
        )
        test_db.add(label1)
        test_db.commit()

        # Create another project
        from src.models.project import Project
        project2 = Project(
            name="Another Project",
            owner_id=test_user.id
        )
        test_db.add(project2)
        test_db.commit()
        test_db.refresh(project2)

        # Same name in different project should be allowed
        label2 = Label(
            name="Duplicate Name",
            project_id=project2.id
        )
        test_db.add(label2)
        test_db.commit()

        assert label1.name == label2.name
        assert label1.project_id != label2.project_id