"""
Validation Engine

Comprehensive validation system for annotations with rule-based validation,
quality checks, consistency analysis, and automated validation workflows.
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import func

from src.core.database import engine
from src.models.annotation import Annotation
from src.models.text import Text
from src.models.label import Label
from src.models.user import User
from src.models.project import Project
from src.models.batch_models import BatchValidationRule

logger = logging.getLogger(__name__)


class ValidationType(str, Enum):
    """Types of validation that can be performed."""
    SCHEMA = "schema"
    BUSINESS = "business"
    QUALITY = "quality"
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    INTEGRITY = "integrity"
    PERFORMANCE = "performance"


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Individual validation issue."""
    code: str
    message: str
    severity: ValidationSeverity
    field: Optional[str] = None
    value: Optional[Any] = None
    suggestion: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    metadata: Dict[str, Any]
    validation_time: float
    rules_applied: List[str]


class ValidationEngine:
    """Advanced validation engine for annotation data."""
    
    def __init__(self):
        self.session_factory = sessionmaker(bind=engine)
        self._built_in_rules = self._initialize_built_in_rules()
        self._validation_cache = {}
    
    def _initialize_built_in_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize built-in validation rules."""
        return {
            # Schema validation rules
            "required_fields": {
                "type": ValidationType.SCHEMA,
                "severity": ValidationSeverity.CRITICAL,
                "description": "Check for required fields",
                "fields": ["start_char", "end_char", "selected_text", "text_id", "label_id"]
            },
            "field_types": {
                "type": ValidationType.SCHEMA,
                "severity": ValidationSeverity.ERROR,
                "description": "Validate field data types",
                "rules": {
                    "start_char": int,
                    "end_char": int,
                    "confidence_score": float,
                    "text_id": int,
                    "label_id": int,
                    "annotator_id": int
                }
            },
            
            # Business logic rules
            "span_validity": {
                "type": ValidationType.BUSINESS,
                "severity": ValidationSeverity.ERROR,
                "description": "Validate text span boundaries",
                "min_span_length": 1,
                "max_span_length": 1000
            },
            "confidence_range": {
                "type": ValidationType.BUSINESS,
                "severity": ValidationSeverity.WARNING,
                "description": "Validate confidence score range",
                "min_confidence": 0.0,
                "max_confidence": 1.0
            },
            
            # Quality rules
            "text_quality": {
                "type": ValidationType.QUALITY,
                "severity": ValidationSeverity.WARNING,
                "description": "Check text selection quality",
                "min_word_boundary": True,
                "whitespace_handling": "trim",
                "special_chars_limit": 0.3
            },
            "annotation_completeness": {
                "type": ValidationType.COMPLETENESS,
                "severity": ValidationSeverity.INFO,
                "description": "Check annotation completeness",
                "require_notes": False,
                "require_context": False,
                "min_metadata_fields": 0
            },
            
            # Consistency rules
            "duplicate_detection": {
                "type": ValidationType.CONSISTENCY,
                "severity": ValidationSeverity.WARNING,
                "description": "Detect duplicate annotations",
                "tolerance": 0  # Character tolerance for overlaps
            },
            "label_consistency": {
                "type": ValidationType.CONSISTENCY,
                "severity": ValidationSeverity.WARNING,
                "description": "Check label usage consistency",
                "check_similar_spans": True,
                "similarity_threshold": 0.8
            }
        }
    
    async def validate_annotation(
        self,
        annotation_data: Dict[str, Any],
        validation_types: Optional[List[ValidationType]] = None,
        project_id: Optional[int] = None,
        custom_rules: Optional[List[Dict[str, Any]]] = None
    ) -> ValidationResult:
        """
        Validate a single annotation with comprehensive checks.
        
        Args:
            annotation_data: Annotation data to validate
            validation_types: Types of validation to perform
            project_id: Project ID for context-specific validation
            custom_rules: Additional custom validation rules
            
        Returns:
            ValidationResult with validation outcome and issues
        """
        start_time = datetime.utcnow()
        issues = []
        rules_applied = []
        validation_types = validation_types or list(ValidationType)
        
        try:
            # Schema validation
            if ValidationType.SCHEMA in validation_types:
                schema_issues = await self._validate_schema(annotation_data)
                issues.extend(schema_issues)
                rules_applied.extend(["required_fields", "field_types"])
            
            # Business logic validation
            if ValidationType.BUSINESS in validation_types:
                business_issues = await self._validate_business_logic(annotation_data, project_id)
                issues.extend(business_issues)
                rules_applied.extend(["span_validity", "confidence_range"])
            
            # Quality validation
            if ValidationType.QUALITY in validation_types:
                quality_issues = await self._validate_quality(annotation_data)
                issues.extend(quality_issues)
                rules_applied.extend(["text_quality"])
            
            # Consistency validation
            if ValidationType.CONSISTENCY in validation_types and project_id:
                consistency_issues = await self._validate_consistency(annotation_data, project_id)
                issues.extend(consistency_issues)
                rules_applied.extend(["duplicate_detection", "label_consistency"])
            
            # Completeness validation
            if ValidationType.COMPLETENESS in validation_types:
                completeness_issues = await self._validate_completeness(annotation_data)
                issues.extend(completeness_issues)
                rules_applied.extend(["annotation_completeness"])
            
            # Apply custom rules
            if custom_rules:
                for rule in custom_rules:
                    custom_issues = await self._apply_custom_rule(annotation_data, rule)
                    issues.extend(custom_issues)
                    rules_applied.append(rule.get("name", "custom_rule"))
            
            # Apply project-specific rules
            if project_id:
                project_issues = await self._apply_project_rules(annotation_data, project_id)
                issues.extend(project_issues)
            
            # Calculate validation score
            validation_score = self._calculate_validation_score(issues)
            
            # Determine if valid (no critical or error issues)
            is_valid = not any(
                issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR] 
                for issue in issues
            )
            
            # Calculate validation time
            validation_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ValidationResult(
                is_valid=is_valid,
                score=validation_score,
                issues=issues,
                metadata={
                    "validation_types": [vt.value for vt in validation_types],
                    "project_id": project_id,
                    "custom_rules_count": len(custom_rules) if custom_rules else 0,
                    "total_checks": len(rules_applied)
                },
                validation_time=validation_time,
                rules_applied=rules_applied
            )
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                score=0.0,
                issues=[ValidationIssue(
                    code="validation_error",
                    message=f"Validation engine error: {str(e)}",
                    severity=ValidationSeverity.CRITICAL
                )],
                metadata={"error": str(e)},
                validation_time=(datetime.utcnow() - start_time).total_seconds(),
                rules_applied=rules_applied
            )
    
    async def validate_annotation_by_type(
        self,
        annotation: Annotation,
        validation_type: str
    ) -> ValidationResult:
        """Validate an existing annotation by specific type."""
        annotation_data = {
            "id": annotation.id,
            "start_char": annotation.start_char,
            "end_char": annotation.end_char,
            "selected_text": annotation.selected_text,
            "notes": annotation.notes,
            "confidence_score": annotation.confidence_score,
            "metadata": annotation.metadata,
            "context_before": annotation.context_before,
            "context_after": annotation.context_after,
            "is_validated": annotation.is_validated,
            "text_id": annotation.text_id,
            "annotator_id": annotation.annotator_id,
            "label_id": annotation.label_id
        }
        
        # Get project ID from text relationship
        session = self.session_factory()
        try:
            text = session.query(Text).filter(Text.id == annotation.text_id).first()
            project_id = text.project_id if text else None
        finally:
            session.close()
        
        # Map validation type string to enum
        validation_types = []
        if validation_type == "quality":
            validation_types = [ValidationType.QUALITY, ValidationType.COMPLETENESS]
        elif validation_type == "consistency":
            validation_types = [ValidationType.CONSISTENCY]
        elif validation_type == "completeness":
            validation_types = [ValidationType.COMPLETENESS]
        else:
            validation_types = list(ValidationType)
        
        return await self.validate_annotation(annotation_data, validation_types, project_id)
    
    async def batch_validate_annotations(
        self,
        annotation_ids: List[int],
        validation_types: Optional[List[ValidationType]] = None,
        parallel: bool = True
    ) -> Dict[int, ValidationResult]:
        """Validate multiple annotations in batch."""
        results = {}
        session = self.session_factory()
        
        try:
            # Get annotations with related data
            annotations = session.query(Annotation).filter(
                Annotation.id.in_(annotation_ids)
            ).all()
            
            if parallel:
                # TODO: Implement parallel validation using asyncio
                for annotation in annotations:
                    result = await self.validate_annotation_by_type(annotation, "quality")
                    results[annotation.id] = result
            else:
                for annotation in annotations:
                    result = await self.validate_annotation_by_type(annotation, "quality")
                    results[annotation.id] = result
            
            return results
            
        finally:
            session.close()
    
    async def _validate_schema(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate data schema and required fields."""
        issues = []
        required_rule = self._built_in_rules["required_fields"]
        type_rule = self._built_in_rules["field_types"]
        
        # Check required fields
        for field in required_rule["fields"]:
            if field not in data or data[field] is None:
                issues.append(ValidationIssue(
                    code="missing_required_field",
                    message=f"Required field '{field}' is missing or null",
                    severity=ValidationSeverity.CRITICAL,
                    field=field,
                    suggestion=f"Provide a valid value for field '{field}'"
                ))
        
        # Check field types
        for field, expected_type in type_rule["rules"].items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    issues.append(ValidationIssue(
                        code="invalid_field_type",
                        message=f"Field '{field}' should be of type {expected_type.__name__}",
                        severity=ValidationSeverity.ERROR,
                        field=field,
                        value=data[field],
                        suggestion=f"Convert '{field}' to {expected_type.__name__}"
                    ))
        
        return issues
    
    async def _validate_business_logic(
        self, 
        data: Dict[str, Any], 
        project_id: Optional[int]
    ) -> List[ValidationIssue]:
        """Validate business logic rules."""
        issues = []
        
        # Validate span boundaries
        if "start_char" in data and "end_char" in data:
            start_char = data["start_char"]
            end_char = data["end_char"]
            
            if start_char >= end_char:
                issues.append(ValidationIssue(
                    code="invalid_span",
                    message="Start character position must be less than end character position",
                    severity=ValidationSeverity.ERROR,
                    context={"start_char": start_char, "end_char": end_char},
                    suggestion="Ensure start_char < end_char"
                ))
            
            span_length = end_char - start_char
            span_rule = self._built_in_rules["span_validity"]
            
            if span_length < span_rule["min_span_length"]:
                issues.append(ValidationIssue(
                    code="span_too_short",
                    message=f"Span length ({span_length}) is below minimum ({span_rule['min_span_length']})",
                    severity=ValidationSeverity.WARNING,
                    context={"span_length": span_length},
                    suggestion="Select a longer text span"
                ))
            
            if span_length > span_rule["max_span_length"]:
                issues.append(ValidationIssue(
                    code="span_too_long",
                    message=f"Span length ({span_length}) exceeds maximum ({span_rule['max_span_length']})",
                    severity=ValidationSeverity.WARNING,
                    context={"span_length": span_length},
                    suggestion="Select a shorter text span"
                ))
        
        # Validate confidence score
        if "confidence_score" in data:
            confidence = data["confidence_score"]
            confidence_rule = self._built_in_rules["confidence_range"]
            
            if not (confidence_rule["min_confidence"] <= confidence <= confidence_rule["max_confidence"]):
                issues.append(ValidationIssue(
                    code="invalid_confidence",
                    message=f"Confidence score ({confidence}) must be between {confidence_rule['min_confidence']} and {confidence_rule['max_confidence']}",
                    severity=ValidationSeverity.WARNING,
                    field="confidence_score",
                    value=confidence,
                    suggestion="Set confidence score between 0.0 and 1.0"
                ))
        
        # Validate foreign key references
        if project_id:
            session = self.session_factory()
            try:
                # Check if text exists in project
                if "text_id" in data:
                    text_exists = session.query(Text).filter(
                        Text.id == data["text_id"],
                        Text.project_id == project_id
                    ).first() is not None
                    
                    if not text_exists:
                        issues.append(ValidationIssue(
                            code="invalid_text_reference",
                            message=f"Text ID {data['text_id']} does not exist in project {project_id}",
                            severity=ValidationSeverity.ERROR,
                            field="text_id",
                            value=data["text_id"],
                            suggestion="Use a valid text ID from the current project"
                        ))
                
                # Check if label exists in project
                if "label_id" in data:
                    label_exists = session.query(Label).filter(
                        Label.id == data["label_id"],
                        Label.project_id == project_id
                    ).first() is not None
                    
                    if not label_exists:
                        issues.append(ValidationIssue(
                            code="invalid_label_reference",
                            message=f"Label ID {data['label_id']} does not exist in project {project_id}",
                            severity=ValidationSeverity.ERROR,
                            field="label_id",
                            value=data["label_id"],
                            suggestion="Use a valid label ID from the current project"
                        ))
                        
            finally:
                session.close()
        
        return issues
    
    async def _validate_quality(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate annotation quality."""
        issues = []
        quality_rule = self._built_in_rules["text_quality"]
        
        if "selected_text" in data:
            selected_text = data["selected_text"]
            
            # Check for leading/trailing whitespace
            if selected_text != selected_text.strip():
                issues.append(ValidationIssue(
                    code="whitespace_in_selection",
                    message="Selected text contains leading or trailing whitespace",
                    severity=ValidationSeverity.WARNING,
                    field="selected_text",
                    suggestion="Trim whitespace from text selection"
                ))
            
            # Check for excessive special characters
            special_char_count = len(re.findall(r'[^\w\s]', selected_text))
            total_chars = len(selected_text)
            
            if total_chars > 0:
                special_char_ratio = special_char_count / total_chars
                if special_char_ratio > quality_rule["special_chars_limit"]:
                    issues.append(ValidationIssue(
                        code="excessive_special_chars",
                        message=f"Selected text has high ratio of special characters ({special_char_ratio:.2f})",
                        severity=ValidationSeverity.WARNING,
                        field="selected_text",
                        context={"special_char_ratio": special_char_ratio},
                        suggestion="Consider refining text selection to include more meaningful content"
                    ))
            
            # Check for word boundaries if required
            if quality_rule["min_word_boundary"]:
                words = selected_text.split()
                if len(words) == 0:
                    issues.append(ValidationIssue(
                        code="no_words_selected",
                        message="Selected text contains no complete words",
                        severity=ValidationSeverity.WARNING,
                        field="selected_text",
                        suggestion="Select text that includes at least one complete word"
                    ))
        
        return issues
    
    async def _validate_consistency(
        self, 
        data: Dict[str, Any], 
        project_id: int
    ) -> List[ValidationIssue]:
        """Validate annotation consistency within project."""
        issues = []
        session = self.session_factory()
        
        try:
            # Check for duplicate annotations
            if all(k in data for k in ["text_id", "start_char", "end_char"]):
                existing = session.query(Annotation).filter(
                    Annotation.text_id == data["text_id"],
                    Annotation.start_char == data["start_char"],
                    Annotation.end_char == data["end_char"]
                )
                
                # Exclude current annotation if this is an update
                if "id" in data:
                    existing = existing.filter(Annotation.id != data["id"])
                
                duplicate_count = existing.count()
                if duplicate_count > 0:
                    issues.append(ValidationIssue(
                        code="duplicate_annotation",
                        message=f"Found {duplicate_count} duplicate annotation(s) with same span",
                        severity=ValidationSeverity.WARNING,
                        context={
                            "text_id": data["text_id"],
                            "start_char": data["start_char"],
                            "end_char": data["end_char"],
                            "duplicate_count": duplicate_count
                        },
                        suggestion="Check if this annotation already exists or modify the span"
                    ))
            
            # Check label consistency for similar text spans
            if "selected_text" in data and "label_id" in data:
                similar_annotations = session.query(Annotation).join(Text).filter(
                    Text.project_id == project_id,
                    Annotation.selected_text == data["selected_text"],
                    Annotation.label_id != data["label_id"]
                ).limit(5).all()
                
                if similar_annotations:
                    conflicting_labels = [ann.label.name for ann in similar_annotations if ann.label]
                    issues.append(ValidationIssue(
                        code="inconsistent_labeling",
                        message=f"Similar text spans have different labels: {', '.join(conflicting_labels)}",
                        severity=ValidationSeverity.INFO,
                        context={
                            "selected_text": data["selected_text"],
                            "conflicting_labels": conflicting_labels
                        },
                        suggestion="Review labeling consistency for similar text spans"
                    ))
                    
        finally:
            session.close()
        
        return issues
    
    async def _validate_completeness(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate annotation completeness."""
        issues = []
        completeness_rule = self._built_in_rules["annotation_completeness"]
        
        # Check for optional but recommended fields
        if completeness_rule["require_notes"] and not data.get("notes"):
            issues.append(ValidationIssue(
                code="missing_notes",
                message="Annotation notes are recommended for quality documentation",
                severity=ValidationSeverity.INFO,
                field="notes",
                suggestion="Add notes to explain the annotation reasoning"
            ))
        
        if completeness_rule["require_context"]:
            if not data.get("context_before") or not data.get("context_after"):
                issues.append(ValidationIssue(
                    code="missing_context",
                    message="Context information is missing",
                    severity=ValidationSeverity.INFO,
                    suggestion="Include context before and after the annotation"
                ))
        
        # Check metadata completeness
        metadata = data.get("metadata", {})
        if len(metadata) < completeness_rule["min_metadata_fields"]:
            issues.append(ValidationIssue(
                code="insufficient_metadata",
                message=f"Metadata should have at least {completeness_rule['min_metadata_fields']} fields",
                severity=ValidationSeverity.INFO,
                field="metadata",
                suggestion="Add relevant metadata to enrich the annotation"
            ))
        
        return issues
    
    async def _apply_custom_rule(
        self, 
        data: Dict[str, Any], 
        rule: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Apply a custom validation rule."""
        issues = []
        
        try:
            rule_type = rule.get("type", "custom")
            rule_function = rule.get("function")
            
            if rule_function and callable(rule_function):
                custom_issues = await rule_function(data)
                issues.extend(custom_issues)
            elif "conditions" in rule:
                # Simple condition-based validation
                for condition in rule["conditions"]:
                    field = condition.get("field")
                    operator = condition.get("operator")
                    value = condition.get("value")
                    
                    if field in data:
                        field_value = data[field]
                        
                        if operator == "equals" and field_value != value:
                            issues.append(ValidationIssue(
                                code="custom_rule_violation",
                                message=condition.get("message", f"Field {field} must equal {value}"),
                                severity=ValidationSeverity(rule.get("severity", "warning")),
                                field=field,
                                value=field_value
                            ))
                        # Add more operators as needed
                        
        except Exception as e:
            logger.error(f"Error applying custom rule: {str(e)}")
            issues.append(ValidationIssue(
                code="custom_rule_error",
                message=f"Error applying custom rule: {str(e)}",
                severity=ValidationSeverity.ERROR
            ))
        
        return issues
    
    async def _apply_project_rules(
        self, 
        data: Dict[str, Any], 
        project_id: int
    ) -> List[ValidationIssue]:
        """Apply project-specific validation rules."""
        issues = []
        session = self.session_factory()
        
        try:
            # Get project validation rules
            rules = session.query(BatchValidationRule).filter(
                BatchValidationRule.project_id == project_id,
                BatchValidationRule.is_active == True
            ).all()
            
            for rule in rules:
                try:
                    # Apply rule based on its definition
                    rule_issues = await self._execute_validation_rule(data, rule)
                    issues.extend(rule_issues)
                except Exception as e:
                    logger.error(f"Error applying project rule {rule.id}: {str(e)}")
                    
        finally:
            session.close()
        
        return issues
    
    async def _execute_validation_rule(
        self, 
        data: Dict[str, Any], 
        rule: BatchValidationRule
    ) -> List[ValidationIssue]:
        """Execute a specific validation rule."""
        issues = []
        
        try:
            rule_definition = rule.rule_definition
            rule_type = rule.rule_type
            
            # Implement rule execution based on rule_type and definition
            # This would be expanded based on the specific rule format
            
            return issues
            
        except Exception as e:
            logger.error(f"Error executing validation rule {rule.id}: {str(e)}")
            return [ValidationIssue(
                code="rule_execution_error",
                message=f"Error executing validation rule '{rule.name}': {str(e)}",
                severity=ValidationSeverity.ERROR
            )]
    
    def _calculate_validation_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall validation score based on issues."""
        if not issues:
            return 1.0
        
        # Weight issues by severity
        severity_weights = {
            ValidationSeverity.CRITICAL: -1.0,
            ValidationSeverity.ERROR: -0.5,
            ValidationSeverity.WARNING: -0.2,
            ValidationSeverity.INFO: -0.1
        }
        
        total_penalty = 0.0
        for issue in issues:
            total_penalty += severity_weights.get(issue.severity, -0.1)
        
        # Calculate score (0.0 to 1.0)
        score = max(0.0, 1.0 + total_penalty)
        return min(1.0, score)
    
    def get_validation_statistics(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """Get validation statistics for a project or overall system."""
        session = self.session_factory()
        
        try:
            # This would implement statistics gathering
            # For now, return basic structure
            return {
                "total_validations": 0,
                "avg_validation_score": 0.0,
                "common_issues": [],
                "validation_trends": {}
            }
        finally:
            session.close()