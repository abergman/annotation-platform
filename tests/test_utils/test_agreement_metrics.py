"""
Unit tests for agreement metrics module.

This module tests all inter-annotator agreement calculations including
Cohen's Kappa, Fleiss' Kappa, and Krippendorff's Alpha.
"""

import unittest
import numpy as np
from typing import List, Any
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from utils.agreement_metrics import AgreementMetrics, AgreementAnalysis, calculate_agreement_metrics


class TestCohenKappa(unittest.TestCase):
    """Test cases for Cohen's Kappa calculations."""
    
    def setUp(self):
        self.metrics = AgreementMetrics()
    
    def test_perfect_agreement(self):
        """Test Cohen's Kappa with perfect agreement."""
        ann1 = ['A', 'B', 'C', 'A', 'B', 'C']
        ann2 = ['A', 'B', 'C', 'A', 'B', 'C']
        
        result = self.metrics.cohen_kappa(ann1, ann2)
        
        self.assertAlmostEqual(result['kappa'], 1.0, places=3)
        self.assertAlmostEqual(result['observed_agreement'], 1.0, places=3)
        self.assertEqual(result['n_items'], 6)
        self.assertIn('categories', result)
    
    def test_no_agreement(self):
        """Test Cohen's Kappa with no agreement (random)."""
        # Create systematically opposite annotations
        ann1 = ['A', 'A', 'A', 'B', 'B', 'B']
        ann2 = ['B', 'B', 'B', 'A', 'A', 'A']
        
        result = self.metrics.cohen_kappa(ann1, ann2)
        
        # Should be negative (worse than chance)
        self.assertLess(result['kappa'], 0.1)
        self.assertLess(result['observed_agreement'], 1.0)
        self.assertEqual(result['n_items'], 6)
    
    def test_moderate_agreement(self):
        """Test Cohen's Kappa with moderate agreement."""
        ann1 = ['A', 'B', 'A', 'A', 'B', 'C', 'A', 'B', 'C', 'A']
        ann2 = ['A', 'B', 'A', 'B', 'B', 'C', 'A', 'C', 'C', 'A']
        
        result = self.metrics.cohen_kappa(ann1, ann2)
        
        # Should be moderate agreement
        self.assertGreater(result['kappa'], 0.2)
        self.assertLess(result['kappa'], 0.9)
        self.assertIn('interpretation', result)
        self.assertIn('standard_error', result)
    
    def test_weighted_kappa_linear(self):
        """Test weighted Cohen's Kappa with linear weights."""
        ann1 = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        ann2 = [1, 2, 3, 4, 4, 2, 2, 3, 3, 5]  # Close but not perfect
        
        result_unweighted = self.metrics.cohen_kappa(ann1, ann2)
        result_weighted = self.metrics.cohen_kappa(ann1, ann2, weights='linear')
        
        # Weighted kappa should be higher for ordinal data
        self.assertGreater(result_weighted['kappa'], result_unweighted['kappa'])
    
    def test_weighted_kappa_quadratic(self):
        """Test weighted Cohen's Kappa with quadratic weights."""
        ann1 = [1, 2, 3, 4, 5] * 4
        ann2 = [1, 2, 4, 4, 5] * 4  # Some disagreement
        
        result_linear = self.metrics.cohen_kappa(ann1, ann2, weights='linear')
        result_quadratic = self.metrics.cohen_kappa(ann1, ann2, weights='quadratic')
        
        # Both should be positive
        self.assertGreater(result_linear['kappa'], 0)
        self.assertGreater(result_quadratic['kappa'], 0)
    
    def test_different_length_arrays(self):
        """Test that different length arrays raise ValueError."""
        ann1 = ['A', 'B', 'C']
        ann2 = ['A', 'B']
        
        with self.assertRaises(ValueError):
            self.metrics.cohen_kappa(ann1, ann2)
    
    def test_empty_arrays(self):
        """Test that empty arrays raise ValueError."""
        ann1 = []
        ann2 = []
        
        with self.assertRaises(ValueError):
            self.metrics.cohen_kappa(ann1, ann2)
    
    def test_confidence_intervals(self):
        """Test that confidence intervals are properly calculated."""
        ann1 = ['A', 'B', 'A', 'B', 'A', 'B', 'A', 'B'] * 5
        ann2 = ['A', 'B', 'A', 'A', 'A', 'B', 'B', 'B'] * 5
        
        result = self.metrics.cohen_kappa(ann1, ann2)
        
        self.assertIn('ci_lower', result)
        self.assertIn('ci_upper', result)
        self.assertLess(result['ci_lower'], result['kappa'])
        self.assertGreater(result['ci_upper'], result['kappa'])
    
    def test_confusion_matrix(self):
        """Test that confusion matrix is correctly generated."""
        ann1 = ['A', 'B', 'A', 'B']
        ann2 = ['A', 'B', 'B', 'B']
        
        result = self.metrics.cohen_kappa(ann1, ann2)
        
        self.assertIn('confusion_matrix', result)
        matrix = np.array(result['confusion_matrix'])
        self.assertEqual(matrix.shape, (2, 2))  # 2x2 for categories A, B
        self.assertEqual(np.sum(matrix), 4)  # Total items


