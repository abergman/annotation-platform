"""
Inter-Annotator Agreement Integration

Integrates the conflict resolution system with the existing inter-annotator agreement
analysis system. Provides bi-directional integration for quality metrics and
conflict resolution insights.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from src.models.conflict import (
    AnnotationConflict, ConflictResolution, ConflictSettings,
    ConflictStatus, ConflictType, ResolutionOutcome
)
from src.models.agreement import (
    AgreementStudy, CohenKappaResult, FleissKappaResult, 
    KrippendorffAlphaResult, StudyRecommendation,
    AnnotatorPerformance
)
from src.models.annotation import Annotation
from src.models.user import User
from src.models.project import Project
from src.core.conflict_detection import ConflictDetectionEngine
from src.core.conflict_resolution import ConflictResolutionEngine

logger = logging.getLogger(__name__)


@dataclass
class ConflictImpactMetrics:
    """Metrics showing how conflicts impact agreement scores."""
    baseline_agreement: float
    post_resolution_agreement: float
    agreement_improvement: float
    conflict_resolution_effectiveness: float
    annotator_consensus_improvement: float


@dataclass
class QualityInsights:
    """Quality insights from conflict analysis."""
    frequent_conflict_patterns: List[Dict[str, Any]]
    problematic_annotator_pairs: List[Tuple[str, str, float]]
    improvement_recommendations: List[str]
    conflict_hotspots: List[Dict[str, Any]]
    resolution_effectiveness: Dict[str, float]


class ConflictAgreementAnalyzer:
    """Analyzer for conflict impact on inter-annotator agreement."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.logger = logging.getLogger(__name__)
    
    def analyze_conflict_impact_on_agreement(
        self, 
        project_id: int,
        study_id: Optional[int] = None,
        time_window_days: int = 30
    ) -> ConflictImpactMetrics:
        """
        Analyze how conflicts and their resolutions impact agreement scores.
        
        Args:
            project_id: Project to analyze
            study_id: Specific agreement study to compare against (optional)
            time_window_days: Time window for analysis
            
        Returns:
            Metrics showing conflict impact on agreement
        """
        cutoff_date = datetime.utcnow() - timedelta(days=time_window_days)
        
        # Get baseline agreement scores (before conflict resolution)
        baseline_agreement = self._calculate_baseline_agreement(
            project_id, study_id, cutoff_date
        )
        
        # Get current agreement scores (after conflict resolution)
        current_agreement = self._calculate_current_agreement(project_id, study_id)
        
        # Calculate improvement
        agreement_improvement = current_agreement - baseline_agreement
        
        # Analyze conflict resolution effectiveness
        resolution_effectiveness = self._calculate_resolution_effectiveness(
            project_id, cutoff_date
        )
        
        # Calculate consensus improvement
        consensus_improvement = self._calculate_consensus_improvement(
            project_id, cutoff_date
        )
        
        return ConflictImpactMetrics(
            baseline_agreement=baseline_agreement,
            post_resolution_agreement=current_agreement,
            agreement_improvement=agreement_improvement,
            conflict_resolution_effectiveness=resolution_effectiveness,
            annotator_consensus_improvement=consensus_improvement
        )
    
    def identify_agreement_based_conflicts(
        self, 
        project_id: int,
        kappa_threshold: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Identify potential conflicts based on low agreement scores.
        
        Args:
            project_id: Project to analyze
            kappa_threshold: Minimum kappa score threshold
            
        Returns:
            List of potential conflict areas based on agreement analysis
        """
        # Get recent agreement studies for the project
        studies = (
            self.db.query(AgreementStudy)
            .filter_by(dataset_name=f"project_{project_id}")
            .order_by(AgreementStudy.created_at.desc())
            .limit(5)
            .all()
        )
        
        conflict_candidates = []
        
        for study in studies:
            # Analyze Cohen's Kappa results for problematic pairs
            cohen_results = (
                self.db.query(CohenKappaResult)
                .filter(
                    CohenKappaResult.study_id == study.id,
                    CohenKappaResult.kappa_value < kappa_threshold
                )
                .all()
            )
            
            for result in cohen_results:
                # Find annotations from these annotators that might conflict
                potential_conflicts = self._find_annotations_from_pair(
                    project_id,
                    result.annotator1_name,
                    result.annotator2_name
                )
                
                if potential_conflicts:
                    conflict_candidates.append({
                        "annotator_pair": (result.annotator1_name, result.annotator2_name),
                        "kappa_score": result.kappa_value,
                        "study_id": study.id,
                        "potential_annotation_conflicts": len(potential_conflicts),
                        "recommendation": self._generate_agreement_recommendation(result),
                        "priority": "high" if result.kappa_value < 0.2 else "medium"
                    })
        
        return conflict_candidates
    
    def update_annotator_performance_from_conflicts(
        self, 
        project_id: int
    ) -> Dict[str, Any]:
        """
        Update annotator performance metrics based on conflict resolution data.
        
        Args:
            project_id: Project to update performance for
            
        Returns:
            Summary of performance updates
        """
        # Get all resolved conflicts for the project
        resolved_conflicts = (
            self.db.query(AnnotationConflict)
            .filter(
                AnnotationConflict.project_id == project_id,
                AnnotationConflict.status == ConflictStatus.RESOLVED
            )
            .all()
        )
        
        annotator_stats = {}
        
        # Analyze each resolved conflict
        for conflict in resolved_conflicts:
            # Get annotators involved
            annotator_a = conflict.annotation_a.annotator
            annotator_b = conflict.annotation_b.annotator
            
            # Update statistics for each annotator
            for annotator in [annotator_a, annotator_b]:
                if annotator.username not in annotator_stats:
                    annotator_stats[annotator.username] = {
                        "conflicts_involved": 0,
                        "conflicts_resolved_favorably": 0,
                        "avg_conflict_score": 0.0,
                        "resolution_outcomes": []
                    }
                
                stats = annotator_stats[annotator.username]
                stats["conflicts_involved"] += 1
                
                # Check resolution outcome
                resolutions = conflict.resolutions
                if resolutions:
                    latest_resolution = max(resolutions, key=lambda r: r.created_at)
                    
                    # Determine if resolution favored this annotator
                    if self._resolution_favored_annotator(latest_resolution, annotator):
                        stats["conflicts_resolved_favorably"] += 1
                    
                    stats["resolution_outcomes"].append(latest_resolution.outcome.value if latest_resolution.outcome else "unknown")
                
                # Update average conflict score
                total_score = stats["avg_conflict_score"] * (stats["conflicts_involved"] - 1)
                stats["avg_conflict_score"] = (total_score + conflict.conflict_score) / stats["conflicts_involved"]
        
        # Update AnnotatorPerformance records
        updates_made = 0
        for username, stats in annotator_stats.items():
            performance = (
                self.db.query(AnnotatorPerformance)
                .filter_by(annotator_name=username)
                .first()
            )
            
            if performance:
                # Update existing record with conflict data
                if performance.performance_history is None:
                    performance.performance_history = []
                
                performance.performance_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "conflicts_involved": stats["conflicts_involved"],
                    "conflicts_resolved_favorably": stats["conflicts_resolved_favorably"],
                    "avg_conflict_score": stats["avg_conflict_score"],
                    "favorable_resolution_rate": stats["conflicts_resolved_favorably"] / stats["conflicts_involved"] if stats["conflicts_involved"] > 0 else 0
                })
                
                performance.updated_at = datetime.utcnow()
                updates_made += 1
        
        self.db.commit()
        
        return {
            "annotators_analyzed": len(annotator_stats),
            "performance_records_updated": updates_made,
            "total_conflicts_analyzed": len(resolved_conflicts),
            "summary": annotator_stats
        }
    
    def generate_quality_insights(self, project_id: int) -> QualityInsights:
        """
        Generate comprehensive quality insights from conflict and agreement data.
        
        Args:
            project_id: Project to analyze
            
        Returns:
            Quality insights and recommendations
        """
        # Analyze conflict patterns
        conflict_patterns = self._analyze_conflict_patterns(project_id)
        
        # Identify problematic annotator pairs
        problematic_pairs = self._identify_problematic_pairs(project_id)
        
        # Generate improvement recommendations
        recommendations = self._generate_improvement_recommendations(
            project_id, conflict_patterns, problematic_pairs
        )
        
        # Identify conflict hotspots
        hotspots = self._identify_conflict_hotspots(project_id)
        
        # Analyze resolution effectiveness
        resolution_effectiveness = self._analyze_resolution_effectiveness(project_id)
        
        return QualityInsights(
            frequent_conflict_patterns=conflict_patterns,
            problematic_annotator_pairs=problematic_pairs,
            improvement_recommendations=recommendations,
            conflict_hotspots=hotspots,
            resolution_effectiveness=resolution_effectiveness
        )
    
    def _calculate_baseline_agreement(
        self, 
        project_id: int, 
        study_id: Optional[int], 
        cutoff_date: datetime
    ) -> float:
        """Calculate baseline agreement score before conflicts were resolved."""
        if study_id:
            # Use specific study
            study = self.db.query(AgreementStudy).filter_by(id=study_id).first()
            if study:
                return study.overall_quality_score or 0.0
        
        # Calculate from historical data
        # This is a simplified calculation - in practice, you'd want more sophisticated logic
        historical_studies = (
            self.db.query(AgreementStudy)
            .filter(
                AgreementStudy.dataset_name == f"project_{project_id}",
                AgreementStudy.created_at <= cutoff_date
            )
            .order_by(AgreementStudy.created_at.desc())
            .limit(3)
            .all()
        )
        
        if historical_studies:
            scores = [s.overall_quality_score for s in historical_studies if s.overall_quality_score]
            return sum(scores) / len(scores) if scores else 0.0
        
        return 0.0
    
    def _calculate_current_agreement(self, project_id: int, study_id: Optional[int]) -> float:
        """Calculate current agreement score."""
        # Get most recent study
        recent_study = (
            self.db.query(AgreementStudy)
            .filter_by(dataset_name=f"project_{project_id}")
            .order_by(AgreementStudy.created_at.desc())
            .first()
        )
        
        if recent_study and recent_study.overall_quality_score:
            return recent_study.overall_quality_score
        
        # Fallback calculation
        return self._estimate_current_agreement(project_id)
    
    def _estimate_current_agreement(self, project_id: int) -> float:
        """Estimate current agreement based on conflict resolution success."""
        # Get resolved conflicts
        resolved_conflicts = (
            self.db.query(AnnotationConflict)
            .filter(
                AnnotationConflict.project_id == project_id,
                AnnotationConflict.status == ConflictStatus.RESOLVED
            )
            .all()
        )
        
        if not resolved_conflicts:
            return 0.0
        
        # Calculate success rate based on resolution confidence
        total_confidence = sum(
            max([r.confidence_score for r in conflict.resolutions], default=0.0)
            for conflict in resolved_conflicts
        )
        
        return total_confidence / len(resolved_conflicts) if resolved_conflicts else 0.0
    
    def _calculate_resolution_effectiveness(self, project_id: int, cutoff_date: datetime) -> float:
        """Calculate how effective conflict resolutions have been."""
        recent_resolutions = (
            self.db.query(ConflictResolution)
            .join(ConflictResolution.conflict)
            .filter(
                AnnotationConflict.project_id == project_id,
                ConflictResolution.completed_at >= cutoff_date,
                ConflictResolution.completed_at.isnot(None)
            )
            .all()
        )
        
        if not recent_resolutions:
            return 0.0
        
        successful_resolutions = [
            r for r in recent_resolutions 
            if r.confidence_score and r.confidence_score >= 0.7
        ]
        
        return len(successful_resolutions) / len(recent_resolutions)
    
    def _calculate_consensus_improvement(self, project_id: int, cutoff_date: datetime) -> float:
        """Calculate improvement in annotator consensus."""
        # This is a placeholder calculation
        # In practice, you'd compare agreement metrics before and after conflict resolution
        
        resolved_conflicts = (
            self.db.query(AnnotationConflict)
            .filter(
                AnnotationConflict.project_id == project_id,
                AnnotationConflict.status == ConflictStatus.RESOLVED,
                AnnotationConflict.resolved_at >= cutoff_date
            )
            .all()
        )
        
        if not resolved_conflicts:
            return 0.0
        
        # Estimate consensus improvement based on conflict scores and resolutions
        total_improvement = 0.0
        for conflict in resolved_conflicts:
            # Higher conflict scores that get resolved indicate better consensus improvement
            improvement = conflict.conflict_score * 0.5  # Placeholder calculation
            total_improvement += improvement
        
        return total_improvement / len(resolved_conflicts) if resolved_conflicts else 0.0
    
    def _find_annotations_from_pair(
        self, 
        project_id: int, 
        annotator1: str, 
        annotator2: str
    ) -> List[Annotation]:
        """Find annotations from a specific pair of annotators."""
        return (
            self.db.query(Annotation)
            .join(Annotation.text)
            .join(Annotation.annotator)
            .filter(
                Annotation.text.has(project_id=project_id),
                User.username.in_([annotator1, annotator2])
            )
            .all()
        )
    
    def _generate_agreement_recommendation(self, kappa_result: CohenKappaResult) -> str:
        """Generate recommendation based on kappa score."""
        if kappa_result.kappa_value < 0.0:
            return "Poor agreement - consider retraining annotators and reviewing guidelines"
        elif kappa_result.kappa_value < 0.2:
            return "Slight agreement - review annotation guidelines and provide additional training"
        elif kappa_result.kappa_value < 0.4:
            return "Fair agreement - discuss specific disagreements and clarify guidelines"
        elif kappa_result.kappa_value < 0.6:
            return "Moderate agreement - minor guideline clarifications may be helpful"
        else:
            return "Substantial agreement - maintain current practices"
    
    def _resolution_favored_annotator(
        self, 
        resolution: ConflictResolution, 
        annotator: User
    ) -> bool:
        """Check if a resolution outcome favored a specific annotator."""
        if not resolution.outcome or not resolution.final_annotation:
            return False
        
        # Check if the final annotation belongs to this annotator
        return resolution.final_annotation.annotator_id == annotator.id
    
    def _analyze_conflict_patterns(self, project_id: int) -> List[Dict[str, Any]]:
        """Analyze common conflict patterns in the project."""
        # Get all conflicts for the project
        conflicts = (
            self.db.query(AnnotationConflict)
            .filter_by(project_id=project_id)
            .all()
        )
        
        # Analyze patterns
        type_counts = {}
        severity_counts = {}
        
        for conflict in conflicts:
            # Count by type
            conflict_type = conflict.conflict_type.value
            type_counts[conflict_type] = type_counts.get(conflict_type, 0) + 1
            
            # Count by severity
            severity = conflict.severity_level
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        patterns = []
        
        # Add type patterns
        for conflict_type, count in type_counts.items():
            patterns.append({
                "pattern_type": "conflict_type",
                "pattern_value": conflict_type,
                "frequency": count,
                "percentage": count / len(conflicts) * 100 if conflicts else 0
            })
        
        # Add severity patterns
        for severity, count in severity_counts.items():
            patterns.append({
                "pattern_type": "severity_level",
                "pattern_value": severity,
                "frequency": count,
                "percentage": count / len(conflicts) * 100 if conflicts else 0
            })
        
        return sorted(patterns, key=lambda x: x["frequency"], reverse=True)
    
    def _identify_problematic_pairs(self, project_id: int) -> List[Tuple[str, str, float]]:
        """Identify annotator pairs with frequent conflicts."""
        conflicts = (
            self.db.query(AnnotationConflict)
            .filter_by(project_id=project_id)
            .all()
        )
        
        pair_conflicts = {}
        
        for conflict in conflicts:
            annotator_a = conflict.annotation_a.annotator.username
            annotator_b = conflict.annotation_b.annotator.username
            
            # Create consistent pair key
            pair_key = tuple(sorted([annotator_a, annotator_b]))
            
            if pair_key not in pair_conflicts:
                pair_conflicts[pair_key] = {"count": 0, "total_score": 0.0}
            
            pair_conflicts[pair_key]["count"] += 1
            pair_conflicts[pair_key]["total_score"] += conflict.conflict_score
        
        # Calculate problematic pairs
        problematic_pairs = []
        for pair_key, stats in pair_conflicts.items():
            avg_score = stats["total_score"] / stats["count"]
            if stats["count"] >= 3 or avg_score >= 0.7:  # Threshold for "problematic"
                problematic_pairs.append((pair_key[0], pair_key[1], avg_score))
        
        return sorted(problematic_pairs, key=lambda x: x[2], reverse=True)
    
    def _generate_improvement_recommendations(
        self, 
        project_id: int,
        conflict_patterns: List[Dict[str, Any]],
        problematic_pairs: List[Tuple[str, str, float]]
    ) -> List[str]:
        """Generate improvement recommendations based on analysis."""
        recommendations = []
        
        # Analyze most common conflict types
        type_patterns = [p for p in conflict_patterns if p["pattern_type"] == "conflict_type"]
        if type_patterns:
            most_common = type_patterns[0]
            if most_common["frequency"] > 5:
                if most_common["pattern_value"] == "span_overlap":
                    recommendations.append("Consider providing clearer guidelines for text span boundaries")
                elif most_common["pattern_value"] == "label_conflict":
                    recommendations.append("Review and clarify label definitions to reduce ambiguity")
        
        # Analyze problematic pairs
        if len(problematic_pairs) > 2:
            recommendations.append("Multiple annotator pairs showing high conflict rates - consider additional training sessions")
        
        # Analyze severity patterns
        severity_patterns = [p for p in conflict_patterns if p["pattern_type"] == "severity_level"]
        high_severity = [p for p in severity_patterns if p["pattern_value"] in ["high", "critical"]]
        if high_severity and sum(p["frequency"] for p in high_severity) > 10:
            recommendations.append("High number of severe conflicts detected - recommend comprehensive guideline review")
        
        return recommendations
    
    def _identify_conflict_hotspots(self, project_id: int) -> List[Dict[str, Any]]:
        """Identify texts or sections with high conflict rates."""
        # Group conflicts by text
        text_conflicts = (
            self.db.query(
                AnnotationConflict.text_id,
                func.count(AnnotationConflict.id).label('conflict_count'),
                func.avg(AnnotationConflict.conflict_score).label('avg_score')
            )
            .filter_by(project_id=project_id)
            .group_by(AnnotationConflict.text_id)
            .having(func.count(AnnotationConflict.id) >= 3)  # At least 3 conflicts
            .all()
        )
        
        hotspots = []
        for text_id, conflict_count, avg_score in text_conflicts:
            hotspots.append({
                "text_id": text_id,
                "conflict_count": conflict_count,
                "average_conflict_score": float(avg_score) if avg_score else 0.0,
                "hotspot_type": "text",
                "severity": "high" if conflict_count >= 5 else "medium"
            })
        
        return sorted(hotspots, key=lambda x: x["conflict_count"], reverse=True)
    
    def _analyze_resolution_effectiveness(self, project_id: int) -> Dict[str, float]:
        """Analyze effectiveness of different resolution strategies."""
        resolutions = (
            self.db.query(ConflictResolution)
            .join(ConflictResolution.conflict)
            .filter(AnnotationConflict.project_id == project_id)
            .all()
        )
        
        strategy_stats = {}
        
        for resolution in resolutions:
            strategy = resolution.resolution_strategy.value if resolution.resolution_strategy else "unknown"
            
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {"total": 0, "successful": 0, "avg_confidence": 0.0}
            
            stats = strategy_stats[strategy]
            stats["total"] += 1
            
            if resolution.confidence_score and resolution.confidence_score >= 0.7:
                stats["successful"] += 1
            
            if resolution.confidence_score:
                current_avg = stats["avg_confidence"]
                stats["avg_confidence"] = (current_avg * (stats["total"] - 1) + resolution.confidence_score) / stats["total"]
        
        # Calculate success rates
        effectiveness = {}
        for strategy, stats in strategy_stats.items():
            effectiveness[strategy] = stats["successful"] / stats["total"] if stats["total"] > 0 else 0.0
        
        return effectiveness


# Integration service class

class AgreementConflictIntegration:
    """Main service for integrating agreement analysis with conflict resolution."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.analyzer = ConflictAgreementAnalyzer(db_session)
        self.conflict_engine = ConflictDetectionEngine(db_session)
        self.resolution_engine = ConflictResolutionEngine(db_session)
    
    def run_integrated_quality_analysis(self, project_id: int) -> Dict[str, Any]:
        """Run comprehensive quality analysis integrating conflicts and agreement."""
        try:
            # Analyze conflict impact on agreement
            impact_metrics = self.analyzer.analyze_conflict_impact_on_agreement(project_id)
            
            # Identify agreement-based conflict candidates
            agreement_conflicts = self.analyzer.identify_agreement_based_conflicts(project_id)
            
            # Update annotator performance
            performance_updates = self.analyzer.update_annotator_performance_from_conflicts(project_id)
            
            # Generate quality insights
            quality_insights = self.analyzer.generate_quality_insights(project_id)
            
            # Create study recommendations based on conflict analysis
            recommendations = self._create_integration_recommendations(
                project_id, impact_metrics, quality_insights
            )
            
            return {
                "project_id": project_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "conflict_impact_metrics": {
                    "baseline_agreement": impact_metrics.baseline_agreement,
                    "current_agreement": impact_metrics.post_resolution_agreement,
                    "improvement": impact_metrics.agreement_improvement,
                    "resolution_effectiveness": impact_metrics.conflict_resolution_effectiveness,
                    "consensus_improvement": impact_metrics.annotator_consensus_improvement
                },
                "agreement_based_conflicts": agreement_conflicts,
                "performance_updates": performance_updates,
                "quality_insights": {
                    "conflict_patterns": quality_insights.frequent_conflict_patterns,
                    "problematic_pairs": [
                        {"annotator_1": pair[0], "annotator_2": pair[1], "conflict_score": pair[2]}
                        for pair in quality_insights.problematic_annotator_pairs
                    ],
                    "recommendations": quality_insights.improvement_recommendations,
                    "hotspots": quality_insights.conflict_hotspots,
                    "resolution_effectiveness": quality_insights.resolution_effectiveness
                },
                "integration_recommendations": recommendations
            }
        
        except Exception as e:
            logger.error(f"Error in integrated quality analysis: {e}")
            raise
    
    def _create_integration_recommendations(
        self, 
        project_id: int,
        impact_metrics: ConflictImpactMetrics,
        quality_insights: QualityInsights
    ) -> List[Dict[str, Any]]:
        """Create recommendations based on integrated analysis."""
        recommendations = []
        
        # Agreement improvement recommendations
        if impact_metrics.agreement_improvement < 0.1:
            recommendations.append({
                "type": "agreement_improvement",
                "priority": "high",
                "title": "Low agreement improvement detected",
                "description": "Conflict resolution has not significantly improved inter-annotator agreement",
                "actions": [
                    "Review conflict resolution strategies",
                    "Consider additional annotator training",
                    "Analyze and update annotation guidelines"
                ]
            })
        
        # Resolution effectiveness recommendations
        if impact_metrics.conflict_resolution_effectiveness < 0.6:
            recommendations.append({
                "type": "resolution_effectiveness",
                "priority": "high",
                "title": "Low conflict resolution effectiveness",
                "description": "Current conflict resolution strategies are not highly effective",
                "actions": [
                    "Review and improve resolution strategies",
                    "Consider expert review for complex conflicts",
                    "Implement weighted voting based on annotator performance"
                ]
            })
        
        # Hotspot recommendations
        if quality_insights.conflict_hotspots:
            high_conflict_texts = [h for h in quality_insights.conflict_hotspots if h["conflict_count"] >= 5]
            if high_conflict_texts:
                recommendations.append({
                    "type": "conflict_hotspots",
                    "priority": "medium",
                    "title": f"High conflict texts identified ({len(high_conflict_texts)} texts)",
                    "description": "Certain texts are generating disproportionately high numbers of conflicts",
                    "actions": [
                        "Review and potentially revise problematic texts",
                        "Provide additional context or guidelines for difficult texts",
                        "Consider expert pre-annotation for challenging content"
                    ]
                })
        
        return recommendations


# Convenience functions

def create_integration_service(db_session: Session) -> AgreementConflictIntegration:
    """Create an agreement-conflict integration service."""
    return AgreementConflictIntegration(db_session)


def run_project_quality_analysis(db_session: Session, project_id: int) -> Dict[str, Any]:
    """Run integrated quality analysis for a project."""
    service = create_integration_service(db_session)
    return service.run_integrated_quality_analysis(project_id)