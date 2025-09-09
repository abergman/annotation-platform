# Text Annotation System - Enhanced Architecture Design

## Executive Summary

This document outlines comprehensive improvements to the existing text annotation system, focusing on enhanced collaboration, advanced annotation types, quality metrics, and ML/AI integration capabilities for academic research workflows.

## Current System Analysis

### Architecture Overview
- **Backend**: FastAPI with SQLAlchemy ORM
- **Database**: PostgreSQL with Alembic migrations
- **Authentication**: JWT-based with bcrypt password hashing
- **API Design**: RESTful with OpenAPI documentation

### Key Models
1. **User**: Authentication and profile management
2. **Project**: Organization and access control
3. **Text**: Document storage and metadata
4. **Annotation**: Text span annotations with labels
5. **Label**: Hierarchical categorization system

### Current Limitations
- No real-time collaboration capabilities
- Basic annotation types (span-only)
- No inter-annotator agreement calculations
- Limited quality assessment metrics
- Basic export formats only
- No integration with NLP tools

## Enhanced System Architecture

### 1. Enhanced Collaboration Features

#### A. Team Management System
```
Teams (New Model)
├── id (Primary Key)
├── name (Team name)
├── description (Team purpose)
├── project_id (Foreign Key)
├── created_by (User FK)
├── team_settings (JSON)
│   ├── annotation_conflicts_resolution
│   ├── validation_workflow_type
│   ├── consensus_threshold
│   └── auto_assignment_rules
└── created_at, updated_at

TeamMemberships (New Model)
├── id (Primary Key)  
├── team_id (Foreign Key)
├── user_id (Foreign Key)
├── role (annotator, validator, admin)
├── permissions (JSON)
├── annotation_quota (Integer)
└── joined_at
```

#### B. Assignment and Workflow Management
```
AnnotationTasks (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── assigned_to (User FK)
├── assigned_by (User FK)
├── deadline (DateTime)
├── priority (low, medium, high)
├── status (pending, in_progress, completed, reviewed)
├── completion_percentage (Float)
├── estimated_hours (Float)
├── actual_hours (Float)
└── metadata (JSON)

WorkflowSteps (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── step_name (String)
├── step_order (Integer)
├── required_role (String)
├── validation_rules (JSON)
├── auto_advance (Boolean)
└── step_configuration (JSON)
```

#### C. Communication and Discussion System
```
AnnotationComments (New Model)
├── id (Primary Key)
├── annotation_id (Foreign Key)
├── author_id (User FK)
├── comment_text (Text)
├── comment_type (question, suggestion, clarification)
├── is_resolved (Boolean)
├── parent_comment_id (Self FK for threading)
└── created_at, updated_at

ProjectDiscussions (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── title (String)
├── description (Text)
├── created_by (User FK)
├── discussion_type (general, guidelines, quality)
├── is_pinned (Boolean)
└── created_at, updated_at
```

### 2. Advanced Annotation Types

#### A. Relation Annotations
```
Relations (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── source_annotation_id (Annotation FK)
├── target_annotation_id (Annotation FK)
├── relation_type (String)
├── relation_label (String)
├── confidence_score (Float)
├── directional (Boolean)
├── metadata (JSON)
├── annotator_id (User FK)
├── validation_status (String)
└── created_at, updated_at

RelationTypes (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── name (String)
├── description (Text)
├── is_directional (Boolean)
├── allowed_source_labels (JSON Array)
├── allowed_target_labels (JSON Array)
├── color (String)
├── visualization_style (JSON)
└── created_at, updated_at
```

#### B. Hierarchical and Nested Annotations
```
AnnotationHierarchy (New Model)
├── id (Primary Key)
├── parent_annotation_id (Annotation FK)
├── child_annotation_id (Annotation FK)
├── hierarchy_type (contains, part_of, depends_on)
├── hierarchy_level (Integer)
└── created_at

OverlappingAnnotations (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── annotation_ids (JSON Array)
├── overlap_type (partial, complete, nested)
├── conflict_resolution (JSON)
├── resolved_by (User FK)
└── resolution_date
```

#### C. Structured Annotation Attributes
```
AnnotationAttributes (New Model)
├── id (Primary Key)
├── annotation_id (Foreign Key)
├── attribute_name (String)
├── attribute_value (JSON)
├── attribute_type (text, number, boolean, list, date)
├── is_required (Boolean)
├── validation_rules (JSON)
└── created_at, updated_at

AttributeTemplates (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── label_id (Foreign Key, nullable)
├── template_name (String)
├── attribute_schema (JSON)
├── ui_configuration (JSON)
└── created_at, updated_at
```