class TestFleissKappa(unittest.TestCase):
    """Test cases for Fleiss' Kappa calculations."""
    
    def setUp(self):
        self.metrics = AgreementMetrics()
    
    def test_perfect_agreement_three_annotators(self):
        """Test Fleiss' Kappa with perfect agreement among 3 annotators."""
        annotations = [
            ['A', 'B', 'C', 'A', 'B'],
            ['A', 'B', 'C', 'A', 'B'],
            ['A', 'B', 'C', 'A', 'B']
        ]
        
        result = self.metrics.fleiss_kappa(annotations)
        
        self.assertAlmostEqual(result['kappa'], 1.0, places=3)
        self.assertEqual(result['n_annotators'], 3)
        self.assertEqual(result['n_items'], 5)
    
    def test_moderate_agreement_multiple_annotators(self):
        """Test Fleiss' Kappa with moderate agreement."""
        annotations = [
            ['A', 'B', 'C', 'A', 'B', 'C', 'A'],
            ['A', 'B', 'C', 'B', 'B', 'C', 'A'],
            ['A', 'C', 'C', 'A', 'B', 'B', 'A'],
            ['B', 'B', 'C', 'A', 'B', 'C', 'B']
        ]
        
        result = self.metrics.fleiss_kappa(annotations)
        
        self.assertGreater(result['kappa'], 0.0)
        self.assertLess(result['kappa'], 1.0)
        self.assertEqual(result['n_annotators'], 4)
        self.assertEqual(result['n_items'], 7)
        self.assertIn('interpretation', result)
    
    def test_category_statistics(self):
        """Test that per-category statistics are calculated."""
        annotations = [
            ['A', 'A', 'B', 'B', 'C'],
            ['A', 'B', 'B', 'B', 'C'],
            ['A', 'A', 'B', 'C', 'C']
        ]
        
        result = self.metrics.fleiss_kappa(annotations)
        
        self.assertIn('category_stats', result)
        stats = result['category_stats']
        self.assertIn('A', stats)
        self.assertIn('B', stats)
        self.assertIn('C', stats)
        
        # Check that proportions sum to approximately 1
        total_prop = sum(stat['proportion'] for stat in stats.values())
        self.assertAlmostEqual(total_prop, 1.0, places=2)
    
    def test_insufficient_annotators(self):
        """Test that insufficient annotators raises ValueError."""
        annotations = [['A', 'B', 'C']]  # Only one annotator
        
        with self.assertRaises(ValueError):
            self.metrics.fleiss_kappa(annotations)
    
    def test_mismatched_lengths(self):
        """Test that mismatched annotation lengths raise ValueError."""
        annotations = [
            ['A', 'B', 'C'],
            ['A', 'B']  # Different length
        ]
        
        with self.assertRaises(ValueError):
            self.metrics.fleiss_kappa(annotations)
    
    def test_confidence_intervals(self):
        """Test that confidence intervals are calculated."""
        annotations = [
            ['A', 'B', 'A', 'B'] * 5,
            ['A', 'B', 'B', 'B'] * 5,
            ['A', 'A', 'A', 'B'] * 5
        ]
        
        result = self.metrics.fleiss_kappa(annotations)
        
        self.assertIn('ci_lower', result)
        self.assertIn('ci_upper', result)
        self.assertIsInstance(result['standard_error'], float)


