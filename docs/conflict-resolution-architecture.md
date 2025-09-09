# Annotation Conflict Resolution System Architecture

## Overview

The conflict resolution system provides comprehensive management of overlapping annotations and conflicting labels in multi-user annotation projects. This system ensures annotation quality and enables systematic resolution of disagreements between annotators.

## System Components

### 1. Conflict Detection Engine
- **Span Overlap Detection**: Identifies overlapping text spans between annotations
- **Label Conflict Detection**: Detects conflicting labels for overlapping or identical spans
- **Real-time Monitoring**: Continuously monitors for conflicts as annotations are created/updated
- **Threshold Management**: Configurable overlap thresholds and conflict sensitivity

### 2. Resolution Strategies
- **Automatic Merging**: Rule-based automatic resolution for simple conflicts
- **Voting System**: Democratic resolution through annotator voting
- **Expert Review**: Assignment to domain experts for complex conflicts
- **User Consensus**: Collaborative resolution through discussion
- **Weighted Resolution**: Expert-weighted voting based on annotator experience

### 3. Conflict Tracking Database
- **Conflict Registry**: Central tracking of all detected conflicts
- **Resolution History**: Complete audit trail of resolution processes
- **Performance Metrics**: Conflict resolution statistics and performance tracking
- **Annotator Profiles**: Individual conflict patterns and resolution success rates

### 4. Notification & Workflow System
- **Real-time Alerts**: Immediate notification of new conflicts
- **Assignment System**: Automatic assignment of conflicts to resolvers
- **Escalation Workflows**: Structured escalation paths for unresolved conflicts
- **Status Tracking**: Real-time status updates throughout resolution process

### 5. Integration Layer
- **Agreement System Integration**: Seamless integration with inter-annotator agreement metrics
- **API Gateway**: RESTful APIs for conflict management operations
- **WebSocket Support**: Real-time updates and notifications
- **Admin Dashboard**: Comprehensive administrative interface

## Database Architecture

### Core Tables
- `annotation_conflicts`: Primary conflict registry
- `conflict_resolutions`: Resolution attempts and outcomes
- `conflict_participants`: Participants in conflict resolution
- `resolution_votes`: Voting records for democratic resolution
- `conflict_notifications`: Notification and alert management

### Integration Points
- Links to existing `annotations`, `users`, `projects` tables
- Integration with `agreement_studies` for quality metrics
- Relationship with `labels` for conflict categorization

## Conflict Detection Algorithms

### 1. Span Overlap Detection
```python
def detect_span_overlaps(annotations):
    # Implementation details for geometric overlap detection
    # Considers partial overlaps, complete overlaps, and nested spans
    pass
```

### 2. Label Conflict Analysis
```python
def detect_label_conflicts(overlapping_annotations):
    # Analyzes conflicting labels for overlapping spans
    # Considers label hierarchy and semantic similarity
    pass
```

### 3. Confidence-based Filtering
```python
def filter_by_confidence(conflicts, threshold=0.7):
    # Filters conflicts based on annotation confidence scores
    # Reduces false positives from uncertain annotations
    pass
```

## Resolution Workflow States

1. **Detected**: Conflict identified by detection engine
2. **Assigned**: Conflict assigned to resolver(s)
3. **In Review**: Under active review by assigned resolver
4. **Voting**: Democratic voting process active
5. **Expert Review**: Escalated to domain expert
6. **Resolved**: Conflict successfully resolved
7. **Archived**: Resolved conflict archived for analysis

## Performance Considerations

- **Indexing Strategy**: Optimized database indexes for span overlap queries
- **Caching Layer**: Redis caching for frequently accessed conflict data
- **Batch Processing**: Efficient batch processing for large-scale conflict detection
- **Real-time Updates**: WebSocket-based real-time conflict status updates

## Security & Privacy

- **Access Control**: Role-based access to conflict resolution features
- **Audit Logging**: Complete audit trail of all conflict resolution activities
- **Data Protection**: Anonymization options for sensitive annotation data
- **Permission Management**: Granular permissions for conflict resolution operations

## Monitoring & Analytics

- **Conflict Metrics**: Real-time metrics on conflict rates and resolution times
- **Performance Dashboard**: Administrative dashboard for system monitoring
- **Quality Indicators**: Integration with annotation quality metrics
- **Trend Analysis**: Historical analysis of conflict patterns and trends

## API Endpoints

### Conflict Management
- `GET /api/conflicts` - List conflicts with filtering
- `POST /api/conflicts/detect` - Trigger conflict detection
- `PUT /api/conflicts/{id}/resolve` - Submit resolution
- `POST /api/conflicts/{id}/vote` - Submit resolution vote

### Administrative
- `GET /api/admin/conflicts/stats` - System statistics
- `POST /api/admin/conflicts/settings` - Update system settings
- `GET /api/admin/conflicts/export` - Export conflict data

### Real-time
- `WebSocket /ws/conflicts` - Real-time conflict updates
- `WebSocket /ws/notifications` - Real-time notifications