"""
Conflict Resolution Engine

Advanced system for resolving annotation conflicts through various strategies:
- Automatic merging based on rules
- Democratic voting by annotators
- Expert review and decision
- User consensus through discussion
- Weighted voting based on annotator experience
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from src.models.annotation import Annotation
from src.models.conflict import (
    AnnotationConflict, ConflictResolution, ConflictParticipant,
    ResolutionVote, ConflictNotification, ConflictSettings,
    ConflictStatus, ResolutionStrategy, ResolutionOutcome
)
from src.models.user import User
from src.models.agreement import AnnotatorPerformance

logger = logging.getLogger(__name__)


@dataclass
class ResolutionContext:
    """Context information for conflict resolution."""
    conflict: AnnotationConflict
    participants: List[ConflictParticipant]
    settings: ConflictSettings
    resolver: User
    metadata: Dict[str, Any]


@dataclass
class ResolutionResult:
    """Result of a conflict resolution attempt."""
    success: bool
    outcome: Optional[ResolutionOutcome]
    final_annotation: Optional[Annotation]
    confidence_score: float
    description: str
    metadata: Dict[str, Any]
    errors: List[str] = None


class ResolutionStrategy(ABC):
    """Abstract base class for conflict resolution strategies."""
    
    @abstractmethod
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if this strategy can resolve the given conflict."""
        pass
    
    @abstractmethod
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Attempt to resolve the conflict."""
        pass


class AutoMergeStrategy(ResolutionStrategy):
    """Automatic merging strategy for simple conflicts."""
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if auto-merge is possible."""
        conflict = context.conflict
        settings = context.settings
        
        # Only auto-merge if enabled in settings
        if not settings.auto_merge_enabled:
            return False
        
        # Check if conflict is simple enough for auto-merge
        if conflict.conflict_score > 0.5:  # High complexity conflicts need manual review
            return False
        
        # Check if annotations have similar confidence scores
        ann_a = conflict.annotation_a
        ann_b = conflict.annotation_b
        
        confidence_diff = abs(ann_a.confidence_score - ann_b.confidence_score)
        if confidence_diff > 0.3:  # Too different to auto-merge
            return False
        
        return True
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Attempt automatic resolution through merging."""
        conflict = context.conflict
        ann_a = conflict.annotation_a
        ann_b = conflict.annotation_b
        
        try:
            # Determine merge strategy based on conflict type
            if conflict.conflict_type.value == "span_overlap":
                merged_annotation = self._merge_overlapping_spans(ann_a, ann_b, conflict)
            elif conflict.conflict_type.value == "label_conflict":
                merged_annotation = self._resolve_label_conflict(ann_a, ann_b, conflict)
            else:
                return ResolutionResult(
                    success=False,
                    outcome=None,
                    final_annotation=None,
                    confidence_score=0.0,
                    description="Auto-merge not supported for this conflict type",
                    metadata={},
                    errors=["Unsupported conflict type for auto-merge"]
                )
            
            return ResolutionResult(
                success=True,
                outcome=ResolutionOutcome.MERGED,
                final_annotation=merged_annotation,
                confidence_score=0.8,
                description="Successfully auto-merged conflicting annotations",
                metadata={
                    "merge_method": "automatic",
                    "original_annotations": [ann_a.id, ann_b.id]
                }
            )
        
        except Exception as e:
            logger.error(f"Auto-merge failed for conflict {conflict.id}: {e}")
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description=f"Auto-merge failed: {str(e)}",
                metadata={},
                errors=[str(e)]
            )
    
    def _merge_overlapping_spans(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        conflict: AnnotationConflict
    ) -> Annotation:
        """Merge two overlapping span annotations."""
        # Use the annotation with higher confidence as base
        if ann_a.confidence_score >= ann_b.confidence_score:
            base_ann, other_ann = ann_a, ann_b
        else:
            base_ann, other_ann = ann_b, ann_a
        
        # Create merged annotation
        merged_start = min(ann_a.start_char, ann_b.start_char)
        merged_end = max(ann_a.end_char, ann_b.end_char)
        
        # Extract merged text (this would need access to the original text)
        # For now, we'll combine the selected texts
        merged_text = f"{ann_a.selected_text} | {ann_b.selected_text}"
        
        # Combine notes
        notes = []
        if base_ann.notes:
            notes.append(f"Original: {base_ann.notes}")
        if other_ann.notes:
            notes.append(f"Merged: {other_ann.notes}")
        
        merged_notes = " | ".join(notes) if notes else None
        
        # Create new annotation
        merged_annotation = Annotation(
            start_char=merged_start,
            end_char=merged_end,
            selected_text=merged_text,
            notes=merged_notes,
            confidence_score=(ann_a.confidence_score + ann_b.confidence_score) / 2,
            text_id=base_ann.text_id,
            annotator_id=base_ann.annotator_id,  # Keep original annotator
            label_id=base_ann.label_id,
            metadata={
                "merged_from": [ann_a.id, ann_b.id],
                "merge_method": "span_union",
                "merge_timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return merged_annotation
    
    def _resolve_label_conflict(
        self, 
        ann_a: Annotation, 
        ann_b: Annotation, 
        conflict: AnnotationConflict
    ) -> Annotation:
        """Resolve label conflict by choosing the higher-confidence annotation."""
        if ann_a.confidence_score >= ann_b.confidence_score:
            winner, loser = ann_a, ann_b
        else:
            winner, loser = ann_b, ann_a
        
        # Create resolved annotation based on winner
        resolved_annotation = Annotation(
            start_char=winner.start_char,
            end_char=winner.end_char,
            selected_text=winner.selected_text,
            notes=f"Auto-resolved label conflict. Original conflict with annotation {loser.id}",
            confidence_score=winner.confidence_score * 0.9,  # Slightly lower due to conflict
            text_id=winner.text_id,
            annotator_id=winner.annotator_id,
            label_id=winner.label_id,
            metadata={
                "resolved_from_conflict": conflict.id,
                "rejected_annotation": loser.id,
                "resolution_method": "confidence_based",
                "resolution_timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return resolved_annotation


class VotingStrategy(ResolutionStrategy):
    """Democratic voting strategy for conflict resolution."""
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if voting resolution is possible."""
        conflict = context.conflict
        
        # Need sufficient votes to resolve
        vote_count = len(conflict.votes)
        min_votes = context.settings.minimum_voter_count or 3
        
        return vote_count >= min_votes
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Resolve conflict through voting."""
        conflict = context.conflict
        votes = conflict.votes
        
        if not votes:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description="No votes available for resolution",
                metadata={},
                errors=["No votes found"]
            )
        
        # Count votes
        vote_counts = {}
        total_weight = 0.0
        
        for vote in votes:
            choice = vote.vote_choice
            weight = vote.vote_weight or 1.0
            
            if choice not in vote_counts:
                vote_counts[choice] = 0.0
            vote_counts[choice] += weight
            total_weight += weight
        
        # Find winning choice
        if not vote_counts:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description="No valid votes found",
                metadata={},
                errors=["No valid votes"]
            )
        
        winning_choice = max(vote_counts, key=vote_counts.get)
        winning_votes = vote_counts[winning_choice]
        confidence = winning_votes / total_weight if total_weight > 0 else 0.0
        
        # Check if we have sufficient consensus
        consensus_threshold = context.settings.voting_threshold or 0.6
        if confidence < consensus_threshold:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=confidence,
                description=f"Insufficient consensus ({confidence:.1%} < {consensus_threshold:.1%})",
                metadata={"vote_counts": vote_counts},
                errors=["Insufficient consensus"]
            )
        
        # Apply winning choice
        return self._apply_voting_result(conflict, winning_choice, confidence, vote_counts)
    
    def _apply_voting_result(
        self, 
        conflict: AnnotationConflict, 
        winning_choice: str, 
        confidence: float,
        vote_counts: Dict[str, float]
    ) -> ResolutionResult:
        """Apply the result of voting."""
        ann_a = conflict.annotation_a
        ann_b = conflict.annotation_b
        
        if winning_choice == "annotation_a":
            return ResolutionResult(
                success=True,
                outcome=ResolutionOutcome.ANNOTATION_A_SELECTED,
                final_annotation=ann_a,
                confidence_score=confidence,
                description=f"Annotation A selected by vote ({confidence:.1%} consensus)",
                metadata={"vote_counts": vote_counts, "winning_choice": winning_choice}
            )
        
        elif winning_choice == "annotation_b":
            return ResolutionResult(
                success=True,
                outcome=ResolutionOutcome.ANNOTATION_B_SELECTED,
                final_annotation=ann_b,
                confidence_score=confidence,
                description=f"Annotation B selected by vote ({confidence:.1%} consensus)",
                metadata={"vote_counts": vote_counts, "winning_choice": winning_choice}
            )
        
        elif winning_choice == "merge":
            # Use auto-merge strategy for the actual merging
            auto_merge = AutoMergeStrategy()
            context = ResolutionContext(
                conflict=conflict,
                participants=[],
                settings=ConflictSettings(),  # Default settings
                resolver=None,
                metadata={}
            )
            merge_result = auto_merge.resolve(context)
            
            if merge_result.success:
                merge_result.description = f"Merged by vote ({confidence:.1%} consensus)"
                merge_result.metadata.update({"vote_counts": vote_counts})
            
            return merge_result
        
        elif winning_choice == "reject_both":
            return ResolutionResult(
                success=True,
                outcome=ResolutionOutcome.BOTH_REJECTED,
                final_annotation=None,
                confidence_score=confidence,
                description=f"Both annotations rejected by vote ({confidence:.1%} consensus)",
                metadata={"vote_counts": vote_counts, "winning_choice": winning_choice}
            )
        
        else:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description=f"Unknown voting choice: {winning_choice}",
                metadata={"vote_counts": vote_counts},
                errors=[f"Unknown choice: {winning_choice}"]
            )


class ExpertReviewStrategy(ResolutionStrategy):
    """Expert review strategy for complex conflicts."""
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if expert review can resolve the conflict."""
        # Always can be used, but requires manual expert input
        return True
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Resolve through expert review (requires manual input)."""
        # This strategy would typically require human expert input
        # For now, we'll mark it as requiring manual resolution
        
        return ResolutionResult(
            success=False,
            outcome=None,
            final_annotation=None,
            confidence_score=0.0,
            description="Expert review required - manual resolution needed",
            metadata={"requires_manual_input": True},
            errors=["Manual expert input required"]
        )


class WeightedVotingStrategy(ResolutionStrategy):
    """Weighted voting based on annotator experience and performance."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def can_resolve(self, context: ResolutionContext) -> bool:
        """Check if weighted voting is possible."""
        return len(context.conflict.votes) >= (context.settings.minimum_voter_count or 3)
    
    def resolve(self, context: ResolutionContext) -> ResolutionResult:
        """Resolve using weighted voting based on annotator performance."""
        conflict = context.conflict
        votes = conflict.votes
        
        # Calculate weights based on annotator performance
        weighted_votes = self._calculate_weighted_votes(votes)
        
        # Use same logic as regular voting but with performance weights
        vote_counts = {}
        total_weight = 0.0
        
        for vote_choice, weight in weighted_votes:
            if vote_choice not in vote_counts:
                vote_counts[vote_choice] = 0.0
            vote_counts[vote_choice] += weight
            total_weight += weight
        
        if not vote_counts:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description="No weighted votes available",
                metadata={},
                errors=["No valid weighted votes"]
            )
        
        winning_choice = max(vote_counts, key=vote_counts.get)
        confidence = vote_counts[winning_choice] / total_weight if total_weight > 0 else 0.0
        
        # Apply result using regular voting logic
        voting_strategy = VotingStrategy()
        return voting_strategy._apply_voting_result(conflict, winning_choice, confidence, vote_counts)
    
    def _calculate_weighted_votes(self, votes: List[ResolutionVote]) -> List[Tuple[str, float]]:
        """Calculate vote weights based on annotator performance."""
        weighted_votes = []
        
        for vote in votes:
            # Get annotator performance
            performance = (
                self.db.query(AnnotatorPerformance)
                .filter_by(annotator_name=vote.voter.username)
                .first()
            )
            
            # Calculate weight based on performance
            base_weight = vote.vote_weight or 1.0
            
            if performance and performance.average_kappa_score:
                # Weight based on average kappa score
                performance_multiplier = max(0.1, performance.average_kappa_score)
                weight = base_weight * performance_multiplier
            else:
                # Default weight for new annotators
                weight = base_weight * 0.5
            
            # Consider voter confidence
            if vote.confidence:
                weight *= vote.confidence
            
            weighted_votes.append((vote.vote_choice, weight))
        
        return weighted_votes