class TestKrippendorffAlpha(unittest.TestCase):
    """Test cases for Krippendorff's Alpha calculations."""
    
    def setUp(self):
        self.metrics = AgreementMetrics()
    
    def test_perfect_agreement_nominal(self):
        """Test Krippendorff's Alpha with perfect nominal agreement."""
        annotations = [
            ['A', 'B', 'C', 'A', 'B'],
            ['A', 'B', 'C', 'A', 'B'],
            ['A', 'B', 'C', 'A', 'B']
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'nominal')
        
        self.assertAlmostEqual(result['alpha'], 1.0, places=3)
        self.assertEqual(result['metric'], 'nominal')
        self.assertEqual(result['n_annotators'], 3)
    
    def test_ordinal_metric(self):
        """Test Krippendorff's Alpha with ordinal data."""
        annotations = [
            [1, 2, 3, 4, 5, 1, 2, 3],
            [1, 2, 3, 4, 4, 1, 3, 3],
            [1, 3, 3, 4, 5, 2, 2, 3]
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'ordinal')
        
        self.assertGreater(result['alpha'], 0.0)
        self.assertEqual(result['metric'], 'ordinal')
        self.assertIn('interpretation', result)
    
    def test_interval_metric(self):
        """Test Krippendorff's Alpha with interval data."""
        annotations = [
            [1.0, 2.5, 3.2, 4.1, 5.0],
            [1.1, 2.3, 3.0, 4.2, 4.8],
            [0.9, 2.6, 3.1, 4.0, 5.1]
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'interval')
        
        self.assertGreater(result['alpha'], 0.0)
        self.assertEqual(result['metric'], 'interval')
    
    def test_ratio_metric(self):
        """Test Krippendorff's Alpha with ratio data."""
        annotations = [
            [10, 20, 30, 40, 50],
            [12, 18, 32, 38, 48],
            [9, 22, 28, 42, 52]
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'ratio')
        
        self.assertEqual(result['metric'], 'ratio')
        self.assertIn('alpha', result)
    
    def test_missing_values(self):
        """Test Krippendorff's Alpha with missing values."""
        annotations = [
            ['A', 'B', None, 'A', 'B'],
            ['A', None, 'C', 'A', 'B'],
            [None, 'B', 'C', 'B', 'B']
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'nominal', missing_value=None)
        
        self.assertIn('alpha', result)
        self.assertGreater(result['n_pairs'], 0)  # Should still find valid pairs
    
    def test_confidence_intervals(self):
        """Test that bootstrap confidence intervals are calculated."""
        annotations = [
            ['A', 'B', 'A', 'B'] * 10,
            ['A', 'B', 'B', 'B'] * 10,
            ['A', 'A', 'A', 'B'] * 10
        ]
        
        result = self.metrics.krippendorff_alpha(annotations, 'nominal')
        
        self.assertIn('ci_lower', result)
        self.assertIn('ci_upper', result)
        # Confidence intervals should bracket the alpha value
        self.assertLessEqual(result['ci_lower'], result['alpha'])
        self.assertGreaterEqual(result['ci_upper'], result['alpha'])
    
    def test_insufficient_annotators(self):
        """Test that insufficient annotators raises ValueError."""
        annotations = [['A', 'B', 'C']]
        
        with self.assertRaises(ValueError):
            self.metrics.krippendorff_alpha(annotations)
    
    def test_invalid_metric(self):
        """Test that invalid metric types are handled."""
        annotations = [
            ['A', 'B', 'C'],
            ['A', 'B', 'C']
        ]
        
        # Should not raise error, but use default handling
        result = self.metrics.krippendorff_alpha(annotations, 'invalid_metric')
        self.assertIn('alpha', result)


class TestAgreementAnalysis(unittest.TestCase):
    """Test cases for comprehensive agreement analysis."""
    
    def setUp(self):
        self.analysis = AgreementAnalysis()
    
    def test_comprehensive_analysis(self):
        """Test comprehensive analysis with multiple metrics."""
        annotations = {
            'annotator1': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B'],
            'annotator2': ['A', 'B', 'C', 'B', 'B', 'C', 'A', 'C'],
            'annotator3': ['A', 'C', 'C', 'A', 'B', 'B', 'A', 'B']
        }
        
        result = self.analysis.analyze_dataset(annotations, include_all_metrics=True)
        
        # Check dataset info
        self.assertEqual(result['dataset_info']['n_annotators'], 3)
        self.assertEqual(result['dataset_info']['n_items'], 8)
        self.assertIn('annotators', result['dataset_info'])
        
        # Check metrics
        self.assertIn('metrics', result)
        self.assertIn('pairwise_cohen_kappa', result['metrics'])
        self.assertIn('fleiss_kappa', result['metrics'])
        self.assertIn('krippendorff_alpha', result['metrics'])
        
        # Check summary
        self.assertIn('summary', result)
        self.assertIn('overall_quality', result['summary'])
        self.assertIn('recommendations', result['summary'])
    
    def test_pairwise_cohen_kappa(self):
        """Test that all pairwise Cohen's Kappa values are calculated."""
        annotations = {
            'ann1': ['A', 'B', 'A', 'B'],
            'ann2': ['A', 'B', 'B', 'B'],
            'ann3': ['B', 'B', 'A', 'B']
        }
        
        result = self.analysis.analyze_dataset(annotations)
        
        pairwise = result['metrics']['pairwise_cohen_kappa']
        
        # Should have 3 pairs for 3 annotators: (1,2), (1,3), (2,3)
        self.assertEqual(len(pairwise), 3)
        self.assertIn('ann1_vs_ann2', pairwise)
        self.assertIn('ann1_vs_ann3', pairwise)
        self.assertIn('ann2_vs_ann3', pairwise)
        
        # Each result should have kappa value
        for pair_result in pairwise.values():
            self.assertIn('kappa', pair_result)
    
    def test_insufficient_annotators(self):
        """Test analysis with insufficient annotators."""
        annotations = {
            'single_annotator': ['A', 'B', 'C']
        }
        
        with self.assertRaises(ValueError):
            self.analysis.analyze_dataset(annotations)
    
    def test_summary_generation(self):
        """Test that summary includes appropriate recommendations."""
        # Create high agreement data
        high_agreement = {
            'ann1': ['A', 'B', 'C'] * 10,
            'ann2': ['A', 'B', 'C'] * 10,
            'ann3': ['A', 'B', 'C'] * 10
        }
        
        result = self.analysis.analyze_dataset(high_agreement)
        summary = result['summary']
        
        self.assertIn('overall_quality', summary)
        self.assertIn('key_findings', summary)
        self.assertIn('recommendations', summary)
        
        # High agreement should result in positive recommendations
        if summary['recommendations']:
            rec_text = ' '.join(summary['recommendations']).lower()
            self.assertTrue('excellent' in rec_text or 'reliable' in rec_text)


