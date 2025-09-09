# Inter-Annotator Agreement System Documentation

## Overview

The Inter-Annotator Agreement System provides comprehensive functionality for calculating and tracking agreement between annotators in text annotation projects. This system is critical for academic research workflows where annotation quality and reliability must be measured and maintained.

## Features

### Core Agreement Metrics
- **Cohen's Kappa**: Agreement between two annotators
- **Fleiss' Kappa**: Agreement among multiple annotators
- **Krippendorff's Alpha**: General agreement metric supporting various data types
- **Percentage Agreement**: Simple agreement calculation

### Agreement Methods
- **Span Overlap**: Considers overlapping text spans (configurable threshold)
- **Exact Match**: Requires identical spans and labels
- **Label Only**: Only considers label agreement, ignores spans

### Automatic Tracking
- Triggers agreement calculation when annotations are created/updated
- Stores agreement history with timestamps
- Tracks annotator performance over time
- Generates recommendations based on agreement scores

### API Endpoints
- Calculate agreement for individual texts or entire projects
- Retrieve agreement history and statistics
- Enable/disable agreement tracking per project
- Generate agreement dashboards and reports

## Architecture

### Database Models

#### AgreementStudy
Central model for grouping agreement calculations.
```python
class AgreementStudy(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    n_annotators = Column(Integer, nullable=False)
    n_items = Column(Integer, nullable=False)
    overall_quality_score = Column(Float)
    study_status = Column(String(50), default='completed')
```

#### CohenKappaResult
Stores Cohen's Kappa calculations for pairs of annotators.
```python
class CohenKappaResult(Base):
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'))
    annotator1_name = Column(String(255), nullable=False)
    annotator2_name = Column(String(255), nullable=False)
    kappa_value = Column(Float, nullable=False)
    confidence_interval_lower = Column(Float)
    confidence_interval_upper = Column(Float)
```

#### FleissKappaResult
Stores Fleiss' Kappa calculations for multiple annotators.
```python
class FleissKappaResult(Base):
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'))
    kappa_value = Column(Float, nullable=False)
    n_annotators = Column(Integer, nullable=False)
    n_items = Column(Integer, nullable=False)
```

#### AnnotatorPerformance
Tracks individual annotator performance over time.
```python
class AnnotatorPerformance(Base):
    id = Column(Integer, primary_key=True)
    annotator_name = Column(String(255), nullable=False)
    studies_participated = Column(Integer, default=0)
    average_kappa_score = Column(Float)
    consistency_rating = Column(String(50))
```

### Service Layer

#### AgreementService
Main service class handling agreement calculations and integration.

Key methods:
- `trigger_agreement_calculation()`: Auto-triggered when annotations change
- `calculate_text_agreement()`: Calculate agreement for specific text
- `calculate_project_agreement()`: Calculate agreement for entire project
- `extract_annotations()`: Convert annotations to analysis format
- `update_annotator_performance()`: Update performance tracking

### Utilities

#### AgreementMetrics
Low-level statistical calculations for agreement metrics.

#### AgreementAnalysis
High-level analysis workflows combining multiple metrics.

## API Endpoints

### Agreement Calculation

#### Calculate Cohen's Kappa
```http
POST /api/agreement/calculate/cohen-kappa
Content-Type: application/json

{
    "annotator1": ["A", "B", "C", "A", "B"],
    "annotator2": ["A", "B", "C", "A", "C"],
    "annotator1_name": "Alice",
    "annotator2_name": "Bob",
    "weights": "linear" // optional
}
```

#### Calculate Fleiss' Kappa
```http
POST /api/agreement/calculate/fleiss-kappa
Content-Type: application/json

{
    "annotations": [
        ["A", "B", "C", "A", "B"],
        ["A", "B", "C", "A", "C"],
        ["A", "A", "C", "A", "B"]
    ],
    "annotator_names": ["Alice", "Bob", "Charlie"]
}
```

#### Comprehensive Analysis
```http
POST /api/agreement/analyze/comprehensive
Content-Type: application/json

{
    "annotations": {
        "alice": ["A", "B", "C", "A", "B"],
        "bob": ["A", "B", "C", "A", "C"],
        "charlie": ["A", "A", "C", "A", "B"]
    },
    "dataset_name": "Project Annotations",
    "save_to_database": true,
    "study_name": "Weekly Agreement Check"
}
```

