"""
Unit tests for agreement database models.

This module tests the database models used for storing agreement calculations
and related data.
"""

import unittest
import tempfile
import os
import json
from datetime import datetime
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.agreement import (
    Base, AgreementStudy, CohenKappaResult, FleissKappaResult, 
    KrippendorffAlphaResult, StudyRecommendation, AnnotatorPerformance,
    create_tables, get_study_summary, store_agreement_analysis
)


class TestAgreementModels(unittest.TestCase):
    """Test cases for agreement database models."""
    
    def setUp(self):
        """Set up test database."""
        # Create temporary database
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        self.engine = create_engine(f'sqlite:///{self.db_file.name}', echo=False)
        create_tables(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def tearDown(self):
        """Clean up test database."""
        self.session.close()
        os.unlink(self.db_file.name)
    
    def test_create_agreement_study(self):
        """Test creating an agreement study."""
        study = AgreementStudy(
            name="Test Study",
            description="A test agreement study",
            dataset_name="test_dataset",
            n_annotators=3,
            n_items=100,
            annotation_categories=['A', 'B', 'C'],
            annotator_names=['ann1', 'ann2', 'ann3'],
            metrics_calculated=['cohen_kappa', 'fleiss_kappa'],
            overall_quality_score=0.75,
            quality_interpretation="Substantial"
        )
        
        self.session.add(study)
        self.session.commit()
        
        # Verify study was created
        retrieved = self.session.query(AgreementStudy).filter_by(name="Test Study").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.n_annotators, 3)
        self.assertEqual(retrieved.n_items, 100)
        self.assertEqual(retrieved.annotation_categories, ['A', 'B', 'C'])
        self.assertEqual(retrieved.annotator_names, ['ann1', 'ann2', 'ann3'])
    
    def test_agreement_study_to_dict(self):
        """Test converting agreement study to dictionary."""
        study = AgreementStudy(
            name="Dict Test Study",
            description="Test dictionary conversion",
            n_annotators=2,
            n_items=50,
            annotation_categories=['X', 'Y'],
            overall_quality_score=0.60
        )
        
        self.session.add(study)
        self.session.commit()
        
        study_dict = study.to_dict()
        
        self.assertEqual(study_dict['name'], "Dict Test Study")
        self.assertEqual(study_dict['n_annotators'], 2)
        self.assertEqual(study_dict['n_items'], 50)
        self.assertEqual(study_dict['annotation_categories'], ['X', 'Y'])
        self.assertEqual(study_dict['overall_quality_score'], 0.60)
        self.assertIsNotNone(study_dict['id'])
    
    def test_create_cohen_kappa_result(self):
        """Test creating Cohen's Kappa result."""
        # Create parent study
        study = AgreementStudy(
            name="Kappa Test Study",
            n_annotators=2,
            n_items=20
        )
        self.session.add(study)
        self.session.commit()
        
        # Create Cohen's Kappa result
        kappa_result = CohenKappaResult(
            study_id=study.id,
            annotator1_name="ann1",
            annotator2_name="ann2",
            kappa_value=0.75,
            standard_error=0.05,
            confidence_interval_lower=0.65,
            confidence_interval_upper=0.85,
            observed_agreement=0.80,
            expected_agreement=0.20,
            n_items=20,
            categories=['A', 'B', 'C'],
            confusion_matrix=[[10, 2, 1], [1, 5, 1], [0, 0, 0]],
            interpretation="Substantial",
            quality_level="good"
        )
        
        self.session.add(kappa_result)
        self.session.commit()
        
        # Verify result was created
        retrieved = self.session.query(CohenKappaResult).filter_by(study_id=study.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.kappa_value, 0.75)
        self.assertEqual(retrieved.annotator1_name, "ann1")
        self.assertEqual(retrieved.annotator2_name, "ann2")
        self.assertEqual(retrieved.categories, ['A', 'B', 'C'])
        self.assertEqual(retrieved.confusion_matrix, [[10, 2, 1], [1, 5, 1], [0, 0, 0]])
    
    def test_cohen_kappa_result_to_dict(self):
        """Test converting Cohen's Kappa result to dictionary."""
        study = AgreementStudy(name="Dict Kappa Study", n_annotators=2, n_items=10)
        self.session.add(study)
        self.session.commit()
        
        kappa_result = CohenKappaResult(
            study_id=study.id,
            annotator1_name="test_ann1",
            annotator2_name="test_ann2",
            kappa_value=0.65,
            standard_error=0.08,
            n_items=10,
            interpretation="Substantial"
        )
        
        self.session.add(kappa_result)
        self.session.commit()
        
        result_dict = kappa_result.to_dict()
        
        self.assertEqual(result_dict['study_id'], study.id)
        self.assertEqual(result_dict['annotator1_name'], "test_ann1")
        self.assertEqual(result_dict['annotator2_name'], "test_ann2")
        self.assertEqual(result_dict['kappa_value'], 0.65)
        self.assertEqual(result_dict['standard_error'], 0.08)
        self.assertEqual(result_dict['interpretation'], "Substantial")
    
    def test_create_fleiss_kappa_result(self):
        """Test creating Fleiss' Kappa result."""
        study = AgreementStudy(name="Fleiss Test Study", n_annotators=4, n_items=30)
        self.session.add(study)
        self.session.commit()
        
        fleiss_result = FleissKappaResult(
            study_id=study.id,
            kappa_value=0.68,
            standard_error=0.06,
            confidence_interval_lower=0.56,
            confidence_interval_upper=0.80,
            observed_agreement=0.75,
            expected_agreement=0.25,
            n_annotators=4,
            n_items=30,
            categories=['positive', 'negative', 'neutral'],
            category_statistics={
                'positive': {'count': 40, 'proportion': 0.33},
                'negative': {'count': 35, 'proportion': 0.29},
                'neutral': {'count': 45, 'proportion': 0.38}
            },
            interpretation="Substantial"
        )
        
        self.session.add(fleiss_result)
        self.session.commit()
        
        retrieved = self.session.query(FleissKappaResult).filter_by(study_id=study.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.kappa_value, 0.68)
        self.assertEqual(retrieved.n_annotators, 4)
        self.assertEqual(retrieved.n_items, 30)
        self.assertEqual(retrieved.categories, ['positive', 'negative', 'neutral'])
        self.assertIn('positive', retrieved.category_statistics)
    
    def test_create_krippendorff_alpha_result(self):
        """Test creating Krippendorff's Alpha result."""
        study = AgreementStudy(name="Alpha Test Study", n_annotators=3, n_items=25)
        self.session.add(study)
        self.session.commit()
        
        alpha_result = KrippendorffAlphaResult(
            study_id=study.id,
            alpha_value=0.72,
            confidence_interval_lower=0.61,
            confidence_interval_upper=0.83,
            observed_disagreement=0.15,
            expected_disagreement=0.54,
            n_annotators=3,
            n_items=25,
            n_pairs=150,
            distance_metric="ordinal",
            bootstrap_iterations=1000,
            bootstrap_confidence_level=0.95,
            interpretation="Moderate"
        )
        
        self.session.add(alpha_result)
        self.session.commit()
        
        retrieved = self.session.query(KrippendorffAlphaResult).filter_by(study_id=study.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.alpha_value, 0.72)
        self.assertEqual(retrieved.distance_metric, "ordinal")
        self.assertEqual(retrieved.n_pairs, 150)
        self.assertEqual(retrieved.bootstrap_iterations, 1000)
    
    def test_create_study_recommendation(self):
        """Test creating study recommendations."""
        study = AgreementStudy(name="Rec Test Study", n_annotators=2, n_items=15)
        self.session.add(study)
        self.session.commit()
        
        recommendation = StudyRecommendation(
            study_id=study.id,
            recommendation_type="training",
            recommendation_text="Consider additional annotator training to improve agreement",
            priority_level="high",
            triggered_by_metric="cohen_kappa",
            threshold_value=0.60,
            actual_value=0.45
        )
        
        self.session.add(recommendation)
        self.session.commit()
        
        retrieved = self.session.query(StudyRecommendation).filter_by(study_id=study.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.recommendation_type, "training")
        self.assertEqual(retrieved.priority_level, "high")
        self.assertEqual(retrieved.threshold_value, 0.60)
        self.assertEqual(retrieved.actual_value, 0.45)
    
    def test_annotator_performance(self):
        """Test annotator performance tracking."""
        performance = AnnotatorPerformance(
            annotator_name="test_annotator",
            studies_participated=5,
            average_kappa_score=0.68,
            consistency_rating="good",
            performance_history=[
                {"study_id": 1, "kappa": 0.65, "date": "2023-01-01"},
                {"study_id": 2, "kappa": 0.71, "date": "2023-02-01"}
            ],
            improvement_trend="improving",
            total_items_annotated=500
        )
        
        self.session.add(performance)
        self.session.commit()
        
        retrieved = self.session.query(AnnotatorPerformance).filter_by(annotator_name="test_annotator").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.studies_participated, 5)
        self.assertEqual(retrieved.average_kappa_score, 0.68)
        self.assertEqual(retrieved.improvement_trend, "improving")
        self.assertEqual(len(retrieved.performance_history), 2)
    
    def test_study_relationships(self):
        """Test relationships between models."""
        # Create study
        study = AgreementStudy(name="Relationship Test", n_annotators=3, n_items=20)
        self.session.add(study)
        self.session.commit()
        
        # Add related results
        cohen_result = CohenKappaResult(
            study_id=study.id,
            annotator1_name="ann1",
            annotator2_name="ann2",
            kappa_value=0.70,
            n_items=20
        )
        
        fleiss_result = FleissKappaResult(
            study_id=study.id,
            kappa_value=0.65,
            n_annotators=3,
            n_items=20
        )
        
        recommendation = StudyRecommendation(
            study_id=study.id,
            recommendation_type="guidelines",
            recommendation_text="Consider updating annotation guidelines"
        )
        
        self.session.add_all([cohen_result, fleiss_result, recommendation])
        self.session.commit()
        
        # Test relationships
        self.assertEqual(len(study.cohen_kappa_results), 1)
        self.assertEqual(len(study.fleiss_kappa_results), 1)
        self.assertEqual(len(study.study_recommendations), 1)
        
        # Test reverse relationships
        self.assertEqual(cohen_result.study, study)
        self.assertEqual(fleiss_result.study, study)
        self.assertEqual(recommendation.study, study)


