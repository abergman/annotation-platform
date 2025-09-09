"""
Database models for storing inter-annotator agreement calculations.

These models support storing agreement metrics, analysis results, and
historical tracking of annotation quality over time.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

Base = declarative_base()


class AgreementStudy(Base):
    """
    Represents a complete agreement study/analysis session.
    Groups related agreement calculations together.
    """
    __tablename__ = 'agreement_studies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    dataset_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Study metadata
    n_annotators = Column(Integer, nullable=False)
    n_items = Column(Integer, nullable=False)
    annotation_categories = Column(JSON, nullable=True)  # List of possible annotation values
    annotator_names = Column(JSON, nullable=True)  # List of annotator identifiers
    
    # Study configuration
    metrics_calculated = Column(JSON, nullable=True)  # Which metrics were computed
    study_parameters = Column(JSON, nullable=True)   # Additional parameters used
    
    # Overall results summary
    overall_quality_score = Column(Float, nullable=True)
    quality_interpretation = Column(String(100), nullable=True)
    study_status = Column(String(50), default='completed')  # 'in_progress', 'completed', 'failed'
    
    # Relationships
    cohen_kappa_results = relationship("CohenKappaResult", back_populates="study")
    fleiss_kappa_results = relationship("FleissKappaResult", back_populates="study")
    krippendorff_alpha_results = relationship("KrippendorffAlphaResult", back_populates="study")
    study_recommendations = relationship("StudyRecommendation", back_populates="study")
    
    def __repr__(self):
        return f"<AgreementStudy(id={self.id}, name='{self.name}', n_annotators={self.n_annotators})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert study to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'dataset_name': self.dataset_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'n_annotators': self.n_annotators,
            'n_items': self.n_items,
            'annotation_categories': self.annotation_categories,
            'annotator_names': self.annotator_names,
            'metrics_calculated': self.metrics_calculated,
            'study_parameters': self.study_parameters,
            'overall_quality_score': self.overall_quality_score,
            'quality_interpretation': self.quality_interpretation,
            'study_status': self.study_status
        }


class CohenKappaResult(Base):
    """
    Stores Cohen's Kappa calculations for pairs of annotators.
    """
    __tablename__ = 'cohen_kappa_results'
    
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'), nullable=False)
    
    # Annotator information
    annotator1_name = Column(String(255), nullable=False)
    annotator2_name = Column(String(255), nullable=False)
    
    # Kappa statistics
    kappa_value = Column(Float, nullable=False)
    standard_error = Column(Float, nullable=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    
    # Agreement statistics
    observed_agreement = Column(Float, nullable=True)
    expected_agreement = Column(Float, nullable=True)
    
    # Additional metrics
    weighted_kappa = Column(Boolean, default=False)
    weight_type = Column(String(50), nullable=True)  # 'linear', 'quadratic'
    
    # Metadata
    n_items = Column(Integer, nullable=False)
    categories = Column(JSON, nullable=True)  # List of annotation categories
    confusion_matrix = Column(JSON, nullable=True)  # Confusion matrix as nested list
    
    # Interpretation
    interpretation = Column(String(100), nullable=True)
    quality_level = Column(String(50), nullable=True)  # 'poor', 'fair', 'moderate', etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    study = relationship("AgreementStudy", back_populates="cohen_kappa_results")
    
    def __repr__(self):
        return f"<CohenKappaResult(id={self.id}, kappa={self.kappa_value:.4f}, {self.annotator1_name} vs {self.annotator2_name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            'id': self.id,
            'study_id': self.study_id,
            'annotator1_name': self.annotator1_name,
            'annotator2_name': self.annotator2_name,
            'kappa_value': self.kappa_value,
            'standard_error': self.standard_error,
            'confidence_interval_lower': self.confidence_interval_lower,
            'confidence_interval_upper': self.confidence_interval_upper,
            'observed_agreement': self.observed_agreement,
            'expected_agreement': self.expected_agreement,
            'weighted_kappa': self.weighted_kappa,
            'weight_type': self.weight_type,
            'n_items': self.n_items,
            'categories': self.categories,
            'confusion_matrix': self.confusion_matrix,
            'interpretation': self.interpretation,
            'quality_level': self.quality_level,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FleissKappaResult(Base):
    """
    Stores Fleiss' Kappa calculations for multiple annotators.
    """
    __tablename__ = 'fleiss_kappa_results'
    
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'), nullable=False)
    
    # Kappa statistics
    kappa_value = Column(Float, nullable=False)
    standard_error = Column(Float, nullable=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    
    # Agreement statistics
    observed_agreement = Column(Float, nullable=True)
    expected_agreement = Column(Float, nullable=True)
    
    # Study parameters
    n_annotators = Column(Integer, nullable=False)
    n_items = Column(Integer, nullable=False)
    categories = Column(JSON, nullable=True)  # List of annotation categories
    
    # Per-category statistics
    category_statistics = Column(JSON, nullable=True)  # Dict of category stats
    
    # Interpretation
    interpretation = Column(String(100), nullable=True)
    quality_level = Column(String(50), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    study = relationship("AgreementStudy", back_populates="fleiss_kappa_results")
    
    def __repr__(self):
        return f"<FleissKappaResult(id={self.id}, kappa={self.kappa_value:.4f}, n_annotators={self.n_annotators})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            'id': self.id,
            'study_id': self.study_id,
            'kappa_value': self.kappa_value,
            'standard_error': self.standard_error,
            'confidence_interval_lower': self.confidence_interval_lower,
            'confidence_interval_upper': self.confidence_interval_upper,
            'observed_agreement': self.observed_agreement,
            'expected_agreement': self.expected_agreement,
            'n_annotators': self.n_annotators,
            'n_items': self.n_items,
            'categories': self.categories,
            'category_statistics': self.category_statistics,
            'interpretation': self.interpretation,
            'quality_level': self.quality_level,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class KrippendorffAlphaResult(Base):
    """
    Stores Krippendorff's Alpha calculations.
    """
    __tablename__ = 'krippendorff_alpha_results'
    
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'), nullable=False)
    
    # Alpha statistics
    alpha_value = Column(Float, nullable=False)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    
    # Disagreement statistics
    observed_disagreement = Column(Float, nullable=True)
    expected_disagreement = Column(Float, nullable=True)
    
    # Study parameters
    n_annotators = Column(Integer, nullable=False)
    n_items = Column(Integer, nullable=False)
    n_pairs = Column(Integer, nullable=True)  # Number of annotation pairs analyzed
    distance_metric = Column(String(50), nullable=False)  # 'nominal', 'ordinal', etc.
    missing_value_handling = Column(String(100), nullable=True)
    
    # Bootstrap parameters (if used)
    bootstrap_iterations = Column(Integer, nullable=True)
    bootstrap_confidence_level = Column(Float, nullable=True)
    
    # Interpretation
    interpretation = Column(String(100), nullable=True)
    quality_level = Column(String(50), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    study = relationship("AgreementStudy", back_populates="krippendorff_alpha_results")
    
    def __repr__(self):
        return f"<KrippendorffAlphaResult(id={self.id}, alpha={self.alpha_value:.4f}, metric={self.distance_metric})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            'id': self.id,
            'study_id': self.study_id,
            'alpha_value': self.alpha_value,
            'confidence_interval_lower': self.confidence_interval_lower,
            'confidence_interval_upper': self.confidence_interval_upper,
            'observed_disagreement': self.observed_disagreement,
            'expected_disagreement': self.expected_disagreement,
            'n_annotators': self.n_annotators,
            'n_items': self.n_items,
            'n_pairs': self.n_pairs,
            'distance_metric': self.distance_metric,
            'missing_value_handling': self.missing_value_handling,
            'bootstrap_iterations': self.bootstrap_iterations,
            'bootstrap_confidence_level': self.bootstrap_confidence_level,
            'interpretation': self.interpretation,
            'quality_level': self.quality_level,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class StudyRecommendation(Base):
    """
    Stores recommendations generated from agreement analysis.
    """
    __tablename__ = 'study_recommendations'
    
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('agreement_studies.id'), nullable=False)
    
    # Recommendation details
    recommendation_type = Column(String(100), nullable=False)  # 'training', 'guidelines', etc.
    recommendation_text = Column(Text, nullable=False)
    priority_level = Column(String(50), nullable=True)  # 'high', 'medium', 'low'
    
    # Context
    triggered_by_metric = Column(String(100), nullable=True)  # Which metric triggered this
    threshold_value = Column(Float, nullable=True)  # The threshold that was crossed
    actual_value = Column(Float, nullable=True)     # The actual metric value
    
    # Action tracking
    implemented = Column(Boolean, default=False)
    implementation_notes = Column(Text, nullable=True)
    implemented_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    study = relationship("AgreementStudy", back_populates="study_recommendations")
    
    def __repr__(self):
        return f"<StudyRecommendation(id={self.id}, type={self.recommendation_type}, priority={self.priority_level})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation to dictionary representation."""
        return {
            'id': self.id,
            'study_id': self.study_id,
            'recommendation_type': self.recommendation_type,
            'recommendation_text': self.recommendation_text,
            'priority_level': self.priority_level,
            'triggered_by_metric': self.triggered_by_metric,
            'threshold_value': self.threshold_value,
            'actual_value': self.actual_value,
            'implemented': self.implemented,
            'implementation_notes': self.implementation_notes,
            'implemented_at': self.implemented_at.isoformat() if self.implemented_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AnnotatorPerformance(Base):
    """
    Tracks individual annotator performance across studies.
    """
    __tablename__ = 'annotator_performance'
    
    id = Column(Integer, primary_key=True)
    annotator_name = Column(String(255), nullable=False)
    
    # Performance metrics
    studies_participated = Column(Integer, default=0)
    average_kappa_score = Column(Float, nullable=True)
    consistency_rating = Column(String(50), nullable=True)  # 'excellent', 'good', etc.
    
    # Detailed performance tracking
    performance_history = Column(JSON, nullable=True)  # List of performance records
    improvement_trend = Column(String(50), nullable=True)  # 'improving', 'stable', 'declining'
    
    # Metadata
    first_study_date = Column(DateTime(timezone=True), nullable=True)
    last_study_date = Column(DateTime(timezone=True), nullable=True)
    total_items_annotated = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<AnnotatorPerformance(annotator='{self.annotator_name}', avg_kappa={self.average_kappa_score})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert performance record to dictionary representation."""
        return {
            'id': self.id,
            'annotator_name': self.annotator_name,
            'studies_participated': self.studies_participated,
            'average_kappa_score': self.average_kappa_score,
            'consistency_rating': self.consistency_rating,
            'performance_history': self.performance_history,
            'improvement_trend': self.improvement_trend,
            'first_study_date': self.first_study_date.isoformat() if self.first_study_date else None,
            'last_study_date': self.last_study_date.isoformat() if self.last_study_date else None,
            'total_items_annotated': self.total_items_annotated,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Database utility functions

def create_tables(engine):
    """Create all agreement-related tables."""
    Base.metadata.create_all(engine)


def get_study_summary(session, study_id: int) -> Dict[str, Any]:
    """
    Get a comprehensive summary of an agreement study.
    """
    study = session.query(AgreementStudy).filter_by(id=study_id).first()
    if not study:
        return None
    
    summary = study.to_dict()
    
    # Add results
    summary['cohen_kappa_results'] = [
        result.to_dict() for result in study.cohen_kappa_results
    ]
    summary['fleiss_kappa_results'] = [
        result.to_dict() for result in study.fleiss_kappa_results  
    ]
    summary['krippendorff_alpha_results'] = [
        result.to_dict() for result in study.krippendorff_alpha_results
    ]
    summary['recommendations'] = [
        rec.to_dict() for rec in study.study_recommendations
    ]
    
    return summary


def store_agreement_analysis(session, analysis_results: Dict[str, Any], 
                           study_name: str, description: str = None) -> int:
    """
    Store complete agreement analysis results in database.
    
    Returns the created study ID.
    """
    # Create study record
    study = AgreementStudy(
        name=study_name,
        description=description,
        n_annotators=analysis_results['dataset_info']['n_annotators'],
        n_items=analysis_results['dataset_info']['n_items'],
        annotator_names=analysis_results['dataset_info']['annotators'],
        metrics_calculated=list(analysis_results['metrics'].keys())
    )
    
    session.add(study)
    session.flush()  # Get the ID
    
    # Store Cohen's Kappa results
    if 'pairwise_cohen_kappa' in analysis_results['metrics']:
        for pair_name, result in analysis_results['metrics']['pairwise_cohen_kappa'].items():
            annotator1, annotator2 = pair_name.split('_vs_')
            
            cohen_result = CohenKappaResult(
                study_id=study.id,
                annotator1_name=annotator1,
                annotator2_name=annotator2,
                kappa_value=result['kappa'],
                standard_error=result.get('standard_error'),
                confidence_interval_lower=result.get('ci_lower'),
                confidence_interval_upper=result.get('ci_upper'),
                observed_agreement=result.get('observed_agreement'),
                expected_agreement=result.get('expected_agreement'),
                n_items=result['n_items'],
                categories=result.get('categories'),
                confusion_matrix=result.get('confusion_matrix'),
                interpretation=result.get('interpretation')
            )
            session.add(cohen_result)
    
    # Store Fleiss' Kappa results
    if 'fleiss_kappa' in analysis_results['metrics']:
        result = analysis_results['metrics']['fleiss_kappa']
        fleiss_result = FleissKappaResult(
            study_id=study.id,
            kappa_value=result['kappa'],
            standard_error=result.get('standard_error'),
            confidence_interval_lower=result.get('ci_lower'),
            confidence_interval_upper=result.get('ci_upper'),
            observed_agreement=result.get('observed_agreement'),
            expected_agreement=result.get('expected_agreement'),
            n_annotators=result['n_annotators'],
            n_items=result['n_items'],
            categories=result.get('categories'),
            category_statistics=result.get('category_stats'),
            interpretation=result.get('interpretation')
        )
        session.add(fleiss_result)
    
    # Store Krippendorff's Alpha results
    if 'krippendorff_alpha' in analysis_results['metrics']:
        result = analysis_results['metrics']['krippendorff_alpha']
        alpha_result = KrippendorffAlphaResult(
            study_id=study.id,
            alpha_value=result['alpha'],
            confidence_interval_lower=result.get('ci_lower'),
            confidence_interval_upper=result.get('ci_upper'),
            observed_disagreement=result.get('observed_disagreement'),
            expected_disagreement=result.get('expected_disagreement'),
            n_annotators=result['n_annotators'],
            n_items=result['n_items'],
            n_pairs=result.get('n_pairs'),
            distance_metric=result.get('metric', 'nominal'),
            interpretation=result.get('interpretation')
        )
        session.add(alpha_result)
    
    # Store recommendations if present
    if 'summary' in analysis_results and 'recommendations' in analysis_results['summary']:
        for rec_text in analysis_results['summary']['recommendations']:
            recommendation = StudyRecommendation(
                study_id=study.id,
                recommendation_type='general',
                recommendation_text=rec_text,
                priority_level='medium'
            )
            session.add(recommendation)
    
    session.commit()
    return study.id