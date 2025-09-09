# Inter-Annotator Agreement & Quality Metrics System

## Overview
This document specifies the implementation of comprehensive quality assessment systems including inter-annotator agreement calculations, quality metrics, and validation frameworks for academic annotation projects.

## 1. Inter-Annotator Agreement Calculations

### Database Schema
```sql
CREATE TABLE agreement_calculations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    text_id INTEGER REFERENCES texts(id) ON DELETE CASCADE, -- NULL for project-wide calculations
    calculation_type VARCHAR(50) NOT NULL CHECK (calculation_type IN ('kappa', 'alpha', 'fleiss_kappa', 'gwet_ac', 'scott_pi', 'custom')),
    annotator_pairs JSONB NOT NULL, -- [{annotator1_id: 1, annotator2_id: 2}] or [1,2,3] for multi-annotator
    agreement_scope VARCHAR(50) NOT NULL CHECK (agreement_scope IN ('span', 'label', 'attribute', 'relation', 'complete')),
    agreement_score FLOAT,
    confidence_interval JSONB, -- {lower: 0.65, upper: 0.85, confidence_level: 0.95}
    calculation_parameters JSONB DEFAULT '{}',
    calculated_by INTEGER NOT NULL REFERENCES users(id),
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detailed_results JSONB DEFAULT '{}',
    interpretation VARCHAR(20) CHECK (interpretation IN ('poor', 'fair', 'moderate', 'good', 'very_good', 'excellent')),
    
    -- Performance tracking
    calculation_time_ms INTEGER,
    annotations_analyzed INTEGER,
    
    CONSTRAINT valid_score_range CHECK (agreement_score IS NULL OR (agreement_score >= -1.0 AND agreement_score <= 1.0))
);

CREATE TABLE agreement_metrics (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN ('inter_annotator', 'intra_annotator', 'gold_standard', 'consensus')),
    measurement_method VARCHAR(50) NOT NULL CHECK (measurement_method IN ('exact_match', 'partial_overlap', 'label_only', 'boundary_flexible', 'semantic_similarity')),
    threshold_config JSONB DEFAULT '{}', -- {min_overlap: 0.5, boundary_tolerance: 5}
    weight_config JSONB DEFAULT '{}', -- For weighted agreement calculations
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    configuration JSONB DEFAULT '{}',
    
    CONSTRAINT unique_metric_per_project UNIQUE(project_id, metric_name)
);

CREATE TABLE quality_metrics (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    annotator_id INTEGER REFERENCES users(id) ON DELETE CASCADE, -- NULL for project-wide metrics
    metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN ('consistency', 'accuracy', 'completeness', 'efficiency', 'bias', 'difficulty')),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    benchmark_value FLOAT,
    measurement_period VARCHAR(50) DEFAULT 'all_time',
    calculated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    improvement_trend JSONB DEFAULT '{}', -- Historical trend data
    detailed_breakdown JSONB DEFAULT '{}',
    
    -- Contextual information
    text_count INTEGER DEFAULT 0,
    annotation_count INTEGER DEFAULT 0,
    comparison_baseline VARCHAR(50) -- 'project_avg', 'expert', 'consensus'
);

CREATE TABLE gold_standard_annotations (
    id SERIAL PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
    expert_annotations JSONB NOT NULL, -- Complete annotation data in standardized format
    created_by INTEGER NOT NULL REFERENCES users(id),
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'approved', 'rejected')),
    validation_notes TEXT,
    validated_by INTEGER REFERENCES users(id),
    validation_date TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    difficulty_rating FLOAT CHECK (difficulty_rating >= 1.0 AND difficulty_rating <= 5.0),
    consensus_level FLOAT CHECK (consensus_level >= 0.0 AND consensus_level <= 1.0),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_gold_standard_per_text UNIQUE(text_id)
);

-- Indexes for performance
CREATE INDEX idx_agreement_calculations_project ON agreement_calculations(project_id);
CREATE INDEX idx_agreement_calculations_date ON agreement_calculations(calculation_date);
CREATE INDEX idx_quality_metrics_annotator ON quality_metrics(annotator_id);
CREATE INDEX idx_quality_metrics_type ON quality_metrics(metric_type);
CREATE INDEX idx_gold_standard_text ON gold_standard_annotations(text_id);
```

