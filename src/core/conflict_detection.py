"""
Conflict Detection Engine

Advanced algorithms for detecting annotation conflicts including span overlaps,
label disagreements, and quality disputes. Integrates with the annotation system
to provide real-time conflict detection and monitoring.
"""

from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from src.models.annotation import Annotation
from src.models.conflict import (
    AnnotationConflict, ConflictType, ConflictStatus, 
    ConflictSettings, ResolutionStrategy
)
from src.models.project import Project
from src.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class OverlapInfo:
    """Information about span overlap between annotations."""
    start: int
    end: int
    length: int
    percentage_a: float  # Percentage of annotation A that overlaps
    percentage_b: float  # Percentage of annotation B that overlaps
    overlap_type: str    # 'partial', 'complete', 'nested', 'identical'


@dataclass
class ConflictCandidate:
    """Potential conflict detected by the detection engine."""
    annotation_a: Annotation
    annotation_b: Annotation
    conflict_type: ConflictType
    severity_level: str
    confidence_score: float
    overlap_info: Optional[OverlapInfo]
    description: str
    metadata: Dict[str, Any]


class ConflictDetectionEngine:
    """Main engine for detecting annotation conflicts."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.logger = logging.getLogger(__name__)
    
    def detect_conflicts_for_project(
        self, 
        project_id: int,
        check_new_only: bool = True,
        batch_size: int = 1000
    ) -> List[ConflictCandidate]:
        """
        Detect all conflicts for a project.
        
        Args:
            project_id: Project to check for conflicts
            check_new_only: Only check recently added/modified annotations
            batch_size: Number of annotations to process per batch
        
        Returns:
            List of detected conflict candidates
        """
        settings = self._get_project_settings(project_id)
        if not settings.enable_conflict_detection:
            return []
        
        # Get annotations to check
        annotations = self._get_annotations_for_detection(project_id, check_new_only)
        self.logger.info(f"Checking {len(annotations)} annotations for conflicts in project {project_id}")
        
        conflict_candidates = []
        
        # Process annotations in batches
        for i in range(0, len(annotations), batch_size):
            batch = annotations[i:i + batch_size]
            batch_conflicts = self._detect_conflicts_in_batch(batch, settings)
            conflict_candidates.extend(batch_conflicts)
        
        # Filter by confidence threshold
        filtered_conflicts = [
            conflict for conflict in conflict_candidates
            if conflict.confidence_score >= settings.confidence_threshold
        ]
        
        self.logger.info(f"Detected {len(filtered_conflicts)} potential conflicts")
        return filtered_conflicts
    
    def detect_conflicts_for_annotation(
        self, 
        annotation_id: int,
        context_window: int = 1000
    ) -> List[ConflictCandidate]:
        """
        Detect conflicts for a specific annotation.
        
        Args:
            annotation_id: Annotation to check for conflicts
            context_window: Character window around annotation to check
        
        Returns:
            List of detected conflict candidates
        """
        annotation = self.db.query(Annotation).filter_by(id=annotation_id).first()
        if not annotation:
            return []
        
        settings = self._get_project_settings(annotation.project_id)
        if not settings.enable_conflict_detection:
            return []
        
        # Get potentially conflicting annotations in the same text
        candidates = self._get_candidate_annotations(
            annotation, context_window, settings
        )
        
        conflict_candidates = []
        for candidate in candidates:
            conflicts = self._analyze_annotation_pair(annotation, candidate, settings)
            conflict_candidates.extend(conflicts)
        
        return conflict_candidates
    
    def _get_annotations_for_detection(
        self, 
        project_id: int, 
        check_new_only: bool
    ) -> List[Annotation]:
        """Get annotations that need conflict detection."""
        query = (
            self.db.query(Annotation)
            .join(Annotation.text)
            .filter(Annotation.text.has(project_id=project_id))
        )
        
        if check_new_only:
            # Only check annotations created/updated in the last hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            query = query.filter(
                or_(
                    Annotation.created_at >= cutoff_time,
                    Annotation.updated_at >= cutoff_time
                )
            )
        
        return query.all()
    
    def _get_candidate_annotations(
        self, 
        annotation: Annotation, 
        context_window: int,
        settings: ConflictSettings
    ) -> List[Annotation]:
        """Get annotations that could potentially conflict with the given annotation."""
        # Calculate search window
        search_start = max(0, annotation.start_char - context_window)
        search_end = annotation.end_char + context_window
        
        # Find overlapping annotations in the same text
        candidates = (
            self.db.query(Annotation)
            .filter(
                Annotation.text_id == annotation.text_id,
                Annotation.id != annotation.id,
                Annotation.start_char < search_end,
                Annotation.end_char > search_start
            )
            .all()
        )
        
        return candidates
    
    def _detect_conflicts_in_batch(
        self, 
        annotations: List[Annotation], 
        settings: ConflictSettings
    ) -> List[ConflictCandidate]:
        """Detect conflicts within a batch of annotations."""
        conflicts = []
        
        # Group annotations by text for efficient comparison
        text_groups = {}
        for annotation in annotations:
            if annotation.text_id not in text_groups:
                text_groups[annotation.text_id] = []
            text_groups[annotation.text_id].append(annotation)
        
        # Check each text group for conflicts
        for text_id, text_annotations in text_groups.items():
            text_conflicts = self._detect_conflicts_in_text(text_annotations, settings)
            conflicts.extend(text_conflicts)
        
        return conflicts
    
    def _detect_conflicts_in_text(
        self, 
        annotations: List[Annotation], 
        settings: ConflictSettings
    ) -> List[ConflictCandidate]:
        """Detect conflicts between annotations in the same text."""
        conflicts = []
        
        # Sort annotations by start position for efficient comparison
        sorted_annotations = sorted(annotations, key=lambda a: a.start_char)
        
        # Compare each pair of annotations
        for i, ann_a in enumerate(sorted_annotations):
            for ann_b in sorted_annotations[i + 1:]:
                # Skip if annotations are too far apart
                if ann_b.start_char > ann_a.end_char + 100:  # Reasonable gap threshold
                    break
                
                pair_conflicts = self._analyze_annotation_pair(ann_a, ann_b, settings)
                conflicts.extend(pair_conflicts)
        
        return conflicts
    
    def _analyze_annotation_pair(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        settings: ConflictSettings
    ) -> List[ConflictCandidate]:
        """Analyze a pair of annotations for conflicts."""
        conflicts = []
        
        # Check for span overlaps
        overlap_info = self._calculate_span_overlap(ann_a, ann_b)
        if overlap_info and overlap_info.percentage_a >= settings.span_overlap_threshold:
            span_conflict = self._create_span_overlap_conflict(
                ann_a, ann_b, overlap_info, settings
            )
            if span_conflict:
                conflicts.append(span_conflict)
        
        # Check for label conflicts on overlapping spans
        if overlap_info and ann_a.label_id != ann_b.label_id:
            label_conflict = self._create_label_conflict(
                ann_a, ann_b, overlap_info, settings
            )
            if label_conflict:
                conflicts.append(label_conflict)
        
        # Check for quality disputes
        quality_conflict = self._check_quality_disputes(ann_a, ann_b, settings)
        if quality_conflict:
            conflicts.append(quality_conflict)
        
        return conflicts
    
    def _calculate_span_overlap(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation
    ) -> Optional[OverlapInfo]:
        """Calculate overlap information between two annotation spans."""
        # No overlap if spans don't intersect
        if ann_a.end_char <= ann_b.start_char or ann_b.end_char <= ann_a.start_char:
            return None
        
        # Calculate overlap boundaries
        overlap_start = max(ann_a.start_char, ann_b.start_char)
        overlap_end = min(ann_a.end_char, ann_b.end_char)
        overlap_length = overlap_end - overlap_start
        
        # Calculate percentages
        len_a = ann_a.end_char - ann_a.start_char
        len_b = ann_b.end_char - ann_b.start_char
        percentage_a = overlap_length / len_a if len_a > 0 else 0
        percentage_b = overlap_length / len_b if len_b > 0 else 0
        
        # Determine overlap type
        overlap_type = self._classify_overlap_type(ann_a, ann_b, overlap_length, len_a, len_b)
        
        return OverlapInfo(
            start=overlap_start,
            end=overlap_end,
            length=overlap_length,
            percentage_a=percentage_a,
            percentage_b=percentage_b,
            overlap_type=overlap_type
        )
    
    def _classify_overlap_type(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        overlap_length: int,
        len_a: int, 
        len_b: int
    ) -> str:
        """Classify the type of overlap between two annotations."""
        if (ann_a.start_char == ann_b.start_char and ann_a.end_char == ann_b.end_char):
            return 'identical'
        elif overlap_length == len_a or overlap_length == len_b:
            return 'complete'
        elif (ann_a.start_char <= ann_b.start_char and ann_a.end_char >= ann_b.end_char) or \
             (ann_b.start_char <= ann_a.start_char and ann_b.end_char >= ann_a.end_char):
            return 'nested'
        else:
            return 'partial'
    
    def _create_span_overlap_conflict(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        overlap_info: OverlapInfo,
        settings: ConflictSettings
    ) -> Optional[ConflictCandidate]:
        """Create a span overlap conflict candidate."""
        # Calculate severity based on overlap percentage
        max_overlap = max(overlap_info.percentage_a, overlap_info.percentage_b)
        severity = self._calculate_overlap_severity(max_overlap)
        
        # Calculate confidence score
        confidence = min(1.0, max_overlap * 2)  # Higher overlap = higher confidence
        
        description = (
            f"Span overlap detected: {overlap_info.overlap_type} overlap "
            f"({overlap_info.percentage_a:.1%} of annotation A, "
            f"{overlap_info.percentage_b:.1%} of annotation B)"
        )
        
        metadata = {
            'overlap_type': overlap_info.overlap_type,
            'overlap_start': overlap_info.start,
            'overlap_end': overlap_info.end,
            'overlap_length': overlap_info.length,
            'percentage_a': overlap_info.percentage_a,
            'percentage_b': overlap_info.percentage_b,
            'detection_method': 'span_analysis'
        }
        
        return ConflictCandidate(
            annotation_a=ann_a,
            annotation_b=ann_b,
            conflict_type=ConflictType.SPAN_OVERLAP,
            severity_level=severity,
            confidence_score=confidence,
            overlap_info=overlap_info,
            description=description,
            metadata=metadata
        )
    
    def _create_label_conflict(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        overlap_info: OverlapInfo,
        settings: ConflictSettings
    ) -> Optional[ConflictCandidate]:
        """Create a label conflict candidate."""
        # Get label names for description
        label_a = ann_a.label.name if ann_a.label else f"Label {ann_a.label_id}"
        label_b = ann_b.label.name if ann_b.label else f"Label {ann_b.label_id}"
        
        # Calculate severity based on overlap and confidence scores
        overlap_factor = max(overlap_info.percentage_a, overlap_info.percentage_b)
        confidence_factor = abs(ann_a.confidence_score - ann_b.confidence_score)
        severity = self._calculate_label_conflict_severity(overlap_factor, confidence_factor)
        
        # Confidence in conflict detection
        confidence = min(1.0, overlap_factor * (1 + confidence_factor))
        
        description = (
            f"Label conflict on overlapping spans: '{label_a}' vs '{label_b}' "
            f"(overlap: {overlap_factor:.1%})"
        )
        
        metadata = {
            'label_a_id': ann_a.label_id,
            'label_b_id': ann_b.label_id,
            'label_a_name': label_a,
            'label_b_name': label_b,
            'confidence_a': ann_a.confidence_score,
            'confidence_b': ann_b.confidence_score,
            'overlap_percentage': overlap_factor,
            'detection_method': 'label_analysis'
        }
        
        return ConflictCandidate(
            annotation_a=ann_a,
            annotation_b=ann_b,
            conflict_type=ConflictType.LABEL_CONFLICT,
            severity_level=severity,
            confidence_score=confidence,
            overlap_info=overlap_info,
            description=description,
            metadata=metadata
        )
    
    def _check_quality_disputes(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation,
        settings: ConflictSettings
    ) -> Optional[ConflictCandidate]:
        """Check for quality-based disputes between annotations."""
        # Check for significant confidence score differences
        confidence_diff = abs(ann_a.confidence_score - ann_b.confidence_score)
        
        # Only flag as quality dispute if annotations are nearby and have very different confidence
        if confidence_diff >= 0.5:  # Significant confidence difference
            # Check if annotations are close enough to be compared
            distance = min(
                abs(ann_a.start_char - ann_b.start_char),
                abs(ann_a.end_char - ann_b.end_char)
            )
            
            if distance <= 50:  # Close proximity
                severity = "high" if confidence_diff >= 0.7 else "medium"
                
                description = (
                    f"Quality dispute detected: significant confidence difference "
                    f"({confidence_diff:.2f}) between nearby annotations"
                )
                
                metadata = {
                    'confidence_difference': confidence_diff,
                    'annotation_distance': distance,
                    'detection_method': 'quality_analysis'
                }
                
                return ConflictCandidate(
                    annotation_a=ann_a,
                    annotation_b=ann_b,
                    conflict_type=ConflictType.QUALITY_DISPUTE,
                    severity_level=severity,
                    confidence_score=confidence_diff,
                    overlap_info=None,
                    description=description,
                    metadata=metadata
                )
        
        return None
    
    def _calculate_overlap_severity(self, overlap_percentage: float) -> str:
        """Calculate severity level based on overlap percentage."""
        if overlap_percentage >= 0.8:
            return "critical"
        elif overlap_percentage >= 0.5:
            return "high"
        elif overlap_percentage >= 0.3:
            return "medium"
        else:
            return "low"
    
    def _calculate_label_conflict_severity(
        self, 
        overlap_factor: float, 
        confidence_factor: float
    ) -> str:
        """Calculate severity for label conflicts."""
        severity_score = overlap_factor + (confidence_factor * 0.3)
        
        if severity_score >= 0.8:
            return "critical"
        elif severity_score >= 0.6:
            return "high"
        elif severity_score >= 0.4:
            return "medium"
        else:
            return "low"
    
    def _get_project_settings(self, project_id: int) -> ConflictSettings:
        """Get conflict settings for a project, creating defaults if needed."""
        settings = (
            self.db.query(ConflictSettings)
            .filter_by(project_id=project_id)
            .first()
        )
        
        if not settings:
            # Create default settings
            settings = ConflictSettings(project_id=project_id)
            self.db.add(settings)
            self.db.commit()
        
        return settings
    
    def create_conflict_records(
        self, 
        conflict_candidates: List[ConflictCandidate]
    ) -> List[AnnotationConflict]:
        """Create database records for detected conflicts."""
        created_conflicts = []
        
        for candidate in conflict_candidates:
            # Check if conflict already exists
            existing_conflict = self._find_existing_conflict(candidate)
            if existing_conflict:
                continue
            
            # Create new conflict record
            conflict = AnnotationConflict(
                conflict_type=candidate.conflict_type,
                conflict_description=candidate.description,
                severity_level=candidate.severity_level,
                annotation_a_id=candidate.annotation_a.id,
                annotation_b_id=candidate.annotation_b.id,
                project_id=candidate.annotation_a.text.project_id,
                text_id=candidate.annotation_a.text_id,
                conflict_score=candidate.confidence_score,
                detection_metadata=candidate.metadata
            )
            
            # Add overlap information if available
            if candidate.overlap_info:
                conflict.overlap_start = candidate.overlap_info.start
                conflict.overlap_end = candidate.overlap_info.end
                conflict.overlap_percentage = max(
                    candidate.overlap_info.percentage_a,
                    candidate.overlap_info.percentage_b
                )
            
            self.db.add(conflict)
            created_conflicts.append(conflict)
        
        if created_conflicts:
            self.db.commit()
            self.logger.info(f"Created {len(created_conflicts)} new conflict records")
        
        return created_conflicts
    
    def _find_existing_conflict(self, candidate: ConflictCandidate) -> Optional[AnnotationConflict]:
        """Check if a conflict already exists for the given candidate."""
        return (
            self.db.query(AnnotationConflict)
            .filter(
                or_(
                    and_(
                        AnnotationConflict.annotation_a_id == candidate.annotation_a.id,
                        AnnotationConflict.annotation_b_id == candidate.annotation_b.id
                    ),
                    and_(
                        AnnotationConflict.annotation_a_id == candidate.annotation_b.id,
                        AnnotationConflict.annotation_b_id == candidate.annotation_a.id
                    )
                ),
                AnnotationConflict.conflict_type == candidate.conflict_type,
                AnnotationConflict.status.in_([
                    ConflictStatus.DETECTED,
                    ConflictStatus.ASSIGNED,
                    ConflictStatus.IN_REVIEW,
                    ConflictStatus.VOTING,
                    ConflictStatus.EXPERT_REVIEW
                ])
            )
            .first()
        )


class ConflictMonitor:
    """Real-time monitoring of annotation conflicts."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.detection_engine = ConflictDetectionEngine(db_session)
        self.logger = logging.getLogger(__name__)
    
    def monitor_annotation_changes(self, annotation_id: int) -> List[AnnotationConflict]:
        """Monitor for new conflicts when an annotation is created or updated."""
        try:
            # Detect conflicts for the specific annotation
            candidates = self.detection_engine.detect_conflicts_for_annotation(annotation_id)
            
            # Create conflict records
            conflicts = self.detection_engine.create_conflict_records(candidates)
            
            # Trigger notifications if needed
            if conflicts:
                self._trigger_conflict_notifications(conflicts)
            
            return conflicts
        
        except Exception as e:
            self.logger.error(f"Error monitoring annotation {annotation_id}: {e}")
            return []
    
    def _trigger_conflict_notifications(self, conflicts: List[AnnotationConflict]):
        """Trigger notifications for newly detected conflicts."""
        # This would integrate with the notification system
        # Implementation depends on your notification infrastructure
        for conflict in conflicts:
            self.logger.info(
                f"New conflict detected: {conflict.conflict_type.value} "
                f"(ID: {conflict.id}, Severity: {conflict.severity_level})"
            )


def detect_project_conflicts(
    db_session: Session, 
    project_id: int, 
    check_new_only: bool = True
) -> List[AnnotationConflict]:
    """Convenience function to detect and create conflicts for a project."""
    engine = ConflictDetectionEngine(db_session)
    candidates = engine.detect_conflicts_for_project(project_id, check_new_only)
    conflicts = engine.create_conflict_records(candidates)
    return conflicts


def setup_conflict_monitoring(db_session: Session) -> ConflictMonitor:
    """Set up conflict monitoring for real-time detection."""
    return ConflictMonitor(db_session)