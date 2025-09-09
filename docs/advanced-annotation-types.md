# Advanced Annotation Types - Technical Specification

## Overview
This document details the implementation of advanced annotation types including relations, hierarchical annotations, overlapping spans, and structured attributes to support complex academic research workflows.

## 1. Relation Annotations

### Database Schema
```sql
CREATE TABLE relations (
    id SERIAL PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
    source_annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    target_annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    relation_type VARCHAR(100) NOT NULL,
    relation_label VARCHAR(200),
    confidence_score FLOAT DEFAULT 1.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    directional BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    annotator_id INTEGER NOT NULL REFERENCES users(id),
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'approved', 'rejected')),
    validation_notes TEXT,
    validated_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_relation UNIQUE(source_annotation_id, target_annotation_id, relation_type),
    CONSTRAINT no_self_relation CHECK (source_annotation_id != target_annotation_id)
);

CREATE TABLE relation_types (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_directional BOOLEAN DEFAULT TRUE,
    allowed_source_labels JSONB DEFAULT '[]',
    allowed_target_labels JSONB DEFAULT '[]',
    color VARCHAR(7) DEFAULT '#007bff',
    visualization_style JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_relation_type_per_project UNIQUE(project_id, name)
);

-- Indexes for performance
CREATE INDEX idx_relations_text_id ON relations(text_id);
CREATE INDEX idx_relations_source_annotation ON relations(source_annotation_id);
CREATE INDEX idx_relations_target_annotation ON relations(target_annotation_id);
CREATE INDEX idx_relations_type ON relations(relation_type);
CREATE INDEX idx_relation_types_project ON relation_types(project_id);
```

### API Models
```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class RelationTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_directional: bool = True
    allowed_source_labels: List[int] = []
    allowed_target_labels: List[int] = []
    color: str = Field('#007bff', regex=r'^#[0-9A-Fa-f]{6}$')
    visualization_style: Dict[str, Any] = {}

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

class RelationCreate(BaseModel):
    source_annotation_id: int
    target_annotation_id: int
    relation_type_id: int
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = {}

    @validator('source_annotation_id')
    def validate_different_annotations(cls, v, values):
        if 'target_annotation_id' in values and v == values['target_annotation_id']:
            raise ValueError('Source and target annotations must be different')
        return v

class RelationResponse(BaseModel):
    id: int
    text_id: int
    source_annotation_id: int
    target_annotation_id: int
    relation_type: str
    relation_label: Optional[str]
    confidence_score: float
    directional: bool
    metadata: Dict[str, Any]
    validation_status: str
    validation_notes: Optional[str]
    annotator_id: int
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    source_annotation: Optional[Dict[str, Any]] = None
    target_annotation: Optional[Dict[str, Any]] = None
    annotator_username: Optional[str] = None
```

### API Endpoints
```python
@router.post("/relations", response_model=RelationResponse)
async def create_relation(
    relation_data: RelationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new relation between annotations."""
    
    # Validate both annotations exist and belong to same text
    source_annotation = db.query(Annotation).filter(
        Annotation.id == relation_data.source_annotation_id
    ).first()
    target_annotation = db.query(Annotation).filter(
        Annotation.id == relation_data.target_annotation_id
    ).first()
    
    if not source_annotation or not target_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    if source_annotation.text_id != target_annotation.text_id:
        raise HTTPException(
            status_code=400, 
            detail="Annotations must belong to the same text"
        )
    
    # Check access permissions
    text = source_annotation.text
    if not await check_project_access(text.project, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate relation type
    relation_type = db.query(RelationType).filter(
        RelationType.id == relation_data.relation_type_id,
        RelationType.project_id == text.project_id,
        RelationType.is_active == True
    ).first()
    
    if not relation_type:
        raise HTTPException(status_code=404, detail="Relation type not found")
    
    # Validate label compatibility
    if (relation_type.allowed_source_labels and 
        source_annotation.label_id not in relation_type.allowed_source_labels):
        raise HTTPException(
            status_code=400,
            detail="Source annotation label not allowed for this relation type"
        )
    
    if (relation_type.allowed_target_labels and 
        target_annotation.label_id not in relation_type.allowed_target_labels):
        raise HTTPException(
            status_code=400,
            detail="Target annotation label not allowed for this relation type"
        )
    
    # Check for duplicate relations
    existing = db.query(Relation).filter(
        Relation.source_annotation_id == relation_data.source_annotation_id,
        Relation.target_annotation_id == relation_data.target_annotation_id,
        Relation.relation_type == relation_type.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Relation already exists")
    
    # Create relation
    relation = Relation(
        text_id=text.id,
        source_annotation_id=relation_data.source_annotation_id,
        target_annotation_id=relation_data.target_annotation_id,
        relation_type=relation_type.name,
        relation_label=relation_type.name,
        confidence_score=relation_data.confidence_score,
        directional=relation_type.is_directional,
        metadata=relation_data.metadata,
        annotator_id=current_user.id
    )
    
    db.add(relation)
    relation_type.usage_count += 1
    db.commit()
    db.refresh(relation)
    
    return await build_relation_response(relation, db)
```

