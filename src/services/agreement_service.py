"""
Agreement Service

Service layer for handling inter-annotator agreement calculations and tracking.
This module provides functionality to automatically calculate agreement when
annotations are created or updated.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from collections import defaultdict

from ..models.annotation import Annotation
from ..models.text import Text
from ..models.project import Project
from ..models.user import User
from ..models.agreement import (
    AgreementStudy, CohenKappaResult, FleissKappaResult,
    store_agreement_analysis, AnnotatorPerformance
)
from ..utils.agreement_metrics import AgreementAnalysis, AgreementMetrics

logger = logging.getLogger(__name__)


class AgreementService:
    """
    Service for managing inter-annotator agreement calculations and tracking.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.agreement_analysis = AgreementAnalysis()
        self.agreement_metrics = AgreementMetrics()
    
    def trigger_agreement_calculation(self, annotation_id: int, 
                                    auto_calculate: bool = True,
                                    agreement_method: str = 'span_overlap') -> Optional[Dict[str, Any]]:
        """
        Trigger agreement calculation when an annotation is created or updated.
        
        Args:
            annotation_id: ID of the annotation that was created/updated
            auto_calculate: Whether to automatically calculate agreement
            agreement_method: Method for agreement calculation
            
        Returns:
            Agreement calculation results if performed, None otherwise
        """
        try:
            if not auto_calculate:
                return None
            
            annotation = self.db.query(Annotation).filter_by(id=annotation_id).first()
            if not annotation:
                logger.warning(f"Annotation {annotation_id} not found for agreement calculation")
                return None
            
            # Check if project has inter-annotator agreement enabled
            project = annotation.text.project
            if not project.inter_annotator_agreement:
                logger.debug(f"Project {project.id} does not have agreement tracking enabled")
                return None
            
            # Check if we have multiple annotators for this text
            annotator_count = self.db.query(Annotation.annotator_id).filter(
                Annotation.text_id == annotation.text_id
            ).distinct().count()
            
            if annotator_count < 2:
                logger.debug(f"Text {annotation.text_id} has only {annotator_count} annotator(s), skipping agreement calculation")
                return None
            
            # Calculate agreement for this text
            results = self.calculate_text_agreement(
                annotation.text_id,
                agreement_method=agreement_method,
                save_to_database=True
            )
            
            # Update annotator performance tracking
            self.update_annotator_performance(annotation.text.project_id)
            
            logger.info(f"Agreement calculation triggered for annotation {annotation_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error triggering agreement calculation: {str(e)}")
            return None
    
    def calculate_text_agreement(self, text_id: int,
                               annotator_ids: Optional[List[int]] = None,
                               label_ids: Optional[List[int]] = None,
                               agreement_method: str = 'span_overlap',
                               overlap_threshold: float = 0.5,
                               save_to_database: bool = True) -> Dict[str, Any]:
        """
        Calculate agreement for annotations on a specific text.
        """
        try:
            text = self.db.query(Text).filter_by(id=text_id).first()
            if not text:
                raise ValueError(f"Text {text_id} not found")
            
            # Extract annotations for this text
            annotations_data = self.extract_text_annotations(
                text_id,
                annotator_ids=annotator_ids,
                label_ids=label_ids,
                agreement_method=agreement_method,
                overlap_threshold=overlap_threshold
            )
            
            if not annotations_data or len(annotations_data) < 2:
                raise ValueError("Need at least 2 annotators with annotations for agreement calculation")
            
            # Perform agreement analysis
            results = self.agreement_analysis.analyze_dataset(annotations_data, True)
            
            # Add metadata
            results['text_info'] = {
                'text_id': text_id,
                'text_title': text.title,
                'project_id': text.project_id,
                'project_name': text.project.name,
                'calculation_timestamp': datetime.now().isoformat(),
                'agreement_method': agreement_method,
                'overlap_threshold': overlap_threshold if agreement_method == 'span_overlap' else None
            }
            
            # Save to database if requested
            if save_to_database:
                study_name = f"Text Agreement: {text.title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                study_description = f"Automated agreement analysis for text '{text.title}' in project {text.project.name}"
                
                study_id = store_agreement_analysis(self.db, results, study_name, study_description)
                results['database_info'] = {'saved': True, 'study_id': study_id}
            
            return results
            
        except Exception as e:
            logger.error(f"Error calculating text agreement: {str(e)}")
            raise
    
    def calculate_project_agreement(self, project_id: int,
                                  text_ids: Optional[List[int]] = None,
                                  annotator_ids: Optional[List[int]] = None,
                                  label_ids: Optional[List[int]] = None,
                                  agreement_method: str = 'span_overlap',
                                  overlap_threshold: float = 0.5,
                                  save_to_database: bool = True) -> Dict[str, Any]:
        """
        Calculate agreement for all annotations in a project.
        """
        try:
            project = self.db.query(Project).filter_by(id=project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Extract all project annotations
            annotations_data = self.extract_project_annotations(
                project_id,
                text_ids=text_ids,
                annotator_ids=annotator_ids,
                label_ids=label_ids,
                agreement_method=agreement_method,
                overlap_threshold=overlap_threshold
            )
            
            if not annotations_data or len(annotations_data) < 2:
                raise ValueError("Need at least 2 annotators with annotations for agreement calculation")
            
            # Perform comprehensive analysis
            results = self.agreement_analysis.analyze_dataset(annotations_data, True)
            
            # Add project metadata
            results['project_info'] = {
                'project_id': project_id,
                'project_name': project.name,
                'calculation_timestamp': datetime.now().isoformat(),
                'agreement_method': agreement_method,
                'overlap_threshold': overlap_threshold if agreement_method == 'span_overlap' else None
            }
            
            # Save to database if requested
            if save_to_database:
                study_name = f"Project Agreement: {project.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                study_description = f"Automated agreement analysis for project {project.name}"
                
                study_id = store_agreement_analysis(self.db, results, study_name, study_description)
                results['database_info'] = {'saved': True, 'study_id': study_id}
            
            return results
            
        except Exception as e:
            logger.error(f"Error calculating project agreement: {str(e)}")
            raise
    
    def extract_text_annotations(self, text_id: int,
                               annotator_ids: Optional[List[int]] = None,
                               label_ids: Optional[List[int]] = None,
                               agreement_method: str = 'span_overlap',
                               overlap_threshold: float = 0.5) -> Dict[str, List[str]]:
        """
        Extract annotations for a specific text and convert to agreement analysis format.
        """
        try:
            # Build query for annotations on this text
            query = self.db.query(Annotation).filter(Annotation.text_id == text_id)
            
            # Apply filters
            if annotator_ids:
                query = query.filter(Annotation.annotator_id.in_(annotator_ids))
            
            if label_ids:
                query = query.filter(Annotation.label_id.in_(label_ids))
            
            # Get annotations
            annotations = query.all()
            
            if not annotations:
                return {}
            
            # Group by annotator
            annotator_annotations = defaultdict(list)
            
            for ann in annotations:
                annotator_name = ann.annotator.username
                
                # Create annotation representation based on method
                if agreement_method == 'label_only':
                    annotation_value = ann.label.name
                elif agreement_method == 'exact_match':
                    annotation_value = f"{ann.label.name}:{ann.start_char}-{ann.end_char}"
                else:  # span_overlap
                    annotation_value = {
                        'label': ann.label.name,
                        'start': ann.start_char,
                        'end': ann.end_char,
                        'text': ann.selected_text
                    }
                
                annotator_annotations[annotator_name].append(annotation_value)
            
            # Convert to agreement analysis format
            if agreement_method == 'span_overlap':
                return self.convert_span_annotations_to_sequences(
                    {name: {text_id: anns} for name, anns in annotator_annotations.items()},
                    overlap_threshold
                )
            else:
                # For exact match and label only, return as is
                return dict(annotator_annotations)
                
        except Exception as e:
            logger.error(f"Error extracting text annotations: {str(e)}")
            raise
    
    def extract_project_annotations(self, project_id: int,
                                  text_ids: Optional[List[int]] = None,
                                  annotator_ids: Optional[List[int]] = None,
                                  label_ids: Optional[List[int]] = None,
                                  agreement_method: str = 'span_overlap',
                                  overlap_threshold: float = 0.5) -> Dict[str, List[str]]:
        """
        Extract annotations from a project and convert to agreement analysis format.
        """
        try:
            # Build query for annotations in this project
            query = self.db.query(Annotation).join(Text).filter(Text.project_id == project_id)
            
            # Apply filters
            if text_ids:
                query = query.filter(Text.id.in_(text_ids))
            
            if annotator_ids:
                query = query.filter(Annotation.annotator_id.in_(annotator_ids))
            
            if label_ids:
                query = query.filter(Annotation.label_id.in_(label_ids))
            
            # Get all annotations
            annotations = query.all()
            
            if not annotations:
                return {}
            
            # Group annotations by annotator and text
            annotator_annotations = defaultdict(lambda: defaultdict(list))
            
            for ann in annotations:
                annotator_name = ann.annotator.username
                text_id = ann.text_id
                
                # Create annotation representation based on method
                if agreement_method == 'label_only':
                    annotation_value = ann.label.name
                elif agreement_method == 'exact_match':
                    annotation_value = f"{ann.label.name}:{ann.start_char}-{ann.end_char}"
                else:  # span_overlap
                    annotation_value = {
                        'label': ann.label.name,
                        'start': ann.start_char,
                        'end': ann.end_char,
                        'text': ann.selected_text
                    }
                
                annotator_annotations[annotator_name][text_id].append(annotation_value)
            
            # Convert to format expected by agreement metrics
            if agreement_method == 'span_overlap':
                return self.convert_span_annotations_to_sequences(
                    annotator_annotations, overlap_threshold
                )
            else:
                # For exact match and label only, create flat sequences
                result = {}
                
                # Get all texts that have annotations
                all_texts = set()
                for annotator_data in annotator_annotations.values():
                    all_texts.update(annotator_data.keys())
                
                # Create sequences for each annotator across all texts
                for annotator_name, text_annotations in annotator_annotations.items():
                    sequence = []
                    for text_id in sorted(all_texts):
                        if text_id in text_annotations:
                            sequence.extend(text_annotations[text_id])
                        else:
                            # Add placeholder for texts this annotator didn't annotate
                            sequence.append(None)
                    
                    result[annotator_name] = sequence
                
                return result
                
        except Exception as e:
            logger.error(f"Error extracting project annotations: {str(e)}")
            raise
    
    def convert_span_annotations_to_sequences(self, annotator_annotations: Dict[str, Dict[int, List[Dict]]],
                                           overlap_threshold: float = 0.5) -> Dict[str, List[str]]:
        """
        Convert span-based annotations to agreement analysis sequences.
        """
        try:
            # Collect all unique annotation spans across all annotators
            all_spans = []
            
            for annotator_name, text_annotations in annotator_annotations.items():
                for text_id, annotations in text_annotations.items():
                    for ann in annotations:
                        all_spans.append({
                            'text_id': text_id,
                            'start': ann['start'],
                            'end': ann['end'],
                            'label': ann['label'],
                            'annotator': annotator_name
                        })
            
            # Sort spans by text_id and start position
            all_spans.sort(key=lambda x: (x['text_id'], x['start']))
            
            # Create unified annotation items by merging overlapping spans
            unified_items = []
            processed_spans = set()
            
            for i, span1 in enumerate(all_spans):
                if i in processed_spans:
                    continue
                
                # Find all spans that overlap with this one
                overlapping_spans = [span1]
                processed_spans.add(i)
                
                for j, span2 in enumerate(all_spans[i+1:], i+1):
                    if j in processed_spans:
                        continue
                    
                    if (span1['text_id'] == span2['text_id'] and
                        self.calculate_overlap_ratio(span1, span2) >= overlap_threshold):
                        overlapping_spans.append(span2)
                        processed_spans.add(j)
                
                # Create unified item from overlapping spans
                item_annotations = {}
                for span in overlapping_spans:
                    item_annotations[span['annotator']] = span['label']
                
                unified_items.append(item_annotations)
            
            # Convert to annotator sequences
            annotator_names = list(annotator_annotations.keys())
            result = {name: [] for name in annotator_names}
            
            for item in unified_items:
                for annotator_name in annotator_names:
                    # Use label if annotator annotated this item, otherwise None
                    result[annotator_name].append(item.get(annotator_name, None))
            
            return result
            
        except Exception as e:
            logger.error(f"Error converting span annotations: {str(e)}")
            raise
    
    def calculate_overlap_ratio(self, span1: Dict, span2: Dict) -> float:
        """
        Calculate overlap ratio between two spans.
        """
        if span1['text_id'] != span2['text_id']:
            return 0.0
        
        # Calculate intersection
        start = max(span1['start'], span2['start'])
        end = min(span1['end'], span2['end'])
        
        if start >= end:
            return 0.0
        
        intersection = end - start
        
        # Calculate union
        union = (span1['end'] - span1['start']) + (span2['end'] - span2['start']) - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def update_annotator_performance(self, project_id: int) -> None:
        """
        Update annotator performance statistics for a project.
        """
        try:
            # Get all agreement studies for this project
            studies = self.db.query(AgreementStudy).filter(
                AgreementStudy.description.contains(str(project_id))
            ).all()
            
            if not studies:
                return
            
            # Collect performance data by annotator
            annotator_performance = defaultdict(list)
            
            for study in studies:
                # Get Cohen's kappa results for pairwise comparisons
                for result in study.cohen_kappa_results:
                    annotator_performance[result.annotator1_name].append(result.kappa_value)
                    annotator_performance[result.annotator2_name].append(result.kappa_value)
            
            # Update or create performance records
            for annotator_name, kappa_scores in annotator_performance.items():
                if not kappa_scores:
                    continue
                
                avg_kappa = sum(kappa_scores) / len(kappa_scores)
                
                # Find or create performance record
                performance = self.db.query(AnnotatorPerformance).filter_by(
                    annotator_name=annotator_name
                ).first()
                
                if not performance:
                    performance = AnnotatorPerformance(
                        annotator_name=annotator_name,
                        studies_participated=1,
                        average_kappa_score=avg_kappa,
                        first_study_date=datetime.now(),
                        last_study_date=datetime.now()
                    )
                    self.db.add(performance)
                else:
                    # Update existing record
                    performance.studies_participated += 1
                    performance.average_kappa_score = avg_kappa
                    performance.last_study_date = datetime.now()
                
                # Update consistency rating
                if avg_kappa >= 0.8:
                    performance.consistency_rating = 'excellent'
                elif avg_kappa >= 0.6:
                    performance.consistency_rating = 'good'
                elif avg_kappa >= 0.4:
                    performance.consistency_rating = 'moderate'
                else:
                    performance.consistency_rating = 'poor'
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating annotator performance: {str(e)}")
            self.db.rollback()
    
    def get_project_agreement_summary(self, project_id: int) -> Dict[str, Any]:
        """
        Get a summary of agreement statistics for a project.
        """
        try:
            project = self.db.query(Project).filter_by(id=project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Get recent agreement studies for this project
            studies = self.db.query(AgreementStudy).filter(
                AgreementStudy.description.contains(str(project_id))
            ).order_by(AgreementStudy.created_at.desc()).limit(10).all()
            
            if not studies:
                return {
                    'project_id': project_id,
                    'project_name': project.name,
                    'has_agreement_data': False,
                    'message': 'No agreement calculations found for this project'
                }
            
            # Calculate overall statistics
            latest_study = studies[0]
            
            # Get average kappa scores
            avg_cohen_kappa = None
            avg_fleiss_kappa = None
            
            if latest_study.cohen_kappa_results:
                cohen_kappas = [r.kappa_value for r in latest_study.cohen_kappa_results]
                avg_cohen_kappa = sum(cohen_kappas) / len(cohen_kappas)
            
            if latest_study.fleiss_kappa_results:
                fleiss_kappas = [r.kappa_value for r in latest_study.fleiss_kappa_results]
                avg_fleiss_kappa = sum(fleiss_kappas) / len(fleiss_kappas)
            
            return {
                'project_id': project_id,
                'project_name': project.name,
                'has_agreement_data': True,
                'latest_calculation': latest_study.created_at.isoformat(),
                'total_studies': len(studies),
                'latest_study_id': latest_study.id,
                'average_cohen_kappa': round(avg_cohen_kappa, 4) if avg_cohen_kappa else None,
                'average_fleiss_kappa': round(avg_fleiss_kappa, 4) if avg_fleiss_kappa else None,
                'overall_quality_score': latest_study.overall_quality_score,
                'quality_interpretation': latest_study.quality_interpretation
            }
            
        except Exception as e:
            logger.error(f"Error getting project agreement summary: {str(e)}")
            raise