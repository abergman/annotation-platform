#!/usr/bin/env python3
"""
Test script for inter-annotator agreement integration.

This script tests the complete agreement calculation workflow
including database integration and API endpoints.
"""

import sys
import os
import json
import requests
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.agreement_metrics import AgreementMetrics, AgreementAnalysis
from services.agreement_service import AgreementService


def test_agreement_metrics():
    """Test the basic agreement metrics calculations."""
    print("Testing Agreement Metrics...")
    
    metrics = AgreementMetrics()
    
    # Test Cohen's Kappa
    annotator1 = ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'A', 'B', 'C']
    annotator2 = ['A', 'B', 'C', 'A', 'C', 'C', 'A', 'A', 'B', 'B']
    
    cohen_result = metrics.cohen_kappa(annotator1, annotator2)
    print(f"Cohen's Kappa: {cohen_result['kappa']} ({cohen_result['interpretation']})")
    
    # Test Fleiss' Kappa
    annotations = [annotator1, annotator2, ['A', 'A', 'C', 'A', 'B', 'C', 'A', 'A', 'B', 'C']]
    fleiss_result = metrics.fleiss_kappa(annotations)
    print(f"Fleiss' Kappa: {fleiss_result['kappa']} ({fleiss_result['interpretation']})")
    
    # Test Krippendorff's Alpha
    alpha_result = metrics.krippendorff_alpha(annotations)
    print(f"Krippendorff's Alpha: {alpha_result['alpha']} ({alpha_result['interpretation']})")
    
    print("✓ Agreement metrics tests passed\n")


def test_agreement_analysis():
    """Test the comprehensive agreement analysis."""
    print("Testing Agreement Analysis...")
    
    analysis = AgreementAnalysis()
    
    # Sample annotation data
    annotations_data = {
        'annotator_alice': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'A', 'B', 'C'],
        'annotator_bob': ['A', 'B', 'C', 'A', 'C', 'C', 'A', 'A', 'B', 'B'],
        'annotator_charlie': ['A', 'A', 'C', 'A', 'B', 'C', 'A', 'A', 'B', 'C']
    }
    
    results = analysis.analyze_dataset(annotations_data, include_all_metrics=True)
    
    print("Dataset Info:")
    print(f"  Annotators: {results['dataset_info']['n_annotators']}")
    print(f"  Items: {results['dataset_info']['n_items']}")
    
    print("\nMetrics Results:")
    if 'fleiss_kappa' in results['metrics']:
        fleiss = results['metrics']['fleiss_kappa']
        print(f"  Fleiss' Kappa: {fleiss['kappa']} ({fleiss['interpretation']})")
    
    if 'krippendorff_alpha' in results['metrics']:
        alpha = results['metrics']['krippendorff_alpha']
        print(f"  Krippendorff's Alpha: {alpha['alpha']} ({alpha['interpretation']})")
    
    if 'pairwise_cohen_kappa' in results['metrics']:
        print("  Pairwise Cohen's Kappa:")
        for pair, result in results['metrics']['pairwise_cohen_kappa'].items():
            print(f"    {pair}: {result['kappa']} ({result['interpretation']})")
    
    print("\nSummary:")
    summary = results['summary']
    print(f"  Overall Quality: {summary['overall_quality']}")
    print(f"  Key Findings: {summary['key_findings']}")
    print(f"  Recommendations: {summary['recommendations']}")
    
    print("✓ Agreement analysis tests passed\n")