## 2. Hierarchical and Overlapping Annotations

### Database Schema
```sql
CREATE TABLE annotation_hierarchy (
    id SERIAL PRIMARY KEY,
    parent_annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    child_annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    hierarchy_type VARCHAR(50) NOT NULL CHECK (hierarchy_type IN ('contains', 'part_of', 'depends_on', 'modifies')),
    hierarchy_level INTEGER NOT NULL DEFAULT 1,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_hierarchy UNIQUE(parent_annotation_id, child_annotation_id),
    CONSTRAINT no_self_hierarchy CHECK (parent_annotation_id != child_annotation_id)
);

CREATE TABLE overlapping_annotations (
    id SERIAL PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
    annotation_ids INTEGER[] NOT NULL,
    overlap_type VARCHAR(50) NOT NULL CHECK (overlap_type IN ('partial', 'complete', 'nested', 'crossing')),
    overlap_spans JSONB NOT NULL, -- [{start: 10, end: 20, annotation_ids: [1,2]}]
    conflict_resolution JSONB DEFAULT '{}',
    resolution_strategy VARCHAR(50) CHECK (resolution_strategy IN ('merge', 'prioritize', 'split', 'manual')),
    resolved_by INTEGER REFERENCES users(id),
    resolution_date TIMESTAMP,
    auto_detected BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT minimum_two_annotations CHECK (array_length(annotation_ids, 1) >= 2)
);

-- Complex function to detect overlaps
CREATE OR REPLACE FUNCTION detect_annotation_overlaps(text_id_param INTEGER)
RETURNS TABLE(annotation_ids INTEGER[], overlap_type VARCHAR, overlap_spans JSONB) AS $$
DECLARE
    annotation_record RECORD;
    other_annotation RECORD;
    overlaps INTEGER[];
    overlap_data JSONB;
BEGIN
    FOR annotation_record IN 
        SELECT id, start_char, end_char FROM annotations 
        WHERE text_id = text_id_param 
        ORDER BY start_char
    LOOP
        overlaps := ARRAY[]::INTEGER[];
        
        FOR other_annotation IN
            SELECT id, start_char, end_char FROM annotations
            WHERE text_id = text_id_param 
            AND id != annotation_record.id
            AND (
                (start_char < annotation_record.end_char AND end_char > annotation_record.start_char)
            )
        LOOP
            overlaps := array_append(overlaps, other_annotation.id);
        END LOOP;
        
        IF array_length(overlaps, 1) > 0 THEN
            overlaps := array_prepend(annotation_record.id, overlaps);
            
            -- Determine overlap type
            -- Implementation for overlap type detection...
            
            RETURN QUERY SELECT overlaps, 'partial'::VARCHAR, '{}'::JSONB;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### Overlap Detection Algorithm
```python
from typing import List, Tuple, Dict, Set
from dataclasses import dataclass
from enum import Enum

class OverlapType(Enum):
    PARTIAL = "partial"
    COMPLETE = "complete"
    NESTED = "nested"
    CROSSING = "crossing"

@dataclass
class AnnotationSpan:
    id: int
    start: int
    end: int
    label_id: int
    annotator_id: int

@dataclass
class OverlapRegion:
    start: int
    end: int
    annotation_ids: Set[int]
    overlap_type: OverlapType