class TestDatabaseUtilities(unittest.TestCase):
    """Test cases for database utility functions."""
    
    def setUp(self):
        """Set up test database."""
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        self.engine = create_engine(f'sqlite:///{self.db_file.name}', echo=False)
        create_tables(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def tearDown(self):
        """Clean up test database."""
        self.session.close()
        os.unlink(self.db_file.name)
    
    def test_get_study_summary(self):
        """Test getting comprehensive study summary."""
        # Create study with results
        study = AgreementStudy(name="Summary Test", n_annotators=2, n_items=10)
        self.session.add(study)
        self.session.commit()
        
        cohen_result = CohenKappaResult(
            study_id=study.id,
            annotator1_name="ann1",
            annotator2_name="ann2",
            kappa_value=0.75,
            n_items=10
        )
        
        recommendation = StudyRecommendation(
            study_id=study.id,
            recommendation_type="training",
            recommendation_text="Excellent agreement"
        )
        
        self.session.add_all([cohen_result, recommendation])
        self.session.commit()
        
        # Get summary
        summary = get_study_summary(self.session, study.id)
        
        self.assertIsNotNone(summary)
        self.assertEqual(summary['name'], "Summary Test")
        self.assertEqual(len(summary['cohen_kappa_results']), 1)
        self.assertEqual(len(summary['recommendations']), 1)
        self.assertEqual(summary['cohen_kappa_results'][0]['kappa_value'], 0.75)
    
    def test_get_nonexistent_study_summary(self):
        """Test getting summary for nonexistent study."""
        summary = get_study_summary(self.session, 999)
        self.assertIsNone(summary)
    
    def test_store_agreement_analysis(self):
        """Test storing complete agreement analysis results."""
        # Create sample analysis results
        analysis_results = {
            'dataset_info': {
                'n_annotators': 3,
                'n_items': 20,
                'annotators': ['ann1', 'ann2', 'ann3']
            },
            'metrics': {
                'pairwise_cohen_kappa': {
                    'ann1_vs_ann2': {
                        'kappa': 0.75,
                        'standard_error': 0.05,
                        'ci_lower': 0.65,
                        'ci_upper': 0.85,
                        'observed_agreement': 0.80,
                        'expected_agreement': 0.20,
                        'n_items': 20,
                        'categories': ['A', 'B'],
                        'confusion_matrix': [[10, 2], [3, 5]],
                        'interpretation': 'Substantial'
                    }
                },
                'fleiss_kappa': {
                    'kappa': 0.68,
                    'standard_error': 0.06,
                    'ci_lower': 0.56,
                    'ci_upper': 0.80,
                    'observed_agreement': 0.75,
                    'expected_agreement': 0.25,
                    'n_annotators': 3,
                    'n_items': 20,
                    'categories': ['A', 'B'],
                    'category_stats': {
                        'A': {'count': 30, 'proportion': 0.5},
                        'B': {'count': 30, 'proportion': 0.5}
                    },
                    'interpretation': 'Substantial'
                },
                'krippendorff_alpha': {
                    'alpha': 0.72,
                    'ci_lower': 0.61,
                    'ci_upper': 0.83,
                    'observed_disagreement': 0.15,
                    'expected_disagreement': 0.54,
                    'n_annotators': 3,
                    'n_items': 20,
                    'n_pairs': 60,
                    'metric': 'nominal',
                    'interpretation': 'Moderate'
                }
            },
            'summary': {
                'overall_quality': 'Good',
                'recommendations': [
                    'Good agreement achieved',
                    'Consider minor improvements'
                ],
                'key_findings': [
                    'Fleiss Kappa: 0.68 (Substantial)',
                    'Alpha: 0.72 (Moderate)'
                ]
            }
        }
        
        # Store analysis
        study_id = store_agreement_analysis(
            self.session,
            analysis_results,
            "Stored Analysis Test",
            "Test storing complete analysis"
        )
        
        # Verify study was created
        study = self.session.query(AgreementStudy).filter_by(id=study_id).first()
        self.assertIsNotNone(study)
        self.assertEqual(study.name, "Stored Analysis Test")
        self.assertEqual(study.n_annotators, 3)
        self.assertEqual(study.n_items, 20)
        
        # Verify results were stored
        cohen_results = self.session.query(CohenKappaResult).filter_by(study_id=study_id).all()
        self.assertEqual(len(cohen_results), 1)
        self.assertEqual(cohen_results[0].kappa_value, 0.75)
        
        fleiss_results = self.session.query(FleissKappaResult).filter_by(study_id=study_id).all()
        self.assertEqual(len(fleiss_results), 1)
        self.assertEqual(fleiss_results[0].kappa_value, 0.68)
        
        alpha_results = self.session.query(KrippendorffAlphaResult).filter_by(study_id=study_id).all()
        self.assertEqual(len(alpha_results), 1)
        self.assertEqual(alpha_results[0].alpha_value, 0.72)
        
        recommendations = self.session.query(StudyRecommendation).filter_by(study_id=study_id).all()
        self.assertEqual(len(recommendations), 2)  # Two recommendations from summary
    
    def test_create_tables(self):
        """Test that all tables are created properly."""
        # Tables should already be created in setUp
        # Verify we can query each table
        studies = self.session.query(AgreementStudy).all()
        cohen_results = self.session.query(CohenKappaResult).all()
        fleiss_results = self.session.query(FleissKappaResult).all()
        alpha_results = self.session.query(KrippendorffAlphaResult).all()
        recommendations = self.session.query(StudyRecommendation).all()
        performances = self.session.query(AnnotatorPerformance).all()
        
        # Should be empty but no errors
        self.assertEqual(len(studies), 0)
        self.assertEqual(len(cohen_results), 0)
        self.assertEqual(len(fleiss_results), 0)
        self.assertEqual(len(alpha_results), 0)
        self.assertEqual(len(recommendations), 0)
        self.assertEqual(len(performances), 0)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [TestAgreementModels, TestDatabaseUtilities]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")