### Project Integration

#### Calculate Project Agreement
```http
POST /api/agreement/projects/{project_id}/calculate
Content-Type: application/json

{
    "text_ids": [1, 2, 3], // optional
    "annotator_ids": [1, 2], // optional
    "agreement_method": "span_overlap", // "span_overlap", "exact_match", "label_only"
    "overlap_threshold": 0.5,
    "save_to_database": true,
    "study_name": "Project Agreement Analysis"
}
```

#### Calculate Text-Specific Agreement
```http
POST /api/agreement/projects/{project_id}/texts/{text_id}/calculate
Content-Type: application/json

{
    "annotator_ids": [1, 2], // optional
    "agreement_method": "span_overlap",
    "overlap_threshold": 0.5,
    "save_to_database": false
}
```

#### Enable Agreement Tracking
```http
POST /api/agreement/projects/{project_id}/enable
```

#### Disable Agreement Tracking
```http
POST /api/agreement/projects/{project_id}/disable
```

### Reporting and Analysis

#### Get Project Agreement Summary
```http
GET /api/agreement/projects/{project_id}/summary
```

Response:
```json
{
    "success": true,
    "project_summary": {
        "project_id": 1,
        "project_name": "Medical Text Annotation",
        "has_agreement_data": true,
        "latest_calculation": "2024-01-15T10:30:00Z",
        "total_studies": 5,
        "average_cohen_kappa": 0.75,
        "average_fleiss_kappa": 0.68,
        "overall_quality_score": 0.72,
        "quality_interpretation": "Good"
    }
}
```

#### Get Agreement History
```http
GET /api/agreement/projects/{project_id}/history
```

#### List All Studies
```http
GET /api/agreement/studies?page=1&per_page=10&status=completed
```

#### Get Specific Study
```http
GET /api/agreement/studies/{study_id}
```

#### Get Annotator Performance
```http
GET /api/agreement/annotators/performance
GET /api/agreement/annotators/{annotator_name}/performance
```

#### Agreement Dashboard
```http
GET /api/agreement/reports/dashboard
```

#### Interpretation Guidelines
```http
GET /api/agreement/metrics/guidelines
```

## Integration with Annotation Workflow

### Automatic Triggers
The system automatically calculates agreement when:
1. A new annotation is created
2. An existing annotation is updated (label, span changes)
3. Project has `inter_annotator_agreement` enabled
4. Text has multiple annotators

### Configuration
Enable agreement tracking per project:
```python
project = Project(
    name="Research Project",
    inter_annotator_agreement=True,
    # ... other fields
)
```

### Service Integration
```python
from src.services.agreement_service import AgreementService

# In annotation creation/update endpoints
agreement_service = AgreementService(db)
agreement_service.trigger_agreement_calculation(annotation_id)
```

## Agreement Interpretation

### Cohen's & Fleiss' Kappa (Landis & Koch, 1977)
- `< 0.00`: Poor (less than chance agreement)
- `0.00-0.20`: Slight agreement
- `0.21-0.40`: Fair agreement
- `0.41-0.60`: Moderate agreement
- `0.61-0.80`: Substantial agreement
- `0.81-1.00`: Almost perfect agreement

### Krippendorff's Alpha (Krippendorff, 2004)
- `< 0.67`: Low reliability (inadequate for most purposes)
- `0.67-0.80`: Moderate reliability (acceptable for some purposes)
- `≥ 0.80`: High reliability (acceptable for most purposes)

### Recommendations
- **< 0.40**: Poor agreement - training needed
- **0.40-0.60**: Moderate - consider improvements
- **0.60-0.80**: Good agreement - minor improvements may help
- **≥ 0.80**: Excellent agreement

## Usage Examples