### 3. Inter-Annotator Agreement System

#### A. Agreement Calculation Engine
```
AgreementCalculations (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── text_id (Foreign Key, nullable)
├── calculation_type (kappa, alpha, fleiss_kappa, custom)
├── annotator_pairs (JSON Array)
├── agreement_scope (span, label, attribute, relation)
├── agreement_score (Float)
├── confidence_interval (JSON)
├── calculation_parameters (JSON)
├── calculated_by (User FK)
├── calculation_date (DateTime)
└── detailed_results (JSON)

AgreementMetrics (New Model)  
├── id (Primary Key)
├── project_id (Foreign Key)
├── metric_name (String)
├── metric_type (inter_annotator, intra_annotator, gold_standard)
├── measurement_method (exact_match, partial_overlap, label_only)
├── threshold_config (JSON)
├── is_active (Boolean)
└── configuration (JSON)
```

#### B. Quality Assessment Framework
```
QualityMetrics (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── annotator_id (User FK)
├── metric_type (consistency, accuracy, completeness, efficiency)
├── metric_value (Float)
├── benchmark_value (Float)
├── measurement_period (String)
├── calculated_date (DateTime)
├── improvement_trend (JSON)
└── detailed_breakdown (JSON)

GoldStandardAnnotations (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── expert_annotations (JSON)
├── created_by (User FK)
├── validation_status (pending, approved, rejected)
├── usage_count (Integer)
├── last_used (DateTime)
└── metadata (JSON)
```

### 4. Real-Time Collaboration System

#### A. WebSocket Integration
```python
# New WebSocket Manager
class CollaborationManager:
    def __init__(self):
        self.active_connections = {}
        self.project_rooms = {}
        
    async def connect_user(self, websocket, user_id, project_id)
    async def disconnect_user(self, user_id, project_id)
    async def broadcast_annotation_update(self, project_id, annotation_data)
    async def send_user_activity(self, project_id, activity_data)
    async def handle_conflict_resolution(self, conflict_data)
```

#### B. Real-Time Activity Tracking
```
UserActivity (New Model)
├── id (Primary Key)
├── user_id (Foreign Key)
├── project_id (Foreign Key)
├── activity_type (annotation_created, annotation_updated, comment_added)
├── target_id (Generic FK)
├── activity_data (JSON)
├── timestamp (DateTime)
├── session_id (String)
└── ip_address (String)

CollaborationSessions (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── participants (JSON Array of User IDs)
├── session_start (DateTime)
├── session_end (DateTime)
├── activity_summary (JSON)
└── session_type (annotation, review, discussion)
```

#### C. Conflict Resolution System
```
AnnotationConflicts (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── conflicting_annotations (JSON Array)
├── conflict_type (overlap, disagreement, duplicate)
├── auto_detected (Boolean)
├── resolution_strategy (manual, voting, expert_judgment)
├── resolved_annotation_id (Annotation FK)
├── resolved_by (User FK)
├── resolution_date (DateTime)
└── resolution_notes (Text)
```

### 5. Advanced Export and ML Integration

#### A. Enhanced Export Formats
```
ExportFormats (New Model)
├── id (Primary Key)
├── format_name (String)
├── format_type (json, xml, csv, conll, brat, spacy, transformers)
├── format_schema (JSON)
├── transformation_rules (JSON)
├── output_structure (JSON)
├── is_ml_ready (Boolean)
└── created_at, updated_at

ExportJobs (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── requested_by (User FK)
├── export_format_id (Foreign Key)
├── export_parameters (JSON)
├── status (pending, processing, completed, failed)
├── file_path (String)
├── download_count (Integer)
├── expires_at (DateTime)
└── created_at, updated_at
```

#### B. NLP Tool Integration
```
NLPIntegrations (New Model)
├── id (Primary Key)
├── project_id (Foreign Key)
├── tool_name (spacy, nltk, transformers, custom)
├── model_name (String)
├── configuration (JSON)
├── preprocessing_pipeline (JSON)
├── output_mapping (JSON)
├── is_active (Boolean)
└── last_sync (DateTime)

MLAnnotationSuggestions (New Model)
├── id (Primary Key)
├── text_id (Foreign Key)
├── suggested_annotations (JSON)
├── confidence_scores (JSON Array)
├── source_model (String)
├── model_version (String)
├── generated_at (DateTime)
├── accepted_suggestions (JSON Array)
├── rejected_suggestions (JSON Array)
└── feedback_data (JSON)
```

## Database Schema Changes