class OverlapDetector:
    """Detects and classifies overlapping annotations."""
    
    def detect_overlaps(self, annotations: List[AnnotationSpan]) -> List[OverlapRegion]:
        """Detect all overlapping regions in a list of annotations."""
        overlaps = []
        
        # Sort annotations by start position
        sorted_annotations = sorted(annotations, key=lambda a: a.start)
        
        for i, ann1 in enumerate(sorted_annotations):
            for j, ann2 in enumerate(sorted_annotations[i+1:], i+1):
                if ann2.start >= ann1.end:
                    break  # No more overlaps for ann1
                
                overlap_type = self._classify_overlap(ann1, ann2)
                if overlap_type:
                    overlap_start = max(ann1.start, ann2.start)
                    overlap_end = min(ann1.end, ann2.end)
                    
                    overlaps.append(OverlapRegion(
                        start=overlap_start,
                        end=overlap_end,
                        annotation_ids={ann1.id, ann2.id},
                        overlap_type=overlap_type
                    ))
        
        # Merge overlapping regions that involve the same annotations
        return self._merge_adjacent_overlaps(overlaps)
    
    def _classify_overlap(self, ann1: AnnotationSpan, ann2: AnnotationSpan) -> OverlapType:
        """Classify the type of overlap between two annotations."""
        if ann1.end <= ann2.start or ann2.end <= ann1.start:
            return None  # No overlap
        
        # Complete overlap (one annotation completely contains the other)
        if ann1.start <= ann2.start and ann1.end >= ann2.end:
            return OverlapType.COMPLETE
        if ann2.start <= ann1.start and ann2.end >= ann1.end:
            return OverlapType.COMPLETE
        
        # Nested overlap (one is completely inside the other)
        if (ann1.start > ann2.start and ann1.end < ann2.end) or \
           (ann2.start > ann1.start and ann2.end < ann1.end):
            return OverlapType.NESTED
        
        # Crossing overlap (annotations cross each other's boundaries)
        if (ann1.start < ann2.start < ann1.end < ann2.end) or \
           (ann2.start < ann1.start < ann2.end < ann1.end):
            return OverlapType.CROSSING
        
        # Default to partial overlap
        return OverlapType.PARTIAL
    
    def _merge_adjacent_overlaps(self, overlaps: List[OverlapRegion]) -> List[OverlapRegion]:
        """Merge adjacent overlaps involving the same annotations."""
        if not overlaps:
            return []
        
        merged = []
        current_overlap = overlaps[0]
        
        for next_overlap in overlaps[1:]:
            # Check if overlaps are adjacent and involve same annotations
            if (current_overlap.end == next_overlap.start and
                current_overlap.annotation_ids == next_overlap.annotation_ids):
                # Merge overlaps
                current_overlap.end = next_overlap.end
            else:
                merged.append(current_overlap)
                current_overlap = next_overlap
        
        merged.append(current_overlap)
        return merged
```

## 3. Structured Annotation Attributes

### Database Schema
```sql
CREATE TABLE attribute_templates (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label_id INTEGER REFERENCES labels(id) ON DELETE CASCADE, -- NULL means applies to all labels
    template_name VARCHAR(100) NOT NULL,
    attribute_schema JSONB NOT NULL, -- JSON Schema definition
    ui_configuration JSONB DEFAULT '{}', -- UI rendering instructions
    is_required BOOLEAN DEFAULT FALSE,
    validation_rules JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_template_per_project_label UNIQUE(project_id, label_id, template_name)
);

CREATE TABLE annotation_attributes (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES attribute_templates(id) ON DELETE SET NULL,
    attribute_name VARCHAR(100) NOT NULL,
    attribute_value JSONB NOT NULL,
    attribute_type VARCHAR(50) NOT NULL CHECK (attribute_type IN ('text', 'number', 'boolean', 'list', 'date', 'json')),
    is_validated BOOLEAN DEFAULT FALSE,
    validation_errors JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_attribute_per_annotation UNIQUE(annotation_id, attribute_name)
);

-- Indexes
CREATE INDEX idx_annotation_attributes_annotation ON annotation_attributes(annotation_id);
CREATE INDEX idx_annotation_attributes_name ON annotation_attributes(attribute_name);
CREATE INDEX idx_attribute_templates_project ON attribute_templates(project_id);
CREATE INDEX idx_attribute_templates_label ON attribute_templates(label_id);
```

### Attribute Schema Validation
```python
import jsonschema
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator

class AttributeTemplateCreate(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=100)
    label_id: Optional[int] = None
    attribute_schema: Dict[str, Any] = Field(..., description="JSON Schema for validation")
    ui_configuration: Dict[str, Any] = {}
    is_required: bool = False
    validation_rules: Dict[str, Any] = {}

    @validator('attribute_schema')
    def validate_schema(cls, v):
        """Validate that the schema is a valid JSON Schema."""
        try:
            # Basic JSON Schema validation
            jsonschema.validators.Draft7Validator.check_schema(v)
            return v
        except jsonschema.exceptions.SchemaError as e:
            raise ValueError(f"Invalid JSON Schema: {str(e)}")