### Agreement Calculation Engine
```python
import numpy as np
from scipy import stats
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import itertools
from collections import defaultdict, Counter

class AgreementType(Enum):
    COHENS_KAPPA = "cohens_kappa"
    FLEISS_KAPPA = "fleiss_kappa"
    KRIPPENDORFF_ALPHA = "krippendorff_alpha"
    GWET_AC = "gwet_ac"
    SCOTT_PI = "scott_pi"
    PEARSON_CORRELATION = "pearson_correlation"
    SPEARMAN_CORRELATION = "spearman_correlation"

class AnnotationScope(Enum):
    SPAN_EXACT = "span_exact"
    SPAN_OVERLAP = "span_overlap"
    LABEL_ONLY = "label_only"
    ATTRIBUTE = "attribute"
    RELATION = "relation"
    COMPLETE = "complete"

@dataclass
class AnnotationComparison:
    """Represents a single annotation for comparison."""
    annotator_id: int
    text_id: int
    start_char: int
    end_char: int
    label: str
    attributes: Dict[str, Any] = None
    confidence: float = 1.0

@dataclass
class AgreementResult:
    """Result of an agreement calculation."""
    agreement_type: AgreementType
    score: float
    confidence_interval: Optional[Tuple[float, float]]
    interpretation: str
    detailed_results: Dict[str, Any]
    calculation_time_ms: int
    annotations_analyzed: int

class AgreementCalculator:
    """Calculates various inter-annotator agreement metrics."""
    
    INTERPRETATION_THRESHOLDS = {
        AgreementType.COHENS_KAPPA: {
            (0.0, 0.20): "poor",
            (0.21, 0.40): "fair", 
            (0.41, 0.60): "moderate",
            (0.61, 0.80): "good",
            (0.81, 1.00): "very_good"
        },
        AgreementType.KRIPPENDORFF_ALPHA: {
            (0.0, 0.67): "poor",
            (0.67, 0.80): "acceptable",
            (0.80, 1.00): "good"
        }
    }
    
    def __init__(self):
        self.overlap_threshold = 0.5  # For span overlap calculations
        self.boundary_tolerance = 5   # Character tolerance for span boundaries
    
    def calculate_agreement(
        self,
        annotations: List[AnnotationComparison],
        agreement_type: AgreementType,
        scope: AnnotationScope,
        parameters: Dict[str, Any] = None
    ) -> AgreementResult:
        """Calculate inter-annotator agreement."""
        
        start_time = time.time()
        
        if parameters:
            self.overlap_threshold = parameters.get('overlap_threshold', 0.5)
            self.boundary_tolerance = parameters.get('boundary_tolerance', 5)
        
        # Prepare data based on scope
        if scope == AnnotationScope.SPAN_EXACT:
            agreement_matrix = self._build_span_exact_matrix(annotations)
        elif scope == AnnotationScope.SPAN_OVERLAP:
            agreement_matrix = self._build_span_overlap_matrix(annotations)
        elif scope == AnnotationScope.LABEL_ONLY:
            agreement_matrix = self._build_label_matrix(annotations)
        elif scope == AnnotationScope.ATTRIBUTE:
            agreement_matrix = self._build_attribute_matrix(annotations, parameters.get('attribute_name'))
        elif scope == AnnotationScope.RELATION:
            agreement_matrix = self._build_relation_matrix(annotations)
        else:  # COMPLETE
            agreement_matrix = self._build_complete_matrix(annotations)
        
        # Calculate agreement based on type
        if agreement_type == AgreementType.COHENS_KAPPA:
            score, ci, details = self._calculate_cohens_kappa(agreement_matrix)
        elif agreement_type == AgreementType.FLEISS_KAPPA:
            score, ci, details = self._calculate_fleiss_kappa(agreement_matrix)
        elif agreement_type == AgreementType.KRIPPENDORFF_ALPHA:
            score, ci, details = self._calculate_krippendorff_alpha(agreement_matrix)
        elif agreement_type == AgreementType.GWET_AC:
            score, ci, details = self._calculate_gwet_ac(agreement_matrix)
        elif agreement_type == AgreementType.SCOTT_PI:
            score, ci, details = self._calculate_scott_pi(agreement_matrix)
        else:
            raise ValueError(f"Unsupported agreement type: {agreement_type}")
        
        calculation_time = int((time.time() - start_time) * 1000)
        interpretation = self._interpret_score(agreement_type, score)
        
        return AgreementResult(
            agreement_type=agreement_type,
            score=score,
            confidence_interval=ci,
            interpretation=interpretation,
            detailed_results=details,
            calculation_time_ms=calculation_time,
            annotations_analyzed=len(annotations)
        )
    
    def _build_span_exact_matrix(self, annotations: List[AnnotationComparison]) -> np.ndarray:
        """Build agreement matrix for exact span matching."""
        # Group annotations by text and create comparison matrix
        text_groups = defaultdict(list)
        for ann in annotations:
            text_groups[ann.text_id].append(ann)
        
        agreement_data = []
        
        for text_id, text_annotations in text_groups.items():
            # Create annotator pairs
            annotators = list(set(ann.annotator_id for ann in text_annotations))
            
            for ann1_id, ann2_id in itertools.combinations(annotators, 2):
                ann1_annotations = [a for a in text_annotations if a.annotator_id == ann1_id]
                ann2_annotations = [a for a in text_annotations if a.annotator_id == ann2_id]
                
                # Find exact matches
                matches = 0
                total_possible = max(len(ann1_annotations), len(ann2_annotations))
                
                for a1 in ann1_annotations:
                    for a2 in ann2_annotations:
                        if (a1.start_char == a2.start_char and 
                            a1.end_char == a2.end_char and
                            a1.label == a2.label):
                            matches += 1
                            break
                
                if total_possible > 0:
                    agreement_data.append([matches, total_possible - matches])
                else:
                    agreement_data.append([0, 0])
        
        return np.array(agreement_data)
    
    def _build_span_overlap_matrix(self, annotations: List[AnnotationComparison]) -> np.ndarray:
        """Build agreement matrix for overlapping span matching."""
        text_groups = defaultdict(list)
        for ann in annotations:
            text_groups[ann.text_id].append(ann)
        
        agreement_data = []
        
        for text_id, text_annotations in text_groups.items():
            annotators = list(set(ann.annotator_id for ann in text_annotations))
            
            for ann1_id, ann2_id in itertools.combinations(annotators, 2):
                ann1_annotations = [a for a in text_annotations if a.annotator_id == ann1_id]
                ann2_annotations = [a for a in text_annotations if a.annotator_id == ann2_id]
                
                # Calculate overlap agreement
                agreement_score = self._calculate_span_overlap_agreement(
                    ann1_annotations, ann2_annotations
                )
                agreement_data.append(agreement_score)
        
        return np.array(agreement_data)
    
    def _calculate_span_overlap_agreement(
        self, 
        ann1_list: List[AnnotationComparison], 
        ann2_list: List[AnnotationComparison]
    ) -> float:
        """Calculate overlap agreement between two annotation sets."""
        if not ann1_list or not ann2_list:
            return 0.0
        
        total_overlap = 0
        total_union = 0
        
        # Create span coverage for each annotator
        spans1 = [(a.start_char, a.end_char, a.label) for a in ann1_list]
        spans2 = [(a.start_char, a.end_char, a.label) for a in ann2_list]
        
        # Calculate intersection over union for each unique span
        all_positions = set()
        for start, end, label in spans1 + spans2:
            all_positions.update(range(start, end))
        
        if not all_positions:
            return 1.0  # Perfect agreement on empty annotations
        
        # For each position, check if annotators agree
        agreements = 0
        for pos in all_positions:
            ann1_labels = [label for start, end, label in spans1 if start <= pos < end]
            ann2_labels = [label for start, end, label in spans2 if start <= pos < end]
            
            if set(ann1_labels) == set(ann2_labels):
                agreements += 1
        
        return agreements / len(all_positions) if all_positions else 1.0
    
    def _calculate_cohens_kappa(self, agreement_matrix: np.ndarray) -> Tuple[float, Tuple[float, float], Dict[str, Any]]:
        """Calculate Cohen's Kappa for two annotators."""
        if len(agreement_matrix) < 2:
            return 0.0, (0.0, 0.0), {"error": "Insufficient data"}
        
        # Convert to confusion matrix format
        observed_agreement = np.sum(np.diag(agreement_matrix)) / np.sum(agreement_matrix)
        
        # Calculate expected agreement
        marginal_1 = np.sum(agreement_matrix, axis=1) / np.sum(agreement_matrix)
        marginal_2 = np.sum(agreement_matrix, axis=0) / np.sum(agreement_matrix)
        expected_agreement = np.sum(marginal_1 * marginal_2)
        
        # Calculate Kappa
        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
        
        # Calculate confidence interval (simplified)
        n = np.sum(agreement_matrix)
        se = np.sqrt((observed_agreement * (1 - observed_agreement)) / (n * (1 - expected_agreement) ** 2))
        ci_lower = kappa - 1.96 * se
        ci_upper = kappa + 1.96 * se
        
        details = {
            "observed_agreement": observed_agreement,
            "expected_agreement": expected_agreement,
            "n": int(n),
            "confusion_matrix": agreement_matrix.tolist()
        }
        
        return kappa, (ci_lower, ci_upper), details
    
    def _calculate_fleiss_kappa(self, agreement_matrix: np.ndarray) -> Tuple[float, Tuple[float, float], Dict[str, Any]]:
        """Calculate Fleiss' Kappa for multiple annotators."""
        # Implementation for Fleiss' Kappa
        # This is a simplified version - full implementation would be more complex
        
        n_items, n_categories = agreement_matrix.shape
        n_raters = np.sum(agreement_matrix[0])  # Assuming same number of raters per item
        
        # Calculate observed agreement
        p_i = np.sum(agreement_matrix ** 2, axis=1) / (n_raters * (n_raters - 1))
        p_bar = np.mean(p_i)
        
        # Calculate expected agreement  
        p_j = np.sum(agreement_matrix, axis=0) / (n_items * n_raters)
        p_e = np.sum(p_j ** 2)
        
        # Calculate Fleiss' Kappa
        kappa = (p_bar - p_e) / (1 - p_e)
        
        # Simplified confidence interval
        se = np.sqrt(2 / (n_items * n_raters * (n_raters - 1)))
        ci_lower = kappa - 1.96 * se
        ci_upper = kappa + 1.96 * se
        
        details = {
            "n_items": n_items,
            "n_raters": n_raters,
            "n_categories": n_categories,
            "observed_agreement": p_bar,
            "expected_agreement": p_e
        }
        
        return kappa, (ci_lower, ci_upper), details
    
    def _calculate_krippendorff_alpha(self, agreement_matrix: np.ndarray) -> Tuple[float, Tuple[float, float], Dict[str, Any]]:
        """Calculate Krippendorff's Alpha."""
        # Simplified implementation - full Krippendorff's Alpha is quite complex
        # This would need a full implementation based on the specific data type
        
        # Placeholder implementation
        observed_disagreement = 1 - np.trace(agreement_matrix) / np.sum(agreement_matrix)
        expected_disagreement = 1 - np.sum(np.sum(agreement_matrix, axis=0) ** 2) / np.sum(agreement_matrix) ** 2
        
        if expected_disagreement == 0:
            alpha = 1.0
        else:
            alpha = 1 - (observed_disagreement / expected_disagreement)
        
        # Simplified confidence interval
        ci_lower = max(-1.0, alpha - 0.1)
        ci_upper = min(1.0, alpha + 0.1)
        
        details = {
            "observed_disagreement": observed_disagreement,
            "expected_disagreement": expected_disagreement,
            "note": "Simplified implementation"
        }
        
        return alpha, (ci_lower, ci_upper), details
    
    def _interpret_score(self, agreement_type: AgreementType, score: float) -> str:
        """Interpret agreement score based on established thresholds."""
        if agreement_type not in self.INTERPRETATION_THRESHOLDS:
            return "unknown"
        
        thresholds = self.INTERPRETATION_THRESHOLDS[agreement_type]
        
        for (min_val, max_val), interpretation in thresholds.items():
            if min_val <= score <= max_val:
                return interpretation
        
        return "excellent" if score > 0.80 else "poor"

class QualityMetricsCalculator:
    """Calculates various quality metrics for annotators and projects."""
    
    def calculate_annotator_consistency(
        self, 
        annotator_id: int, 
        annotations: List[AnnotationComparison],
        time_window_days: int = 30
    ) -> Dict[str, float]:
        """Calculate consistency metrics for an annotator."""
        
        # Group annotations by time periods
        time_periods = self._group_by_time_periods(annotations, time_window_days)
        
        if len(time_periods) < 2:
            return {"consistency_score": 1.0, "note": "Insufficient data"}
        
        # Calculate intra-annotator agreement across time periods
        period_agreements = []
        
        for period1, period2 in itertools.combinations(time_periods, 2):
            # Calculate agreement between the same annotator's work in different periods
            agreement = self._calculate_intra_annotator_agreement(period1, period2)
            period_agreements.append(agreement)
        
        consistency_score = np.mean(period_agreements) if period_agreements else 1.0
        
        return {
            "consistency_score": consistency_score,
            "periods_compared": len(period_agreements),
            "score_variance": np.var(period_agreements) if len(period_agreements) > 1 else 0.0
        }
    
    def calculate_annotation_completeness(
        self,
        project_id: int,
        annotator_id: int,
        expected_annotations: int,
        actual_annotations: int
    ) -> Dict[str, float]:
        """Calculate completeness metrics."""
        
        completeness_ratio = actual_annotations / expected_annotations if expected_annotations > 0 else 0.0
        
        return {
            "completeness_ratio": min(1.0, completeness_ratio),
            "expected_annotations": expected_annotations,
            "actual_annotations": actual_annotations,
            "missing_annotations": max(0, expected_annotations - actual_annotations)
        }
    
    def calculate_efficiency_metrics(
        self,
        annotations: List[AnnotationComparison],
        time_spent_hours: float
    ) -> Dict[str, float]:
        """Calculate efficiency metrics."""
        
        if time_spent_hours <= 0:
            return {"annotations_per_hour": 0.0, "error": "Invalid time data"}
        
        annotations_per_hour = len(annotations) / time_spent_hours
        
        # Calculate average confidence as a proxy for annotation difficulty
        avg_confidence = np.mean([ann.confidence for ann in annotations]) if annotations else 0.0
        
        # Efficiency score considering both speed and confidence
        efficiency_score = annotations_per_hour * avg_confidence
        
        return {
            "annotations_per_hour": annotations_per_hour,
            "average_confidence": avg_confidence,
            "efficiency_score": efficiency_score,
            "total_annotations": len(annotations),
            "time_spent_hours": time_spent_hours
        }
```