### Basic Agreement Calculation
```python
from src.utils.agreement_metrics import AgreementMetrics

metrics = AgreementMetrics()

# Two annotators
ann1 = ['A', 'B', 'C', 'A', 'B']
ann2 = ['A', 'B', 'C', 'A', 'C']
cohen_result = metrics.cohen_kappa(ann1, ann2)
print(f"Cohen's Kappa: {cohen_result['kappa']}")

# Multiple annotators
annotations = [ann1, ann2, ['A', 'A', 'C', 'A', 'B']]
fleiss_result = metrics.fleiss_kappa(annotations)
print(f"Fleiss' Kappa: {fleiss_result['kappa']}")
```

### Comprehensive Analysis
```python
from src.utils.agreement_metrics import AgreementAnalysis

analysis = AgreementAnalysis()
annotations_dict = {
    'annotator1': ['A', 'B', 'C', 'A', 'B'],
    'annotator2': ['A', 'B', 'C', 'A', 'C'],
    'annotator3': ['A', 'A', 'C', 'A', 'B']
}

results = analysis.analyze_dataset(annotations_dict)
print(f"Overall Quality: {results['summary']['overall_quality']}")
```

### Service Layer Usage
```python
from src.services.agreement_service import AgreementService

service = AgreementService(db_session)

# Calculate agreement for a project
results = service.calculate_project_agreement(
    project_id=1,
    agreement_method='span_overlap',
    overlap_threshold=0.5
)

# Get project summary
summary = service.get_project_agreement_summary(project_id=1)
```

## Testing

Run the integration tests:
```bash
python test_agreement_integration.py
```

Test specific components:
```bash
python -m pytest tests/test_utils/test_agreement_metrics.py
python -m pytest tests/test_models/test_agreement.py
```

## Configuration

### Environment Variables
- `AGREEMENT_AUTO_CALCULATE`: Enable automatic calculation (default: True)
- `AGREEMENT_DEFAULT_METHOD`: Default agreement method (default: 'span_overlap')
- `AGREEMENT_DEFAULT_THRESHOLD`: Default overlap threshold (default: 0.5)

### Project Settings
```python
# Enable for project
project.inter_annotator_agreement = True

# Disable for project  
project.inter_annotator_agreement = False
```

## Performance Considerations

### Optimization Strategies
1. **Batch Processing**: Calculate agreement for multiple texts/projects together
2. **Caching**: Cache frequent agreement calculations
3. **Background Tasks**: Use task queues for large datasets
4. **Sampling**: Use sample-based calculations for very large datasets

### Resource Usage
- Memory: O(n×m) where n=items, m=annotators
- CPU: O(n²) for pairwise comparisons
- Storage: ~1KB per agreement study result

## Error Handling

Common issues and solutions:

### Insufficient Data
```python
try:
    results = service.calculate_project_agreement(project_id)
except ValueError as e:
    if "Need at least 2 annotators" in str(e):
        # Handle insufficient annotators
        pass
```

### Database Errors
```python
try:
    study_id = store_agreement_analysis(db, results, name, description)
except Exception as e:
    logger.error(f"Failed to save agreement study: {e}")
    # Handle database failure
```

### API Errors
- `400 Bad Request`: Invalid input data
- `404 Not Found`: Project/text not found  
- `500 Internal Server Error`: Calculation or database error

## Future Enhancements

### Planned Features
1. **Real-time Agreement Monitoring**: Live agreement updates during annotation
2. **Advanced Visualizations**: Agreement heatmaps and trend charts
3. **Machine Learning Integration**: Predict annotation quality
4. **Multi-label Support**: Handle complex annotation schemes
5. **Weighted Agreement**: Custom weighting for different label types
6. **Agreement Predictions**: Estimate required annotators for target agreement

### Research Extensions
1. **Bootstrap Confidence Intervals**: More robust statistical estimates
2. **Bayesian Agreement Models**: Incorporate prior knowledge
3. **Active Learning Integration**: Use agreement for annotation selection
4. **Cross-validation**: Agreement-based model validation

## References

1. Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. Biometrics, 159-174.
2. Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters. Psychological Bulletin, 76(5), 378-382.
3. Krippendorff, K. (2004). Content Analysis: An Introduction to Its Methodology. Sage Publications.
4. Artstein, R., & Poesio, M. (2008). Inter-coder agreement for computational linguistics. Computational Linguistics, 34(4), 555-596.