class AttributeValidator:
    """Validates annotation attributes against templates."""
    
    def __init__(self):
        self.validator_cache = {}
    
    def validate_attribute(
        self, 
        template: 'AttributeTemplate', 
        attribute_value: Any
    ) -> Tuple[bool, List[str]]:
        """Validate an attribute value against its template."""
        
        # Get or create validator
        template_key = f"template_{template.id}"
        if template_key not in self.validator_cache:
            self.validator_cache[template_key] = jsonschema.Draft7Validator(
                template.attribute_schema
            )
        
        validator = self.validator_cache[template_key]
        errors = []
        
        # Perform JSON Schema validation
        for error in validator.iter_errors(attribute_value):
            errors.append(f"{'.'.join(str(p) for p in error.path)}: {error.message}")
        
        # Additional custom validation rules
        if template.validation_rules:
            custom_errors = self._apply_custom_validation(
                attribute_value, 
                template.validation_rules
            )
            errors.extend(custom_errors)
        
        return len(errors) == 0, errors
    
    def _apply_custom_validation(self, value: Any, rules: Dict[str, Any]) -> List[str]:
        """Apply custom validation rules."""
        errors = []
        
        # String length validation
        if isinstance(value, str) and 'min_length' in rules:
            if len(value) < rules['min_length']:
                errors.append(f"Must be at least {rules['min_length']} characters")
        
        # Numeric range validation  
        if isinstance(value, (int, float)):
            if 'min_value' in rules and value < rules['min_value']:
                errors.append(f"Must be at least {rules['min_value']}")
            if 'max_value' in rules and value > rules['max_value']:
                errors.append(f"Must be at most {rules['max_value']}")
        
        # Regular expression validation
        if isinstance(value, str) and 'pattern' in rules:
            import re
            if not re.match(rules['pattern'], value):
                errors.append(f"Must match pattern: {rules['pattern']}")
        
        return errors

# Example attribute templates
EXAMPLE_TEMPLATES = {
    "sentiment_analysis": {
        "template_name": "Sentiment Analysis",
        "attribute_schema": {
            "type": "object",
            "properties": {
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral"]
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "aspects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "aspect": {"type": "string"},
                            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["aspect", "sentiment"]
                    }
                }
            },
            "required": ["sentiment"]
        },
        "ui_configuration": {
            "sentiment": {"type": "radio", "layout": "horizontal"},
            "confidence": {"type": "slider", "step": 0.1},
            "aspects": {"type": "dynamic_list", "add_button_text": "Add Aspect"}
        }
    },
    
    "named_entity": {
        "template_name": "Named Entity Attributes",
        "attribute_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["PERSON", "ORGANIZATION", "LOCATION", "DATE", "MONEY", "PERCENT"]
                },
                "normalization": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "disambiguation": {
                    "type": "object",
                    "properties": {
                        "wikidata_id": {"type": "string"},
                        "description": {"type": "string"}
                    }
                }
            },
            "required": ["entity_type"]
        },
        "ui_configuration": {
            "entity_type": {"type": "dropdown"},
            "normalization": {"type": "text", "placeholder": "Canonical form"},
            "confidence": {"type": "slider", "step": 0.1},
            "disambiguation": {"type": "collapsible_section", "title": "Disambiguation"}
        }
    }
}
```

## API Integration Examples

### Creating Complex Annotations
```python
@router.post("/annotations/complex")
async def create_complex_annotation(
    annotation_data: ComplexAnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create annotation with attributes, relations, and hierarchy."""
    
    # Create base annotation
    annotation = await create_base_annotation(annotation_data.base, current_user, db)
    
    # Add attributes
    if annotation_data.attributes:
        await add_annotation_attributes(annotation.id, annotation_data.attributes, db)
    
    # Create relations
    if annotation_data.relations:
        for relation_data in annotation_data.relations:
            await create_relation(relation_data, current_user, db)
    
    # Set up hierarchy
    if annotation_data.parent_id:
        await create_hierarchy_link(annotation_data.parent_id, annotation.id, db)
    
    # Detect and handle overlaps
    overlaps = await detect_overlaps_for_text(annotation.text_id, db)
    if overlaps:
        await handle_overlap_conflicts(overlaps, db)
    
    return await get_full_annotation_response(annotation.id, db)
```

This comprehensive system enables rich, structured annotations suitable for complex academic research requirements while maintaining performance and data integrity.