class ConflictResolutionEngine:
    """Main engine for resolving annotation conflicts."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.logger = logging.getLogger(__name__)
        
        # Initialize resolution strategies
        self.strategies = {
            ResolutionStrategy.AUTO_MERGE: AutoMergeStrategy(),
            ResolutionStrategy.VOTING: VotingStrategy(),
            ResolutionStrategy.EXPERT_REVIEW: ExpertReviewStrategy(),
            ResolutionStrategy.WEIGHTED_VOTING: WeightedVotingStrategy(db_session)
        }
    
    def resolve_conflict(
        self, 
        conflict_id: int, 
        resolver_id: int,
        strategy: Optional[ResolutionStrategy] = None
    ) -> ResolutionResult:
        """
        Resolve a specific conflict.
        
        Args:
            conflict_id: ID of conflict to resolve
            resolver_id: ID of user attempting resolution
            strategy: Specific strategy to use (auto-select if None)
        
        Returns:
            Result of resolution attempt
        """
        # Get conflict and related data
        conflict = self.db.query(AnnotationConflict).filter_by(id=conflict_id).first()
        if not conflict:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description="Conflict not found",
                metadata={},
                errors=["Conflict not found"]
            )
        
        resolver = self.db.query(User).filter_by(id=resolver_id).first()
        if not resolver:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description="Resolver not found",
                metadata={},
                errors=["Resolver not found"]
            )
        
        # Get project settings
        settings = self._get_project_settings(conflict.project_id)
        
        # Get participants
        participants = conflict.participants
        
        # Create resolution context
        context = ResolutionContext(
            conflict=conflict,
            participants=participants,
            settings=settings,
            resolver=resolver,
            metadata={}
        )
        
        # Select resolution strategy
        if not strategy:
            strategy = self._select_resolution_strategy(context)
        
        # Attempt resolution
        resolution_result = self._attempt_resolution(context, strategy)
        
        # Record resolution attempt
        self._record_resolution_attempt(conflict, resolver, strategy, resolution_result)
        
        # Update conflict status
        if resolution_result.success:
            self._update_conflict_status(conflict, ConflictStatus.RESOLVED, resolution_result)
        else:
            # Check if we should escalate
            if self._should_escalate_conflict(conflict, settings):
                self._escalate_conflict(conflict, settings)
        
        return resolution_result
    
    def _select_resolution_strategy(self, context: ResolutionContext) -> ResolutionStrategy:
        """Select the most appropriate resolution strategy."""
        conflict = context.conflict
        settings = context.settings
        
        # Use project default if specified
        if settings.default_resolution_strategy:
            return settings.default_resolution_strategy
        
        # Auto-select based on conflict characteristics
        if conflict.conflict_score <= 0.3 and settings.auto_merge_enabled:
            return ResolutionStrategy.AUTO_MERGE
        
        elif len(conflict.votes) >= (settings.minimum_voter_count or 3):
            return ResolutionStrategy.WEIGHTED_VOTING
        
        elif conflict.severity_level in ["critical", "high"]:
            return ResolutionStrategy.EXPERT_REVIEW
        
        else:
            return ResolutionStrategy.VOTING
    
    def _attempt_resolution(
        self, 
        context: ResolutionContext, 
        strategy: ResolutionStrategy
    ) -> ResolutionResult:
        """Attempt to resolve conflict using specified strategy."""
        strategy_impl = self.strategies.get(strategy)
        if not strategy_impl:
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description=f"Unknown resolution strategy: {strategy}",
                metadata={},
                errors=[f"Unknown strategy: {strategy}"]
            )
        
        if not strategy_impl.can_resolve(context):
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description=f"Strategy {strategy} cannot resolve this conflict",
                metadata={},
                errors=[f"Strategy not applicable: {strategy}"]
            )
        
        try:
            return strategy_impl.resolve(context)
        except Exception as e:
            self.logger.error(f"Resolution strategy {strategy} failed: {e}")
            return ResolutionResult(
                success=False,
                outcome=None,
                final_annotation=None,
                confidence_score=0.0,
                description=f"Strategy execution failed: {str(e)}",
                metadata={},
                errors=[str(e)]
            )
    
    def _record_resolution_attempt(
        self, 
        conflict: AnnotationConflict,
        resolver: User, 
        strategy: ResolutionStrategy, 
        result: ResolutionResult
    ):
        """Record the resolution attempt in the database."""
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            resolution_strategy=strategy,
            outcome=result.outcome,
            resolution_description=result.description,
            final_annotation_id=result.final_annotation.id if result.final_annotation else None,
            resolver_id=resolver.id,
            confidence_score=result.confidence_score,
            resolution_data=result.metadata,
            completed_at=datetime.utcnow() if result.success else None
        )
        
        self.db.add(resolution)
        self.db.commit()
    
    def _update_conflict_status(
        self, 
        conflict: AnnotationConflict, 
        status: ConflictStatus, 
        result: ResolutionResult
    ):
        """Update conflict status after resolution attempt."""
        conflict.status = status
        if status == ConflictStatus.RESOLVED:
            conflict.resolved_at = datetime.utcnow()
        
        self.db.commit()
    
    def _should_escalate_conflict(
        self, 
        conflict: AnnotationConflict, 
        settings: ConflictSettings
    ) -> bool:
        """Check if conflict should be escalated."""
        if not settings.enable_automatic_escalation:
            return False
        
        # Count resolution attempts
        attempt_count = len(conflict.resolutions)
        max_attempts = settings.max_resolution_attempts or 3
        
        if attempt_count >= max_attempts:
            return True
        
        # Check timeout
        if settings.resolution_timeout_hours:
            timeout = timedelta(hours=settings.resolution_timeout_hours)
            if datetime.utcnow() - conflict.detected_at > timeout:
                return True
        
        return False
    
    def _escalate_conflict(self, conflict: AnnotationConflict, settings: ConflictSettings):
        """Escalate conflict to expert review."""
        conflict.status = ConflictStatus.EXPERT_REVIEW
        conflict.resolution_strategy = ResolutionStrategy.EXPERT_REVIEW
        
        # TODO: Implement expert assignment logic
        # This could involve finding available experts, checking their expertise, etc.
        
        self.db.commit()
        
        self.logger.info(f"Escalated conflict {conflict.id} to expert review")
    
    def _get_project_settings(self, project_id: int) -> ConflictSettings:
        """Get conflict settings for a project."""
        settings = (
            self.db.query(ConflictSettings)
            .filter_by(project_id=project_id)
            .first()
        )
        
        if not settings:
            settings = ConflictSettings(project_id=project_id)
            self.db.add(settings)
            self.db.commit()
        
        return settings
    
    def submit_vote(
        self, 
        conflict_id: int, 
        voter_id: int, 
        vote_choice: str,
        rationale: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> bool:
        """Submit a vote for conflict resolution."""
        try:
            # Check if user already voted
            existing_vote = (
                self.db.query(ResolutionVote)
                .filter_by(conflict_id=conflict_id, voter_id=voter_id)
                .first()
            )
            
            if existing_vote:
                # Update existing vote
                existing_vote.vote_choice = vote_choice
                existing_vote.rationale = rationale
                existing_vote.confidence = confidence
                existing_vote.updated_at = datetime.utcnow()
            else:
                # Create new vote
                vote = ResolutionVote(
                    conflict_id=conflict_id,
                    voter_id=voter_id,
                    vote_choice=vote_choice,
                    rationale=rationale,
                    confidence=confidence
                )
                self.db.add(vote)
            
            self.db.commit()
            
            # Check if we have enough votes to attempt resolution
            self._check_voting_completion(conflict_id)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error submitting vote: {e}")
            self.db.rollback()
            return False
    
    def _check_voting_completion(self, conflict_id: int):
        """Check if voting is complete and attempt resolution."""
        conflict = self.db.query(AnnotationConflict).filter_by(id=conflict_id).first()
        if not conflict or conflict.status != ConflictStatus.VOTING:
            return
        
        settings = self._get_project_settings(conflict.project_id)
        min_votes = settings.minimum_voter_count or 3
        
        if len(conflict.votes) >= min_votes:
            # Attempt resolution
            # This could be done asynchronously in a real system
            self.resolve_conflict(
                conflict_id, 
                conflict.assigned_resolver_id or 1,  # System resolver
                ResolutionStrategy.VOTING
            )


# Convenience functions

def resolve_conflict(
    db_session: Session, 
    conflict_id: int, 
    resolver_id: int,
    strategy: Optional[ResolutionStrategy] = None
) -> ResolutionResult:
    """Convenience function to resolve a conflict."""
    engine = ConflictResolutionEngine(db_session)
    return engine.resolve_conflict(conflict_id, resolver_id, strategy)


def submit_resolution_vote(
    db_session: Session,
    conflict_id: int,
    voter_id: int,
    vote_choice: str,
    rationale: Optional[str] = None,
    confidence: Optional[float] = None
) -> bool:
    """Convenience function to submit a resolution vote."""
    engine = ConflictResolutionEngine(db_session)
    return engine.submit_vote(conflict_id, voter_id, vote_choice, rationale, confidence)