"""
API endpoints for inter-annotator agreement analysis.

This module provides RESTful endpoints for calculating agreement metrics,
managing agreement studies, and generating analysis reports.
"""

from flask import Flask, request, jsonify, Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from typing import Dict, List, Any, Optional
import json
import traceback
from datetime import datetime
import logging
from collections import defaultdict

from ..utils.agreement_metrics import AgreementMetrics, AgreementAnalysis, calculate_agreement_metrics
from ..models.agreement import (
    AgreementStudy, CohenKappaResult, FleissKappaResult, 
    KrippendorffAlphaResult, StudyRecommendation, AnnotatorPerformance,
    store_agreement_analysis, get_study_summary, create_tables
)
from ..models.annotation import Annotation
from ..models.text import Text
from ..models.user import User
from ..models.project import Project

# Create blueprint
agreement_bp = Blueprint('agreement', __name__, url_prefix='/api/agreement')

# Global variables (should be configured in main app)
db_session = None
agreement_metrics = AgreementMetrics()
agreement_analysis = AgreementAnalysis()

logger = logging.getLogger(__name__)


@agreement_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'agreement-analysis',
        'timestamp': datetime.now().isoformat()
    }), 200


@agreement_bp.route('/calculate/cohen-kappa', methods=['POST'])
def calculate_cohen_kappa():
    """
    Calculate Cohen's Kappa for two annotators.
    
    Expected JSON payload:
    {
        "annotator1": [list of annotations],
        "annotator2": [list of annotations],
        "weights": "linear|quadratic|null" (optional),
        "annotator1_name": "string" (optional),
        "annotator2_name": "string" (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON payload provided'}), 400
        
        # Validate required fields
        if 'annotator1' not in data or 'annotator2' not in data:
            return jsonify({'error': 'Both annotator1 and annotator2 are required'}), 400
        
        annotator1 = data['annotator1']
        annotator2 = data['annotator2']
        weights = data.get('weights')
        
        # Validate input
        if not isinstance(annotator1, list) or not isinstance(annotator2, list):
            return jsonify({'error': 'Annotator data must be lists'}), 400
        
        if len(annotator1) != len(annotator2):
            return jsonify({'error': 'Annotator arrays must have same length'}), 400
        
        if len(annotator1) == 0:
            return jsonify({'error': 'Annotator arrays cannot be empty'}), 400
        
        # Calculate Cohen's Kappa
        result = agreement_metrics.cohen_kappa(annotator1, annotator2, weights)
        
        # Add metadata
        result['metadata'] = {
            'annotator1_name': data.get('annotator1_name', 'annotator1'),
            'annotator2_name': data.get('annotator2_name', 'annotator2'),
            'calculation_timestamp': datetime.now().isoformat(),
            'weights_used': weights is not None,
            'weight_type': weights
        }
        
        return jsonify({
            'success': True,
            'metric_type': 'cohen_kappa',
            'result': result
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error calculating Cohen's Kappa: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error during calculation'}), 500


@agreement_bp.route('/calculate/fleiss-kappa', methods=['POST'])
def calculate_fleiss_kappa():
    """
    Calculate Fleiss' Kappa for multiple annotators.
    
    Expected JSON payload:
    {
        "annotations": [
            [list of annotations from annotator 1],
            [list of annotations from annotator 2],
            ...
        ],
        "annotator_names": ["name1", "name2", ...] (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON payload provided'}), 400
        
        # Validate required fields
        if 'annotations' not in data:
            return jsonify({'error': 'annotations field is required'}), 400
        
        annotations = data['annotations']
        
        # Validate input
        if not isinstance(annotations, list):
            return jsonify({'error': 'annotations must be a list of lists'}), 400
        
        if len(annotations) < 2:
            return jsonify({'error': 'Need at least 2 annotators'}), 400
        
        # Check all annotation lists are valid
        first_length = len(annotations[0]) if annotations else 0
        for i, ann in enumerate(annotations):
            if not isinstance(ann, list):
                return jsonify({'error': f'Annotator {i} data must be a list'}), 400
            if len(ann) != first_length:
                return jsonify({'error': 'All annotators must annotate same number of items'}), 400
        
        if first_length == 0:
            return jsonify({'error': 'Annotation lists cannot be empty'}), 400
        
        # Calculate Fleiss' Kappa
        result = agreement_metrics.fleiss_kappa(annotations)
        
        # Add metadata
        annotator_names = data.get('annotator_names', 
                                 [f'annotator_{i}' for i in range(len(annotations))])
        
        result['metadata'] = {
            'annotator_names': annotator_names,
            'calculation_timestamp': datetime.now().isoformat(),
            'n_annotators': len(annotations),
            'n_items': len(annotations[0])
        }
        
        return jsonify({
            'success': True,
            'metric_type': 'fleiss_kappa',
            'result': result
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error calculating Fleiss' Kappa: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error during calculation'}), 500


@agreement_bp.route('/calculate/krippendorff-alpha', methods=['POST'])
def calculate_krippendorff_alpha():
    """
    Calculate Krippendorff's Alpha for any number of annotators.
    
    Expected JSON payload:
    {
        "annotations": [
            [list of annotations from annotator 1],
            [list of annotations from annotator 2],
            ...
        ],
        "metric": "nominal|ordinal|interval|ratio" (optional, default: "nominal"),
        "missing_value": null|"value" (optional),
        "annotator_names": ["name1", "name2", ...] (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON payload provided'}), 400
        
        # Validate required fields
        if 'annotations' not in data:
            return jsonify({'error': 'annotations field is required'}), 400
        
        annotations = data['annotations']
        metric = data.get('metric', 'nominal')
        missing_value = data.get('missing_value', None)
        
        # Validate input
        if not isinstance(annotations, list):
            return jsonify({'error': 'annotations must be a list of lists'}), 400
        
        if len(annotations) < 2:
            return jsonify({'error': 'Need at least 2 annotators'}), 400
        
        if metric not in ['nominal', 'ordinal', 'interval', 'ratio']:
            return jsonify({'error': 'Invalid metric type'}), 400
        
        # Check all annotation lists are valid
        first_length = len(annotations[0]) if annotations else 0
        for i, ann in enumerate(annotations):
            if not isinstance(ann, list):
                return jsonify({'error': f'Annotator {i} data must be a list'}), 400
            if len(ann) != first_length:
                return jsonify({'error': 'All annotators must annotate same number of items'}), 400
        
        if first_length == 0:
            return jsonify({'error': 'Annotation lists cannot be empty'}), 400
        
        # Calculate Krippendorff's Alpha
        result = agreement_metrics.krippendorff_alpha(annotations, metric, missing_value)
        
        # Add metadata
        annotator_names = data.get('annotator_names', 
                                 [f'annotator_{i}' for i in range(len(annotations))])
        
        result['metadata'] = {
            'annotator_names': annotator_names,
            'calculation_timestamp': datetime.now().isoformat(),
            'distance_metric': metric,
            'missing_value': missing_value,
            'n_annotators': len(annotations),
            'n_items': len(annotations[0])
        }
        
        return jsonify({
            'success': True,
            'metric_type': 'krippendorff_alpha',
            'result': result
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error calculating Krippendorff's Alpha: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error during calculation'}), 500


@agreement_bp.route('/analyze/comprehensive', methods=['POST'])
def comprehensive_analysis():
    """
    Perform comprehensive agreement analysis with all metrics.
    
    Expected JSON payload:
    {
        "annotations": {
            "annotator1_name": [list of annotations],
            "annotator2_name": [list of annotations],
            ...
        },
        "dataset_name": "string" (optional),
        "include_all_metrics": true|false (optional, default: true),
        "save_to_database": true|false (optional, default: false),
        "study_name": "string" (optional, required if save_to_database=true),
        "study_description": "string" (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON payload provided'}), 400
        
        # Validate required fields
        if 'annotations' not in data:
            return jsonify({'error': 'annotations field is required'}), 400
        
        annotations = data['annotations']
        
        if not isinstance(annotations, dict):
            return jsonify({'error': 'annotations must be a dictionary mapping annotator names to annotation lists'}), 400
        
        if len(annotations) < 2:
            return jsonify({'error': 'Need at least 2 annotators'}), 400
        
        # Validate annotation lists
        first_length = None
        for annotator_name, ann_list in annotations.items():
            if not isinstance(ann_list, list):
                return jsonify({'error': f'Annotations for {annotator_name} must be a list'}), 400
            if first_length is None:
                first_length = len(ann_list)
            elif len(ann_list) != first_length:
                return jsonify({'error': 'All annotators must annotate same number of items'}), 400
        
        if first_length == 0:
            return jsonify({'error': 'Annotation lists cannot be empty'}), 400
        
        # Perform comprehensive analysis
        include_all = data.get('include_all_metrics', True)
        results = agreement_analysis.analyze_dataset(annotations, include_all)
        
        # Add metadata
        results['analysis_metadata'] = {
            'dataset_name': data.get('dataset_name'),
            'analysis_timestamp': datetime.now().isoformat(),
            'include_all_metrics': include_all,
            'api_version': '1.0'
        }
        
        # Save to database if requested
        if data.get('save_to_database', False):
            if not db_session:
                return jsonify({'error': 'Database not configured'}), 500
            
            study_name = data.get('study_name')
            if not study_name:
                return jsonify({'error': 'study_name required when save_to_database=true'}), 400
            
            try:
                study_id = store_agreement_analysis(
                    db_session, 
                    results, 
                    study_name, 
                    data.get('study_description')
                )
                results['database_info'] = {
                    'saved': True,
                    'study_id': study_id,
                    'study_name': study_name
                }
            except Exception as e:
                logger.error(f"Error saving to database: {str(e)}")
                results['database_info'] = {
                    'saved': False,
                    'error': str(e)
                }
        else:
            results['database_info'] = {'saved': False}
        
        return jsonify({
            'success': True,
            'analysis_type': 'comprehensive',
            'results': results
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error during analysis'}), 500


@agreement_bp.route('/studies', methods=['GET'])
def list_studies():
    """List all agreement studies with optional filtering."""
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Parse query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        status_filter = request.args.get('status')
        annotator_filter = request.args.get('annotator')
        
        # Build query
        query = db_session.query(AgreementStudy)
        
        if status_filter:
            query = query.filter(AgreementStudy.study_status == status_filter)
        
        if annotator_filter:
            # Filter studies that include this annotator
            query = query.filter(AgreementStudy.annotator_names.contains([annotator_filter]))
        
        # Order by creation date (newest first)
        query = query.order_by(AgreementStudy.created_at.desc())
        
        # Paginate
        total = query.count()
        studies = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return jsonify({
            'success': True,
            'studies': [study.to_dict() for study in studies],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing studies: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@agreement_bp.route('/studies/<int:study_id>', methods=['GET'])
def get_study(study_id: int):
    """Get detailed information about a specific study."""
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        study_data = get_study_summary(db_session, study_id)
        
        if not study_data:
            return jsonify({'error': 'Study not found'}), 404
        
        return jsonify({
            'success': True,
            'study': study_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving study {study_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@agreement_bp.route('/studies/<int:study_id>', methods=['DELETE'])
def delete_study(study_id: int):
    """Delete a study and all its associated data."""
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        study = db_session.query(AgreementStudy).filter_by(id=study_id).first()
        
        if not study:
            return jsonify({'error': 'Study not found'}), 404
        
        # Delete associated records (CASCADE should handle this, but being explicit)
        db_session.query(CohenKappaResult).filter_by(study_id=study_id).delete()
        db_session.query(FleissKappaResult).filter_by(study_id=study_id).delete()
        db_session.query(KrippendorffAlphaResult).filter_by(study_id=study_id).delete()
        db_session.query(StudyRecommendation).filter_by(study_id=study_id).delete()
        
        # Delete the study itself
        db_session.delete(study)
        db_session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Study {study_id} deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting study {study_id}: {str(e)}")
        db_session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@agreement_bp.route('/annotators/performance', methods=['GET'])
def get_annotator_performance():
    """Get performance statistics for all annotators."""
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        performances = db_session.query(AnnotatorPerformance).all()
        
        return jsonify({
            'success': True,
            'annotator_performances': [perf.to_dict() for perf in performances]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving annotator performance: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@agreement_bp.route('/projects/<int:project_id>/summary', methods=['GET'])
def get_project_agreement_summary(project_id: int):\n    \"\"\"\n    Get a summary of agreement statistics for a project.\n    \"\"\"\n    try:\n        if not db_session:\n            return jsonify({'error': 'Database not configured'}), 500\n        \n        from ..services.agreement_service import AgreementService\n        agreement_service = AgreementService(db_session)\n        \n        summary = agreement_service.get_project_agreement_summary(project_id)\n        \n        return jsonify({\n            'success': True,\n            'project_summary': summary\n        }), 200\n        \n    except ValueError as e:\n        return jsonify({'error': str(e)}), 404\n    except Exception as e:\n        logger.error(f\"Error retrieving project agreement summary: {str(e)}\")\n        return jsonify({'error': 'Internal server error'}), 500\n\n\n@agreement_bp.route('/projects/<int:project_id>/enable', methods=['POST'])\ndef enable_project_agreement_tracking(project_id: int):\n    \"\"\"\n    Enable inter-annotator agreement tracking for a project.\n    \"\"\"\n    try:\n        if not db_session:\n            return jsonify({'error': 'Database not configured'}), 500\n        \n        project = db_session.query(Project).filter_by(id=project_id).first()\n        if not project:\n            return jsonify({'error': 'Project not found'}), 404\n        \n        project.inter_annotator_agreement = True\n        db_session.commit()\n        \n        return jsonify({\n            'success': True,\n            'message': f'Agreement tracking enabled for project {project.name}',\n            'project_id': project_id\n        }), 200\n        \n    except Exception as e:\n        logger.error(f\"Error enabling project agreement tracking: {str(e)}\")\n        db_session.rollback()\n        return jsonify({'error': 'Internal server error'}), 500\n\n\n@agreement_bp.route('/projects/<int:project_id>/disable', methods=['POST'])\ndef disable_project_agreement_tracking(project_id: int):\n    \"\"\"\n    Disable inter-annotator agreement tracking for a project.\n    \"\"\"\n    try:\n        if not db_session:\n            return jsonify({'error': 'Database not configured'}), 500\n        \n        project = db_session.query(Project).filter_by(id=project_id).first()\n        if not project:\n            return jsonify({'error': 'Project not found'}), 404\n        \n        project.inter_annotator_agreement = False\n        db_session.commit()\n        \n        return jsonify({\n            'success': True,\n            'message': f'Agreement tracking disabled for project {project.name}',\n            'project_id': project_id\n        }), 200\n        \n    except Exception as e:\n        logger.error(f\"Error disabling project agreement tracking: {str(e)}\")\n        db_session.rollback()\n        return jsonify({'error': 'Internal server error'}), 500\n\n\n@agreement_bp.route('/annotators/<annotator_name>/performance', methods=['GET'])\ndef get_annotator_individual_performance(annotator_name: str):\n    \"\"\"\n    Get performance statistics for a specific annotator.\n    \"\"\"\n    try:\n        if not db_session:\n            return jsonify({'error': 'Database not configured'}), 500\n        \n        performance = db_session.query(AnnotatorPerformance).filter_by(\n            annotator_name=annotator_name\n        ).first()\n        \n        if not performance:\n            return jsonify({'error': 'Annotator performance data not found'}), 404\n        \n        return jsonify({\n            'success': True,\n            'annotator_performance': performance.to_dict()\n        }), 200\n        \n    except Exception as e:\n        logger.error(f\"Error retrieving annotator performance: {str(e)}\")\n        return jsonify({'error': 'Internal server error'}), 500\n\n\n@agreement_bp.route('/reports/dashboard', methods=['GET'])\ndef get_agreement_dashboard():\n    \"\"\"\n    Get dashboard data for agreement overview.\n    \"\"\"\n    try:\n        if not db_session:\n            return jsonify({'error': 'Database not configured'}), 500\n        \n        # Get recent studies\n        recent_studies = db_session.query(AgreementStudy).order_by(\n            AgreementStudy.created_at.desc()\n        ).limit(5).all()\n        \n        # Get top performing annotators\n        top_annotators = db_session.query(AnnotatorPerformance).filter(\n            AnnotatorPerformance.average_kappa_score.isnot(None)\n        ).order_by(\n            AnnotatorPerformance.average_kappa_score.desc()\n        ).limit(5).all()\n        \n        # Get overall statistics\n        total_studies = db_session.query(AgreementStudy).count()\n        total_annotators = db_session.query(AnnotatorPerformance).count()\n        \n        # Calculate average agreement scores\n        avg_cohen_kappa = db_session.query(\n            db_session.query(CohenKappaResult.kappa_value).subquery().c.kappa_value\n        ).scalar()\n        \n        avg_fleiss_kappa = db_session.query(\n            db_session.query(FleissKappaResult.kappa_value).subquery().c.kappa_value\n        ).scalar()\n        \n        dashboard_data = {\n            'recent_studies': [study.to_dict() for study in recent_studies],\n            'top_annotators': [annotator.to_dict() for annotator in top_annotators],\n            'statistics': {\n                'total_studies': total_studies,\n                'total_annotators': total_annotators,\n                'average_cohen_kappa': avg_cohen_kappa,\n                'average_fleiss_kappa': avg_fleiss_kappa\n            },\n            'generated_at': datetime.now().isoformat()\n        }\n        \n        return jsonify({\n            'success': True,\n            'dashboard': dashboard_data\n        }), 200\n        \n    except Exception as e:\n        logger.error(f\"Error generating agreement dashboard: {str(e)}\")\n        return jsonify({'error': 'Internal server error'}), 500\n\n\n@agreement_bp.route('/metrics/guidelines', methods=['GET'])\ndef get_interpretation_guidelines():"}
    """Get guidelines for interpreting agreement metric values."""
    guidelines = {
        'cohen_kappa': {
            'ranges': [
                {'min': 0.81, 'max': 1.00, 'interpretation': 'Almost Perfect', 'recommendation': 'Excellent agreement'},
                {'min': 0.61, 'max': 0.80, 'interpretation': 'Substantial', 'recommendation': 'Good agreement, minor improvements may help'},
                {'min': 0.41, 'max': 0.60, 'interpretation': 'Moderate', 'recommendation': 'Acceptable for some purposes, consider improvements'},
                {'min': 0.21, 'max': 0.40, 'interpretation': 'Fair', 'recommendation': 'Poor agreement, training needed'},
                {'min': 0.01, 'max': 0.20, 'interpretation': 'Slight', 'recommendation': 'Very poor agreement, major improvements needed'},
                {'min': -1.00, 'max': 0.00, 'interpretation': 'Poor', 'recommendation': 'Worse than random, review methodology'}
            ],
            'reference': 'Landis & Koch (1977)'
        },
        'fleiss_kappa': {
            'ranges': [
                {'min': 0.81, 'max': 1.00, 'interpretation': 'Almost Perfect', 'recommendation': 'Excellent agreement'},
                {'min': 0.61, 'max': 0.80, 'interpretation': 'Substantial', 'recommendation': 'Good agreement'},
                {'min': 0.41, 'max': 0.60, 'interpretation': 'Moderate', 'recommendation': 'Acceptable for exploratory research'},
                {'min': 0.21, 'max': 0.40, 'interpretation': 'Fair', 'recommendation': 'Poor agreement'},
                {'min': 0.01, 'max': 0.20, 'interpretation': 'Slight', 'recommendation': 'Very poor agreement'},
                {'min': -1.00, 'max': 0.00, 'interpretation': 'Poor', 'recommendation': 'Systematic disagreement'}
            ],
            'reference': 'Landis & Koch (1977)'
        },
        'krippendorff_alpha': {
            'ranges': [
                {'min': 0.80, 'max': 1.00, 'interpretation': 'High', 'recommendation': 'Acceptable for most purposes'},
                {'min': 0.67, 'max': 0.79, 'interpretation': 'Moderate', 'recommendation': 'Acceptable for some purposes'},
                {'min': 0.00, 'max': 0.66, 'interpretation': 'Low', 'recommendation': 'Inadequate for most purposes'},
                {'min': -1.00, 'max': -0.01, 'interpretation': 'Poor', 'recommendation': 'Systematic disagreement'}
            ],
            'reference': 'Krippendorff (2004)'
        },
        'general_recommendations': [
            'Values below acceptable thresholds suggest need for annotator training',
            'Consider refining annotation guidelines if agreement is consistently low',
            'Multiple metrics can provide different perspectives on agreement',
            'Bootstrap confidence intervals help assess reliability of estimates',
            'Consider the specific requirements of your research domain'
        ]
    }
    
    return jsonify({
        'success': True,
        'interpretation_guidelines': guidelines
    }), 200


# Error handlers
@agreement_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@agreement_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405


@agreement_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@agreement_bp.route('/projects/<int:project_id>/calculate', methods=['POST'])
def calculate_project_agreement(project_id: int):
    """
    Calculate inter-annotator agreement for a specific project.
    
    Expected JSON payload:
    {
        "text_ids": [list of text IDs] (optional - if not provided, uses all texts),
        "annotator_ids": [list of annotator IDs] (optional - if not provided, uses all annotators),
        "label_ids": [list of label IDs] (optional - if not provided, uses all labels),
        "agreement_method": "span_overlap|exact_match|label_only" (default: "span_overlap"),
        "overlap_threshold": 0.5 (for span_overlap method),
        "save_to_database": true|false (default: true),
        "study_name": "string" (optional),
        "study_description": "string" (optional)
    }
    """
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        data = request.get_json() or {}
        
        # Verify project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Extract annotations for agreement calculation
        annotations_data = extract_project_annotations(
            db_session, 
            project_id,
            text_ids=data.get('text_ids'),
            annotator_ids=data.get('annotator_ids'),
            label_ids=data.get('label_ids'),
            agreement_method=data.get('agreement_method', 'span_overlap'),
            overlap_threshold=data.get('overlap_threshold', 0.5)
        )
        
        if not annotations_data or len(annotations_data) < 2:
            return jsonify({'error': 'Need at least 2 annotators with annotations for agreement calculation'}), 400
        
        # Perform comprehensive analysis
        results = agreement_analysis.analyze_dataset(annotations_data, True)
        
        # Add project metadata
        results['project_info'] = {
            'project_id': project_id,
            'project_name': project.name,
            'calculation_timestamp': datetime.now().isoformat(),
            'agreement_method': data.get('agreement_method', 'span_overlap'),
            'overlap_threshold': data.get('overlap_threshold', 0.5)
        }
        
        # Save to database if requested
        if data.get('save_to_database', True):
            study_name = data.get('study_name', f"Project {project.name} Agreement Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            study_description = data.get('study_description', f"Automated agreement analysis for project {project.name}")
            
            try:
                study_id = store_agreement_analysis(
                    db_session, 
                    results, 
                    study_name, 
                    study_description
                )
                results['database_info'] = {
                    'saved': True,
                    'study_id': study_id,
                    'study_name': study_name
                }
            except Exception as e:
                logger.error(f"Error saving project agreement analysis: {str(e)}")
                results['database_info'] = {
                    'saved': False,
                    'error': str(e)
                }
        
        return jsonify({
            'success': True,
            'analysis_type': 'project_agreement',
            'results': results
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error calculating project agreement: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error during project agreement calculation'}), 500


@agreement_bp.route('/projects/<int:project_id>/texts/<int:text_id>/calculate', methods=['POST'])
def calculate_text_agreement(project_id: int, text_id: int):
    """
    Calculate inter-annotator agreement for a specific text within a project.
    
    Expected JSON payload:
    {
        "annotator_ids": [list of annotator IDs] (optional),
        "label_ids": [list of label IDs] (optional),
        "agreement_method": "span_overlap|exact_match|label_only" (default: "span_overlap"),
        "overlap_threshold": 0.5 (for span_overlap method),
        "save_to_database": true|false (default: false)
    }
    """
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        data = request.get_json() or {}
        
        # Verify text exists and belongs to project
        text = db_session.query(Text).filter_by(id=text_id, project_id=project_id).first()
        if not text:
            return jsonify({'error': 'Text not found in this project'}), 404
        
        # Extract annotations for this specific text
        annotations_data = extract_project_annotations(
            db_session, 
            project_id,
            text_ids=[text_id],
            annotator_ids=data.get('annotator_ids'),
            label_ids=data.get('label_ids'),
            agreement_method=data.get('agreement_method', 'span_overlap'),
            overlap_threshold=data.get('overlap_threshold', 0.5)
        )
        
        if not annotations_data or len(annotations_data) < 2:
            return jsonify({'error': 'Need at least 2 annotators with annotations for this text'}), 400
        
        # Perform analysis
        results = agreement_analysis.analyze_dataset(annotations_data, True)
        
        # Add text metadata
        results['text_info'] = {
            'text_id': text_id,
            'text_title': text.title,
            'project_id': project_id,
            'calculation_timestamp': datetime.now().isoformat(),
            'agreement_method': data.get('agreement_method', 'span_overlap')
        }
        
        # Save to database if requested
        if data.get('save_to_database', False):
            study_name = f"Text '{text.title}' Agreement Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            study_description = f"Agreement analysis for text '{text.title}' in project {text.project.name}"
            
            try:
                study_id = store_agreement_analysis(db_session, results, study_name, study_description)
                results['database_info'] = {'saved': True, 'study_id': study_id}
            except Exception as e:
                logger.error(f"Error saving text agreement analysis: {str(e)}")
                results['database_info'] = {'saved': False, 'error': str(e)}
        
        return jsonify({
            'success': True,
            'analysis_type': 'text_agreement',
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error calculating text agreement: {str(e)}")
        return jsonify({'error': 'Internal server error during text agreement calculation'}), 500


@agreement_bp.route('/projects/<int:project_id>/history', methods=['GET'])
def get_project_agreement_history(project_id: int):
    """
    Get agreement calculation history for a project.
    """
    try:
        if not db_session:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Get studies that contain this project's name or were calculated for this project
        studies = db_session.query(AgreementStudy).filter(
            AgreementStudy.name.contains(f'Project') | 
            AgreementStudy.description.contains(str(project_id))
        ).order_by(AgreementStudy.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'studies': [study.to_dict() for study in studies]
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving project agreement history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def extract_project_annotations(db_session, project_id: int, text_ids: Optional[List[int]] = None,
                              annotator_ids: Optional[List[int]] = None, label_ids: Optional[List[int]] = None,
                              agreement_method: str = 'span_overlap', overlap_threshold: float = 0.5) -> Dict[str, List[str]]:
    """
    Extract annotations from a project and convert them to agreement analysis format.
    
    Args:
        db_session: Database session
        project_id: Project ID to extract annotations from
        text_ids: Optional list of specific text IDs
        annotator_ids: Optional list of specific annotator IDs  
        label_ids: Optional list of specific label IDs
        agreement_method: Method for agreement calculation ('span_overlap', 'exact_match', 'label_only')
        overlap_threshold: Minimum overlap threshold for span_overlap method
        
    Returns:
        Dictionary mapping annotator names to lists of annotation labels/spans
    """
    try:
        # Build query for annotations in this project
        query = db_session.query(Annotation).join(Text).filter(Text.project_id == project_id)
        
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
                # Only consider the label, ignore span
                annotation_value = ann.label.name
            elif agreement_method == 'exact_match':
                # Exact span and label match
                annotation_value = f"{ann.label.name}:{ann.start_char}-{ann.end_char}"
            else:  # span_overlap
                # Use span information for overlap calculation
                annotation_value = {
                    'label': ann.label.name,
                    'start': ann.start_char,
                    'end': ann.end_char,
                    'text': ann.selected_text
                }
            
            annotator_annotations[annotator_name][text_id].append(annotation_value)
        
        # Convert to format expected by agreement metrics
        if agreement_method == 'span_overlap':
            # For span overlap, we need to create annotation sequences per text
            # and then merge across texts, handling overlaps
            return convert_span_annotations_to_sequences(
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
                        # Add None for texts this annotator didn't annotate
                        sequence.extend([None] * len(max([text_annotations.get(text_id, []) for text_annotations in annotator_annotations.values()], key=len)))
                
                result[annotator_name] = sequence
            
            # Ensure all sequences have same length
            max_length = max(len(seq) for seq in result.values()) if result else 0
            for annotator_name in result:
                while len(result[annotator_name]) < max_length:
                    result[annotator_name].append(None)
            
            return result
            
    except Exception as e:
        logger.error(f"Error extracting project annotations: {str(e)}")
        raise


def convert_span_annotations_to_sequences(annotator_annotations: Dict[str, Dict[int, List[Dict]]], 
                                        overlap_threshold: float = 0.5) -> Dict[str, List[str]]:
    """
    Convert span-based annotations to agreement analysis sequences.
    
    For span overlap agreement, we create unified annotation items across all texts
    and determine agreement based on span overlap.
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
                    calculate_overlap_ratio(span1, span2) >= overlap_threshold):
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


def calculate_overlap_ratio(span1: Dict, span2: Dict) -> float:
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


# Configuration function
def configure_agreement_api(app: Flask, database_session=None):
    """
    Configure the agreement analysis API with a Flask app.
    
    Args:
        app: Flask application instance
        database_session: SQLAlchemy session for database operations
    """
    global db_session
    db_session = database_session
    
    # Register blueprint
    app.register_blueprint(agreement_bp)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    return app


# Standalone Flask app for testing
def create_app(config=None):
    """Create a standalone Flask app for testing the agreement API."""
    app = Flask(__name__)
    
    # Default configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get('DATABASE_URI', 'sqlite:///agreement.db') if config else 'sqlite:///agreement.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Configure API
    configure_agreement_api(app, session)
    
    return app


if __name__ == '__main__':
    # Run standalone for testing
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)