class TestConvenienceFunction(unittest.TestCase):
    """Test cases for the convenience function."""
    
    def test_dict_input_comprehensive(self):
        """Test convenience function with dictionary input."""
        annotations = {
            'annotator1': ['A', 'B', 'A', 'B'],
            'annotator2': ['A', 'B', 'B', 'B']
        }
        
        result = calculate_agreement_metrics(annotations, 'all')
        
        self.assertIn('dataset_info', result)
        self.assertIn('metrics', result)
    
    def test_list_input_cohen(self):
        """Test convenience function with list input for Cohen's Kappa."""
        annotations = [
            ['A', 'B', 'A', 'B'],
            ['A', 'B', 'B', 'B']
        ]
        
        result = calculate_agreement_metrics(annotations, 'cohen')
        
        self.assertIn('kappa', result)
        self.assertIn('interpretation', result)
    
    def test_list_input_fleiss(self):
        """Test convenience function with list input for Fleiss' Kappa."""
        annotations = [
            ['A', 'B', 'A', 'B'],
            ['A', 'B', 'B', 'B'],
            ['A', 'A', 'A', 'B']
        ]
        
        result = calculate_agreement_metrics(annotations, 'fleiss')
        
        self.assertIn('kappa', result)
        self.assertEqual(result['n_annotators'], 3)
    
    def test_list_input_alpha(self):
        """Test convenience function with list input for Krippendorff's Alpha."""
        annotations = [
            ['A', 'B', 'A', 'B'],
            ['A', 'B', 'B', 'B'],
            ['A', 'A', 'A', 'B']
        ]
        
        result = calculate_agreement_metrics(annotations, 'alpha')
        
        self.assertIn('alpha', result)
        self.assertEqual(result['n_annotators'], 3)


class TestInterpretationFunctions(unittest.TestCase):
    """Test cases for interpretation helper functions."""
    
    def setUp(self):
        self.metrics = AgreementMetrics()
    
    def test_kappa_interpretation(self):
        """Test Kappa interpretation categories."""
        # Test various kappa values
        test_values = [
            (-0.1, "Poor"),
            (0.1, "Slight"),
            (0.3, "Fair"),
            (0.5, "Moderate"),
            (0.7, "Substantial"),
            (0.9, "Almost Perfect")
        ]
        
        for kappa_value, expected in test_values:
            interpretation = self.metrics._interpret_kappa(kappa_value)
            self.assertIn(expected.lower(), interpretation.lower())
    
    def test_alpha_interpretation(self):
        """Test Alpha interpretation categories."""
        test_values = [
            (-0.1, "Poor"),
            (0.5, "Low"),
            (0.75, "Moderate"),
            (0.85, "High")
        ]
        
        for alpha_value, expected in test_values:
            interpretation = self.metrics._interpret_alpha(alpha_value)
            self.assertIn(expected.lower(), interpretation.lower())


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCohenKappa,
        TestFleissKappa,
        TestKrippendorffAlpha,
        TestAgreementAnalysis,
        TestConvenienceFunction,
        TestInterpretationFunctions
    ]
    
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