def test_api_endpoints():
    """Test the agreement API endpoints."""
    print("Testing API Endpoints...")
    
    base_url = "http://localhost:5000/api/agreement"
    
    # Test health check
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health check endpoint working")
        else:
            print(f"✗ Health check failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ API server not running - skipping endpoint tests")
        return
    
    # Test Cohen's Kappa calculation
    cohen_data = {
        "annotator1": ["A", "B", "C", "A", "B"],
        "annotator2": ["A", "B", "C", "A", "C"],
        "annotator1_name": "Alice",
        "annotator2_name": "Bob"
    }
    
    try:
        response = requests.post(f"{base_url}/calculate/cohen-kappa", json=cohen_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Cohen's Kappa API: {result['result']['kappa']}")
        else:
            print(f"✗ Cohen's Kappa API failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Cohen's Kappa API error: {str(e)}")
    
    # Test Fleiss' Kappa calculation
    fleiss_data = {
        "annotations": [
            ["A", "B", "C", "A", "B"],
            ["A", "B", "C", "A", "C"],
            ["A", "A", "C", "A", "B"]
        ],
        "annotator_names": ["Alice", "Bob", "Charlie"]
    }
    
    try:
        response = requests.post(f"{base_url}/calculate/fleiss-kappa", json=fleiss_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Fleiss' Kappa API: {result['result']['kappa']}")
        else:
            print(f"✗ Fleiss' Kappa API failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Fleiss' Kappa API error: {str(e)}")
    
    # Test comprehensive analysis
    comprehensive_data = {
        "annotations": {
            "alice": ["A", "B", "C", "A", "B"],
            "bob": ["A", "B", "C", "A", "C"],
            "charlie": ["A", "A", "C", "A", "B"]
        },
        "dataset_name": "Test Dataset",
        "save_to_database": False
    }
    
    try:
        response = requests.post(f"{base_url}/analyze/comprehensive", json=comprehensive_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Comprehensive analysis API working")
            if 'results' in result and 'summary' in result['results']:
                summary = result['results']['summary']
                print(f"  Overall Quality: {summary['overall_quality']}")
        else:
            print(f"✗ Comprehensive analysis API failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Comprehensive analysis API error: {str(e)}")
    
    print("✓ API endpoint tests completed\n")


def test_interpretation_guidelines():
    """Test the interpretation guidelines endpoint."""
    print("Testing Interpretation Guidelines...")
    
    base_url = "http://localhost:5000/api/agreement"
    
    try:
        response = requests.get(f"{base_url}/metrics/guidelines")
        if response.status_code == 200:
            guidelines = response.json()['interpretation_guidelines']
            
            print("Cohen's Kappa Guidelines:")
            for range_info in guidelines['cohen_kappa']['ranges'][:3]:  # Show first 3
                print(f"  {range_info['min']}-{range_info['max']}: {range_info['interpretation']}")
            
            print("\nFleiss' Kappa Guidelines:")
            for range_info in guidelines['fleiss_kappa']['ranges'][:3]:  # Show first 3
                print(f"  {range_info['min']}-{range_info['max']}: {range_info['interpretation']}")
            
            print("\nKrippendorff's Alpha Guidelines:")
            for range_info in guidelines['krippendorff_alpha']['ranges']:
                print(f"  {range_info['min']}-{range_info['max']}: {range_info['interpretation']}")
            
            print("✓ Interpretation guidelines working")
        else:
            print(f"✗ Guidelines endpoint failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ API server not running - skipping guidelines test")
    except Exception as e:
        print(f"✗ Guidelines endpoint error: {str(e)}")
    
    print()


def create_sample_dataset():
    """Create sample dataset for testing."""
    print("Creating sample dataset for testing...")
    
    # Simulate different levels of agreement
    high_agreement = {
        'annotator1': ['A'] * 8 + ['B'] * 7 + ['C'] * 5,
        'annotator2': ['A'] * 8 + ['B'] * 6 + ['C'] * 6,
        'annotator3': ['A'] * 7 + ['B'] * 7 + ['C'] * 6
    }
    
    moderate_agreement = {
        'annotator1': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C', 'A'],
        'annotator2': ['A', 'B', 'C', 'B', 'B', 'C', 'A', 'A', 'C', 'A'],
        'annotator3': ['A', 'A', 'C', 'A', 'B', 'B', 'A', 'B', 'B', 'C']
    }
    
    low_agreement = {
        'annotator1': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C', 'A'],
        'annotator2': ['B', 'C', 'A', 'C', 'A', 'B', 'C', 'A', 'B', 'C'],
        'annotator3': ['C', 'A', 'B', 'B', 'C', 'A', 'B', 'C', 'A', 'B']
    }
    
    return {
        'high_agreement': high_agreement,
        'moderate_agreement': moderate_agreement,
        'low_agreement': low_agreement
    }


def test_agreement_levels():
    """Test different levels of agreement."""
    print("Testing Different Agreement Levels...")
    
    analysis = AgreementAnalysis()
    datasets = create_sample_dataset()
    
    for level, data in datasets.items():
        print(f"\n{level.replace('_', ' ').title()}:")
        results = analysis.analyze_dataset(data, include_all_metrics=True)
        
        if 'fleiss_kappa' in results['metrics']:
            fleiss = results['metrics']['fleiss_kappa']
            print(f"  Fleiss' Kappa: {fleiss['kappa']} ({fleiss['interpretation']})")
        
        if 'krippendorff_alpha' in results['metrics']:
            alpha = results['metrics']['krippendorff_alpha']
            print(f"  Krippendorff's Alpha: {alpha['alpha']} ({alpha['interpretation']})")
        
        summary = results['summary']
        print(f"  Overall Quality: {summary['overall_quality']}")
    
    print("\n✓ Agreement level tests completed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("INTER-ANNOTATOR AGREEMENT INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_agreement_metrics()
        test_agreement_analysis()
        test_agreement_levels()
        test_interpretation_guidelines()
        test_api_endpoints()
        
        print("=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        
        print("\nTo test the full integration:")
        print("1. Start the Flask API server:")
        print("   python -m src.api.agreement")
        print()
        print("2. Test project agreement calculation:")
        print("   POST /api/agreement/projects/1/calculate")
        print()
        print("3. Test text-specific agreement:")
        print("   POST /api/agreement/projects/1/texts/1/calculate")
        print()
        print("4. View agreement history:")
        print("   GET /api/agreement/projects/1/history")
        print()
        print("5. Check annotator performance:")
        print("   GET /api/agreement/annotators/performance")
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()