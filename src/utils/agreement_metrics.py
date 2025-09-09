"""
Inter-Annotator Agreement Metrics Module

This module provides comprehensive statistical calculations for measuring
annotation quality and reliability between multiple annotators.

Supported metrics:
- Cohen's Kappa (2 annotators)
- Fleiss' Kappa (multiple annotators)  
- Krippendorff's Alpha (any number of annotators, any data type)
"""

import numpy as np
from typing import Dict, List, Tuple, Union, Optional, Any
import pandas as pd
from scipy import stats
from collections import defaultdict, Counter
import warnings


class AgreementMetrics:
    """
    A comprehensive class for calculating inter-annotator agreement metrics.
    """
    
    def __init__(self):
        self.results_cache = {}
    
    def cohen_kappa(self, annotator1: List[Any], annotator2: List[Any], 
                   weights: Optional[str] = None) -> Dict[str, float]:
        """
        Calculate Cohen's Kappa for two annotators.
        
        Args:
            annotator1: Annotations from first annotator
            annotator2: Annotations from second annotator  
            weights: Type of weighting ('linear', 'quadratic', or None)
            
        Returns:
            Dictionary with kappa value, standard error, and confidence intervals
        """
        if len(annotator1) != len(annotator2):
            raise ValueError("Annotator arrays must have same length")
        
        # Convert to numpy arrays
        ann1 = np.array(annotator1)
        ann2 = np.array(annotator2)
        
        # Get unique categories
        categories = sorted(list(set(ann1) | set(ann2)))
        n_cats = len(categories)
        n_items = len(ann1)
        
        # Create confusion matrix
        confusion_matrix = np.zeros((n_cats, n_cats))
        cat_to_idx = {cat: idx for idx, cat in enumerate(categories)}
        
        for a1, a2 in zip(ann1, ann2):
            i, j = cat_to_idx[a1], cat_to_idx[a2]
            confusion_matrix[i, j] += 1
        
        # Calculate observed agreement
        p_o = np.trace(confusion_matrix) / n_items
        
        # Calculate expected agreement
        marginal1 = confusion_matrix.sum(axis=1) / n_items
        marginal2 = confusion_matrix.sum(axis=0) / n_items
        p_e = np.sum(marginal1 * marginal2)
        
        # Calculate weighted agreement if specified
        if weights is not None:
            weight_matrix = self._get_weight_matrix(n_cats, weights)
            
            # Weighted observed agreement
            p_o_w = np.sum(confusion_matrix * weight_matrix) / n_items
            
            # Weighted expected agreement
            p_e_w = 0
            for i in range(n_cats):
                for j in range(n_cats):
                    p_e_w += marginal1[i] * marginal2[j] * weight_matrix[i, j]
            
            kappa = (p_o_w - p_e_w) / (1 - p_e_w) if p_e_w != 1 else 1.0
        else:
            kappa = (p_o - p_e) / (1 - p_e) if p_e != 1 else 1.0
        
        # Calculate standard error
        se = self._cohen_kappa_se(confusion_matrix, p_o, p_e, n_items)
        
        # 95% confidence intervals
        z_score = 1.96
        ci_lower = kappa - z_score * se
        ci_upper = kappa + z_score * se
        
        return {
            'kappa': round(kappa, 4),
            'standard_error': round(se, 4),
            'ci_lower': round(ci_lower, 4),
            'ci_upper': round(ci_upper, 4),
            'observed_agreement': round(p_o, 4),
            'expected_agreement': round(p_e, 4),
            'n_items': n_items,
            'categories': categories,
            'confusion_matrix': confusion_matrix.tolist(),
            'interpretation': self._interpret_kappa(kappa)
        }
    
    def fleiss_kappa(self, annotations: List[List[Any]]) -> Dict[str, float]:
        """
        Calculate Fleiss' Kappa for multiple annotators.
        
        Args:
            annotations: List of annotation lists, one per annotator
            
        Returns:
            Dictionary with kappa value and related statistics
        """
        if len(annotations) < 2:
            raise ValueError("Need at least 2 annotators")
        
        n_annotators = len(annotations)
        n_items = len(annotations[0])
        
        # Verify all annotators have same number of items
        if not all(len(ann) == n_items for ann in annotations):
            raise ValueError("All annotators must annotate same number of items")
        
        # Get unique categories
        all_categories = set()
        for ann in annotations:
            all_categories.update(ann)
        categories = sorted(list(all_categories))
        n_cats = len(categories)
        cat_to_idx = {cat: idx for idx, cat in enumerate(categories)}
        
        # Create agreement matrix (items x categories)
        agreement_matrix = np.zeros((n_items, n_cats))
        
        for item_idx in range(n_items):
            for ann in annotations:
                cat_idx = cat_to_idx[ann[item_idx]]
                agreement_matrix[item_idx, cat_idx] += 1
        
        # Calculate observed agreement
        p_o = 0
        for i in range(n_items):
            for j in range(n_cats):
                n_ij = agreement_matrix[i, j]
                p_o += n_ij * (n_ij - 1)
        p_o = p_o / (n_items * n_annotators * (n_annotators - 1))
        
        # Calculate expected agreement
        p_e = 0
        for j in range(n_cats):
            p_j = np.sum(agreement_matrix[:, j]) / (n_items * n_annotators)
            p_e += p_j ** 2
        
        # Calculate Fleiss' Kappa
        kappa = (p_o - p_e) / (1 - p_e) if p_e != 1 else 1.0
        
        # Calculate standard error
        se = self._fleiss_kappa_se(agreement_matrix, p_o, p_e, n_items, n_annotators)
        
        # 95% confidence intervals
        z_score = 1.96
        ci_lower = kappa - z_score * se
        ci_upper = kappa + z_score * se
        
        # Calculate per-category statistics
        category_stats = {}
        for j, cat in enumerate(categories):
            n_j = np.sum(agreement_matrix[:, j])
            prop_j = n_j / (n_items * n_annotators)
            category_stats[cat] = {
                'count': int(n_j),
                'proportion': round(prop_j, 4)
            }
        
        return {
            'kappa': round(kappa, 4),
            'standard_error': round(se, 4),
            'ci_lower': round(ci_lower, 4),
            'ci_upper': round(ci_upper, 4),
            'observed_agreement': round(p_o, 4),
            'expected_agreement': round(p_e, 4),
            'n_items': n_items,
            'n_annotators': n_annotators,
            'categories': categories,
            'category_stats': category_stats,
            'interpretation': self._interpret_kappa(kappa)
        }
    
    def krippendorff_alpha(self, annotations: List[List[Any]], 
                          metric: str = 'nominal',
                          missing_value: Any = None) -> Dict[str, float]:
        """
        Calculate Krippendorff's Alpha for any number of annotators and data types.
        
        Args:
            annotations: List of annotation lists, one per annotator
            metric: Distance metric ('nominal', 'ordinal', 'interval', 'ratio')
            missing_value: Value representing missing data
            
        Returns:
            Dictionary with alpha value and related statistics
        """
        if len(annotations) < 2:
            raise ValueError("Need at least 2 annotators")
        
        # Convert to reliability data format (item x annotator matrix)
        n_annotators = len(annotations)
        n_items = len(annotations[0])
        
        # Create value-annotator pairs, excluding missing values
        pairs = []
        for item_idx in range(n_items):
            item_values = []
            for ann_idx, ann in enumerate(annotations):
                if ann[item_idx] != missing_value:
                    item_values.append((ann[item_idx], ann_idx))
            
            # Create all pairs within this item
            for i in range(len(item_values)):
                for j in range(i + 1, len(item_values)):
                    pairs.append((item_values[i][0], item_values[j][0]))
        
        if not pairs:
            raise ValueError("No valid annotation pairs found")
        
        # Calculate disagreement
        observed_disagreement = self._calculate_disagreement(pairs, metric)
        
        # Calculate expected disagreement (pairable values)
        all_values = []
        for ann in annotations:
            for val in ann:
                if val != missing_value:
                    all_values.append(val)
        
        expected_pairs = []
        for i in range(len(all_values)):
            for j in range(i + 1, len(all_values)):
                expected_pairs.append((all_values[i], all_values[j]))
        
        expected_disagreement = self._calculate_disagreement(expected_pairs, metric)
        
        # Calculate Alpha
        if expected_disagreement == 0:
            alpha = 1.0
        else:
            alpha = 1 - (observed_disagreement / expected_disagreement)
        
        # Bootstrap confidence intervals
        ci_lower, ci_upper = self._bootstrap_alpha_ci(
            annotations, metric, missing_value, n_bootstrap=1000
        )
        
        return {
            'alpha': round(alpha, 4),
            'ci_lower': round(ci_lower, 4),
            'ci_upper': round(ci_upper, 4),
            'observed_disagreement': round(observed_disagreement, 4),
            'expected_disagreement': round(expected_disagreement, 4),
            'n_items': n_items,
            'n_annotators': n_annotators,
            'n_pairs': len(pairs),
            'metric': metric,
            'interpretation': self._interpret_alpha(alpha)
        }
    
    def _get_weight_matrix(self, n_cats: int, weight_type: str) -> np.ndarray:
        """Generate weight matrix for weighted kappa calculations."""
        weights = np.ones((n_cats, n_cats))
        
        if weight_type == 'linear':
            for i in range(n_cats):
                for j in range(n_cats):
                    weights[i, j] = 1 - abs(i - j) / (n_cats - 1)
        elif weight_type == 'quadratic':
            for i in range(n_cats):
                for j in range(n_cats):
                    weights[i, j] = 1 - ((i - j) ** 2) / ((n_cats - 1) ** 2)
        
        return weights
    
    def _cohen_kappa_se(self, confusion_matrix: np.ndarray, p_o: float, 
                       p_e: float, n: int) -> float:
        """Calculate standard error for Cohen's Kappa."""
        # Simplified SE calculation
        se = np.sqrt((p_o * (1 - p_o)) / (n * (1 - p_e) ** 2))
        return se
    
    def _fleiss_kappa_se(self, agreement_matrix: np.ndarray, p_o: float, 
                        p_e: float, n_items: int, n_annotators: int) -> float:
        """Calculate standard error for Fleiss' Kappa."""
        # Simplified SE calculation
        se = np.sqrt((p_o * (1 - p_o)) / (n_items * (1 - p_e) ** 2))
        return se
    
    def _calculate_disagreement(self, pairs: List[Tuple], metric: str) -> float:
        """Calculate disagreement for Krippendorff's Alpha."""
        if not pairs:
            return 0.0
        
        total_disagreement = 0.0
        
        for val1, val2 in pairs:
            if metric == 'nominal':
                disagreement = 0.0 if val1 == val2 else 1.0
            elif metric == 'ordinal':
                # Convert to numeric if needed
                try:
                    v1, v2 = float(val1), float(val2)
                    disagreement = abs(v1 - v2)
                except (ValueError, TypeError):
                    disagreement = 0.0 if val1 == val2 else 1.0
            elif metric in ['interval', 'ratio']:
                try:
                    v1, v2 = float(val1), float(val2)
                    disagreement = (v1 - v2) ** 2
                except (ValueError, TypeError):
                    disagreement = 0.0
            else:
                disagreement = 0.0 if val1 == val2 else 1.0
            
            total_disagreement += disagreement
        
        return total_disagreement / len(pairs)
    
    def _bootstrap_alpha_ci(self, annotations: List[List[Any]], metric: str,
                           missing_value: Any, n_bootstrap: int = 1000,
                           confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate bootstrap confidence intervals for Krippendorff's Alpha."""
        try:
            bootstrap_alphas = []
            n_items = len(annotations[0])
            
            for _ in range(min(n_bootstrap, 100)):  # Limit for performance
                # Resample items with replacement
                indices = np.random.choice(n_items, size=n_items, replace=True)
                resampled_annotations = []
                
                for ann in annotations:
                    resampled_ann = [ann[i] for i in indices]
                    resampled_annotations.append(resampled_ann)
                
                # Calculate alpha for resampled data
                try:
                    alpha_result = self.krippendorff_alpha(
                        resampled_annotations, metric, missing_value
                    )
                    bootstrap_alphas.append(alpha_result['alpha'])
                except:
                    continue
            
            if bootstrap_alphas:
                alpha_range = (1 - confidence) / 2
                ci_lower = np.percentile(bootstrap_alphas, alpha_range * 100)
                ci_upper = np.percentile(bootstrap_alphas, (1 - alpha_range) * 100)
                return ci_lower, ci_upper
            else:
                return -1.0, 1.0
        except:
            return -1.0, 1.0
    
    def _interpret_kappa(self, kappa: float) -> str:
        """Interpret Kappa values using Landis & Koch guidelines."""
        if kappa < 0:
            return "Poor (less than chance)"
        elif kappa < 0.20:
            return "Slight"
        elif kappa < 0.40:
            return "Fair"
        elif kappa < 0.60:
            return "Moderate"
        elif kappa < 0.80:
            return "Substantial"
        else:
            return "Almost Perfect"
    
    def _interpret_alpha(self, alpha: float) -> str:
        """Interpret Alpha values using Krippendorff's guidelines."""
        if alpha < 0:
            return "Poor (systematic disagreement)"
        elif alpha < 0.67:
            return "Low (inadequate for most purposes)"
        elif alpha < 0.80:
            return "Moderate (acceptable for some purposes)"
        else:
            return "High (acceptable for most purposes)"


class AgreementAnalysis:
    """
    High-level class for comprehensive agreement analysis workflows.
    """
    
    def __init__(self):
        self.metrics = AgreementMetrics()
    
    def analyze_dataset(self, annotations: Dict[str, List[Any]], 
                       include_all_metrics: bool = True) -> Dict[str, Any]:
        """
        Perform comprehensive agreement analysis on a dataset.
        
        Args:
            annotations: Dictionary mapping annotator names to annotation lists
            include_all_metrics: Whether to calculate all available metrics
            
        Returns:
            Complete agreement analysis results
        """
        annotator_names = list(annotations.keys())
        annotation_lists = list(annotations.values())
        
        results = {
            'dataset_info': {
                'n_annotators': len(annotator_names),
                'n_items': len(annotation_lists[0]),
                'annotators': annotator_names
            },
            'metrics': {}
        }
        
        # Cohen's Kappa for all pairs if 2+ annotators
        if len(annotation_lists) >= 2:
            results['metrics']['pairwise_cohen_kappa'] = {}
            
            for i in range(len(annotator_names)):
                for j in range(i + 1, len(annotator_names)):
                    pair_name = f"{annotator_names[i]}_vs_{annotator_names[j]}"
                    results['metrics']['pairwise_cohen_kappa'][pair_name] = \
                        self.metrics.cohen_kappa(annotation_lists[i], annotation_lists[j])
        
        if include_all_metrics:
            # Fleiss' Kappa for multiple annotators
            if len(annotation_lists) >= 2:
                results['metrics']['fleiss_kappa'] = \
                    self.metrics.fleiss_kappa(annotation_lists)
            
            # Krippendorff's Alpha
            if len(annotation_lists) >= 2:
                results['metrics']['krippendorff_alpha'] = \
                    self.metrics.krippendorff_alpha(annotation_lists)
        
        # Overall assessment
        results['summary'] = self._generate_summary(results['metrics'])
        
        return results
    
    def _generate_summary(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall assessment summary."""
        summary = {
            'overall_quality': 'Unknown',
            'recommendations': [],
            'key_findings': []
        }
        
        # Analyze Fleiss' Kappa if available
        if 'fleiss_kappa' in metrics:
            fleiss = metrics['fleiss_kappa']['kappa']
            summary['key_findings'].append(
                f"Fleiss' Kappa: {fleiss} ({metrics['fleiss_kappa']['interpretation']})"
            )
            
            if fleiss < 0.40:
                summary['recommendations'].append(
                    "Consider additional annotator training or guideline refinement"
                )
            elif fleiss > 0.80:
                summary['recommendations'].append(
                    "Excellent agreement - annotation process appears reliable"
                )
        
        # Analyze Krippendorff's Alpha if available
        if 'krippendorff_alpha' in metrics:
            alpha = metrics['krippendorff_alpha']['alpha']
            summary['key_findings'].append(
                f"Krippendorff's Alpha: {alpha} ({metrics['krippendorff_alpha']['interpretation']})"
            )
            
            if alpha < 0.67:
                summary['recommendations'].append(
                    "Alpha below 0.67 - consider improving annotation guidelines"
                )
        
        # Determine overall quality
        if 'fleiss_kappa' in metrics:
            fleiss = metrics['fleiss_kappa']['kappa']
            if fleiss >= 0.80:
                summary['overall_quality'] = 'Excellent'
            elif fleiss >= 0.60:
                summary['overall_quality'] = 'Good'
            elif fleiss >= 0.40:
                summary['overall_quality'] = 'Moderate'
            else:
                summary['overall_quality'] = 'Poor'
        
        return summary


def calculate_agreement_metrics(annotations: Union[Dict[str, List[Any]], List[List[Any]]], 
                              metric_type: str = 'all') -> Dict[str, Any]:
    """
    Convenience function for calculating agreement metrics.
    
    Args:
        annotations: Annotation data (dict or list of lists)
        metric_type: Type of metric to calculate ('cohen', 'fleiss', 'alpha', 'all')
        
    Returns:
        Agreement metrics results
    """
    if isinstance(annotations, dict):
        analyzer = AgreementAnalysis()
        include_all = metric_type == 'all'
        return analyzer.analyze_dataset(annotations, include_all)
    
    elif isinstance(annotations, list) and len(annotations) == 2:
        metrics = AgreementMetrics()
        if metric_type in ['cohen', 'all']:
            return metrics.cohen_kappa(annotations[0], annotations[1])
    
    else:
        metrics = AgreementMetrics()
        if metric_type == 'fleiss':
            return metrics.fleiss_kappa(annotations)
        elif metric_type == 'alpha':
            return metrics.krippendorff_alpha(annotations)
        elif metric_type == 'all':
            analyzer = AgreementAnalysis()
            ann_dict = {f"annotator_{i}": ann for i, ann in enumerate(annotations)}
            return analyzer.analyze_dataset(ann_dict)
    
    raise ValueError(f"Unsupported combination of annotations type and metric_type: {metric_type}")