### API Implementation
```python
@router.post("/quality/calculate-agreement")
async def calculate_agreement(
    request: AgreementCalculationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calculate inter-annotator agreement."""
    
    # Validate project access
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project or not await check_project_access(project, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get annotations for comparison
    annotations = await get_annotations_for_agreement(
        project_id=request.project_id,
        text_id=request.text_id,
        annotator_ids=request.annotator_ids,
        db=db
    )
    
    if len(annotations) < 2:
        raise HTTPException(status_code=400, detail="Insufficient annotations for agreement calculation")
    
    # Perform calculation
    calculator = AgreementCalculator()
    result = calculator.calculate_agreement(
        annotations=annotations,
        agreement_type=AgreementType(request.agreement_type),
        scope=AnnotationScope(request.scope),
        parameters=request.parameters or {}
    )
    
    # Store result
    calculation_record = AgreementCalculation(
        project_id=request.project_id,
        text_id=request.text_id,
        calculation_type=request.agreement_type,
        annotator_pairs=request.annotator_ids,
        agreement_scope=request.scope,
        agreement_score=result.score,
        confidence_interval={"lower": result.confidence_interval[0], "upper": result.confidence_interval[1]},
        calculation_parameters=request.parameters or {},
        calculated_by=current_user.id,
        detailed_results=result.detailed_results,
        interpretation=result.interpretation,
        calculation_time_ms=result.calculation_time_ms,
        annotations_analyzed=result.annotations_analyzed
    )
    
    db.add(calculation_record)
    db.commit()
    db.refresh(calculation_record)
    
    return AgreementCalculationResponse(**calculation_record.__dict__)

@router.get("/quality/metrics/{annotator_id}")
async def get_annotator_quality_metrics(
    annotator_id: int,
    project_id: Optional[int] = None,
    time_period: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive quality metrics for an annotator."""
    
    # Calculate various quality metrics
    metrics_calculator = QualityMetricsCalculator()
    
    # Get annotator's annotations
    annotations = await get_annotator_annotations(
        annotator_id=annotator_id,
        project_id=project_id,
        time_period=time_period,
        db=db
    )
    
    # Calculate metrics
    consistency_metrics = metrics_calculator.calculate_annotator_consistency(
        annotator_id, annotations
    )
    
    completeness_metrics = metrics_calculator.calculate_annotation_completeness(
        project_id, annotator_id, 
        expected_annotations=await get_expected_annotation_count(annotator_id, project_id, db),
        actual_annotations=len(annotations)
    )
    
    efficiency_metrics = metrics_calculator.calculate_efficiency_metrics(
        annotations,
        time_spent_hours=await get_annotator_time_spent(annotator_id, project_id, time_period, db)
    )
    
    return {
        "annotator_id": annotator_id,
        "project_id": project_id,
        "time_period": time_period,
        "consistency": consistency_metrics,
        "completeness": completeness_metrics,
        "efficiency": efficiency_metrics,
        "total_annotations": len(annotations),
        "calculated_at": datetime.utcnow()
    }
```

This comprehensive quality metrics system provides detailed insights into annotation quality, consistency, and inter-annotator agreement, enabling research teams to maintain high standards and identify areas for improvement.