### New Tables Summary
1. **Teams & TeamMemberships** - Team collaboration
2. **AnnotationTasks & WorkflowSteps** - Task management
3. **AnnotationComments & ProjectDiscussions** - Communication
4. **Relations & RelationTypes** - Relation annotations
5. **AnnotationHierarchy & OverlappingAnnotations** - Complex annotations
6. **AnnotationAttributes & AttributeTemplates** - Structured attributes
7. **AgreementCalculations & AgreementMetrics** - Quality assessment
8. **QualityMetrics & GoldStandardAnnotations** - Quality tracking
9. **UserActivity & CollaborationSessions** - Real-time tracking
10. **AnnotationConflicts** - Conflict resolution
11. **ExportFormats & ExportJobs** - Enhanced exports
12. **NLPIntegrations & MLAnnotationSuggestions** - AI integration

### Modified Existing Tables
```sql
-- Add columns to existing User table
ALTER TABLE users ADD COLUMN expertise_areas JSON;
ALTER TABLE users ADD COLUMN annotation_preferences JSON;
ALTER TABLE users ADD COLUMN performance_metrics JSON;

-- Add columns to existing Project table  
ALTER TABLE projects ADD COLUMN collaboration_settings JSON;
ALTER TABLE projects ADD COLUMN quality_thresholds JSON;
ALTER TABLE projects ADD COLUMN ml_integration_config JSON;

-- Add columns to existing Annotation table
ALTER TABLE annotations ADD COLUMN annotation_attributes JSON;
ALTER TABLE annotations ADD COLUMN quality_scores JSON;
ALTER TABLE annotations ADD COLUMN ml_generated BOOLEAN DEFAULT FALSE;
```

## API Enhancements

### New Endpoint Categories

#### 1. Team Management
```
POST /api/teams/                    - Create team
GET /api/teams/                     - List teams  
PUT /api/teams/{id}/members         - Manage members
GET /api/teams/{id}/performance     - Team metrics
```

#### 2. Advanced Annotations  
```
POST /api/annotations/relations     - Create relation
GET /api/annotations/relations      - List relations
POST /api/annotations/hierarchical  - Create nested annotations
GET /api/annotations/conflicts      - Get conflicts
```

#### 3. Quality & Agreement
```
GET /api/quality/agreement          - Calculate agreement
GET /api/quality/metrics           - Get quality metrics
POST /api/quality/gold-standard    - Create gold standard
GET /api/quality/performance       - Annotator performance
```

#### 4. Real-time Collaboration
```
WebSocket /ws/collaboration/{project_id}  - Real-time updates
GET /api/collaboration/activity           - Activity feed
POST /api/collaboration/conflicts/resolve - Resolve conflicts
```

#### 5. ML Integration
```
POST /api/ml/suggestions           - Get ML suggestions
PUT /api/ml/feedback              - Provide feedback
GET /api/ml/models                - List available models
POST /api/export/ml-formats       - Export for ML
```

## Implementation Roadmap

### Phase 1: Enhanced Collaboration (Weeks 1-4)
- Team management system
- Task assignment workflows  
- Comment and discussion features
- Basic conflict detection

### Phase 2: Advanced Annotations (Weeks 5-8)
- Relation annotation system
- Hierarchical annotations
- Overlapping span support
- Attribute templates

### Phase 3: Quality & Agreement (Weeks 9-12)  
- Inter-annotator agreement calculations
- Quality metrics framework
- Gold standard integration
- Performance dashboards

### Phase 4: Real-time Features (Weeks 13-16)
- WebSocket implementation
- Live collaboration features
- Activity tracking
- Conflict resolution UI

### Phase 5: ML Integration (Weeks 17-20)
- NLP tool integrations
- ML annotation suggestions
- Advanced export formats
- Feedback loop implementation

### Phase 6: Testing & Optimization (Weeks 21-24)
- Comprehensive testing suite
- Performance optimization
- Security audit
- Documentation completion

## Technical Considerations

### Performance Optimizations
- Database indexing strategy for new tables
- Caching layer for agreement calculations
- Async processing for ML suggestions
- WebSocket connection pooling

### Security Enhancements
- Role-based access control expansion
- API rate limiting for ML endpoints
- Data encryption for sensitive annotations
- Audit logging for all activities

### Scalability Considerations
- Horizontal scaling for WebSocket services
- Distributed caching for real-time features
- Queue system for batch processing
- Microservices architecture for ML components

This enhanced architecture transforms the basic annotation system into a comprehensive collaborative platform suitable for large-scale academic research projects with advanced analytical capabilities.