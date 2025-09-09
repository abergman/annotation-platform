# ML/AI Integration and Advanced Export Systems

## Overview
This document specifies the integration with common NLP tools and advanced export formats optimized for machine learning and AI consumption, enabling seamless workflow transitions from annotation to model training.

## 1. Advanced Export Formats

### Database Schema
```sql
CREATE TABLE export_formats (
    id SERIAL PRIMARY KEY,
    format_name VARCHAR(100) NOT NULL UNIQUE,
    format_type VARCHAR(50) NOT NULL CHECK (format_type IN ('json', 'xml', 'csv', 'conll', 'brat', 'spacy', 'transformers', 'jsonl', 'tfrecord', 'arrow')),
    format_schema JSONB NOT NULL, -- JSON Schema defining the output structure
    transformation_rules JSONB DEFAULT '{}', -- Rules for data transformation
    output_structure JSONB DEFAULT '{}', -- Template for output structure
    is_ml_ready BOOLEAN DEFAULT FALSE, -- Optimized for ML consumption
    supports_streaming BOOLEAN DEFAULT FALSE, -- Supports streaming export
    compression_options JSONB DEFAULT '{}', -- Available compression options
    file_extensions TEXT[] DEFAULT ARRAY[]::TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_format_schema CHECK (jsonb_typeof(format_schema) = 'object')
);

CREATE TABLE export_jobs (
    id SERIAL PRIMARY KEY,
    job_uuid UUID DEFAULT gen_random_uuid(),
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requested_by INTEGER NOT NULL REFERENCES users(id),
    export_format_id INTEGER NOT NULL REFERENCES export_formats(id),
    
    -- Export configuration
    export_parameters JSONB DEFAULT '{}', -- Custom parameters for export
    filter_criteria JSONB DEFAULT '{}', -- Filters applied to data
    include_metadata BOOLEAN DEFAULT TRUE,
    include_relations BOOLEAN DEFAULT FALSE,
    include_hierarchies BOOLEAN DEFAULT FALSE,
    
    -- Processing information
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    progress_percentage FLOAT DEFAULT 0.0,
    error_message TEXT,
    
    -- Output information
    output_file_path TEXT,
    output_file_size BIGINT,
    output_format_version VARCHAR(20),
    compression_used VARCHAR(20),
    download_count INTEGER DEFAULT 0,
    
    -- Lifecycle management
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days'),
    completed_at TIMESTAMP,
    processing_time_ms INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ml_export_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    framework VARCHAR(50) NOT NULL CHECK (framework IN ('pytorch', 'tensorflow', 'huggingface', 'spacy', 'scikit_learn', 'custom')),
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('token_classification', 'sequence_classification', 'relation_extraction', 'question_answering', 'language_modeling')),
    
    -- Template configuration
    data_format JSONB NOT NULL, -- How annotations are transformed for this framework
    label_encoding JSONB DEFAULT '{}', -- Label encoding scheme (BIO, BILOU, etc.)
    preprocessing_steps JSONB DEFAULT '[]', -- Steps to apply before export
    validation_schema JSONB DEFAULT '{}', -- Schema to validate export data
    
    -- Framework-specific settings
    framework_config JSONB DEFAULT '{}',
    example_usage TEXT, -- Code example showing how to use exported data
    
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INTEGER DEFAULT 0,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_template_per_framework_task UNIQUE(template_name, framework, task_type)
);

-- Indexes
CREATE INDEX idx_export_jobs_status ON export_jobs(status);
CREATE INDEX idx_export_jobs_project ON export_jobs(project_id);
CREATE INDEX idx_export_jobs_expires_at ON export_jobs(expires_at);
CREATE INDEX idx_ml_export_templates_framework ON ml_export_templates(framework);
CREATE INDEX idx_ml_export_templates_task_type ON ml_export_templates(task_type);
```

### Export Format Implementations
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Iterator, Optional, Union
import json
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path
import gzip
import pickle
from dataclasses import dataclass, asdict
import io

@dataclass
class AnnotationData:
    """Standardized annotation data structure."""
    id: int
    text_id: int
    text_content: str
    start_char: int
    end_char: int
    label: str
    selected_text: str
    annotator_id: int
    confidence_score: float
    attributes: Dict[str, Any] = None
    relations: List[Dict[str, Any]] = None
    created_at: str = None
    metadata: Dict[str, Any] = None

class ExportFormatBase(ABC):
    """Base class for export format implementations."""
    
    def __init__(self, format_config: Dict[str, Any] = None):
        self.config = format_config or {}
        self.compression = self.config.get('compression', None)
        self.batch_size = self.config.get('batch_size', 1000)
    
    @abstractmethod
    def export_data(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export annotations to the target format."""
        pass
    
    def _apply_compression(self, data: Union[str, bytes], output_path: str) -> str:
        """Apply compression if specified."""
        if not self.compression:
            return output_path
        
        if self.compression == 'gzip':
            compressed_path = f"{output_path}.gz"
            with gzip.open(compressed_path, 'wb' if isinstance(data, bytes) else 'wt') as f:
                f.write(data)
            return compressed_path
        
        return output_path

class CoNLLExportFormat(ExportFormatBase):
    """CoNLL format export for token classification tasks."""
    
    def __init__(self, format_config: Dict[str, Any] = None):
        super().__init__(format_config)
        self.label_scheme = self.config.get('label_scheme', 'BIO')  # BIO, BILOU, IO
        self.include_pos = self.config.get('include_pos', False)
        self.include_lemma = self.config.get('include_lemma', False)
    
    def export_data(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export to CoNLL format."""
        
        # Group annotations by text
        text_groups = {}
        for ann in annotations:
            if ann.text_id not in text_groups:
                text_groups[ann.text_id] = {
                    'text_content': ann.text_content,
                    'annotations': []
                }
            text_groups[ann.text_id]['annotations'].append(ann)
        
        conll_lines = []
        total_tokens = 0
        total_entities = 0
        
        for text_id, text_data in text_groups.items():
            # Tokenize text (simplified - in practice would use spaCy or similar)
            tokens = self._tokenize_text(text_data['text_content'])
            
            # Create label sequence
            labels = self._create_label_sequence(
                tokens, text_data['annotations'], text_data['text_content']
            )
            
            # Generate CoNLL lines
            for token, label in zip(tokens, labels):
                line_parts = [token['text'], label]
                
                if self.include_pos:
                    line_parts.append(token.get('pos', 'UNK'))
                if self.include_lemma:
                    line_parts.append(token.get('lemma', token['text']))
                
                conll_lines.append('\t'.join(line_parts))
                total_tokens += 1
            
            # Add empty line between texts
            conll_lines.append('')
            total_entities += len([ann for ann in text_data['annotations']])
        
        # Write to file
        output_content = '\n'.join(conll_lines)
        final_path = self._apply_compression(output_content, output_path)
        
        if not final_path.endswith('.gz'):
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
        
        return {
            'format': 'conll',
            'total_texts': len(text_groups),
            'total_tokens': total_tokens,
            'total_entities': total_entities,
            'label_scheme': self.label_scheme,
            'file_path': final_path,
            'file_size': len(output_content.encode('utf-8'))
        }
    
    def _tokenize_text(self, text: str) -> List[Dict[str, Any]]:
        """Simple tokenization - replace with spaCy in production."""
        import re
        
        tokens = []
        for match in re.finditer(r'\S+', text):
            tokens.append({
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
                'pos': 'UNK',  # Would be filled by NLP pipeline
                'lemma': match.group().lower()
            })
        return tokens
    
    def _create_label_sequence(
        self, 
        tokens: List[Dict[str, Any]], 
        annotations: List[AnnotationData],
        text_content: str
    ) -> List[str]:
        """Create BIO/BILOU label sequence for tokens."""
        
        labels = ['O'] * len(tokens)
        
        for ann in annotations:
            # Find tokens that overlap with annotation
            overlapping_tokens = []
            for i, token in enumerate(tokens):
                if (token['start'] < ann.end_char and token['end'] > ann.start_char):
                    overlapping_tokens.append(i)
            
            if overlapping_tokens:
                if self.label_scheme == 'BIO':
                    labels[overlapping_tokens[0]] = f'B-{ann.label}'
                    for i in overlapping_tokens[1:]:
                        labels[i] = f'I-{ann.label}'
                
                elif self.label_scheme == 'BILOU':
                    if len(overlapping_tokens) == 1:
                        labels[overlapping_tokens[0]] = f'U-{ann.label}'
                    else:
                        labels[overlapping_tokens[0]] = f'B-{ann.label}'
                        for i in overlapping_tokens[1:-1]:
                            labels[i] = f'I-{ann.label}'
                        labels[overlapping_tokens[-1]] = f'L-{ann.label}'
                
                elif self.label_scheme == 'IO':
                    for i in overlapping_tokens:
                        labels[i] = f'I-{ann.label}'
        
        return labels

class SpaCyExportFormat(ExportFormatBase):
    """spaCy format export for training spaCy models."""
    
    def export_data(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export to spaCy training format."""
        
        training_data = []
        
        # Group by text
        text_groups = {}
        for ann in annotations:
            if ann.text_id not in text_groups:
                text_groups[ann.text_id] = {
                    'text': ann.text_content,
                    'entities': []
                }
            
            text_groups[ann.text_id]['entities'].append({
                'start': ann.start_char,
                'end': ann.end_char,
                'label': ann.label
            })
        
        # Convert to spaCy format
        for text_id, text_data in text_groups.items():
            entities = [(ent['start'], ent['end'], ent['label']) 
                       for ent in text_data['entities']]
            
            training_data.append((text_data['text'], {'entities': entities}))
        
        # Save as pickle or JSON
        if output_path.endswith('.pkl'):
            with open(output_path, 'wb') as f:
                pickle.dump(training_data, f)
        else:
            # Convert to JSON-serializable format
            json_data = []
            for text, annotations in training_data:
                json_data.append({
                    'text': text,
                    'entities': annotations['entities']
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return {
            'format': 'spacy',
            'total_examples': len(training_data),
            'file_path': output_path
        }

class HuggingFaceExportFormat(ExportFormatBase):
    """Hugging Face datasets format export."""
    
    def export_data(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export to Hugging Face datasets format."""
        
        # Determine task type from config
        task_type = self.config.get('task_type', 'token_classification')
        
        if task_type == 'token_classification':
            return self._export_token_classification(annotations, output_path, metadata)
        elif task_type == 'sequence_classification':
            return self._export_sequence_classification(annotations, output_path, metadata)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")
    
    def _export_token_classification(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export for token classification tasks."""
        
        dataset_entries = []
        label_set = set()
        
        # Group by text
        text_groups = {}
        for ann in annotations:
            if ann.text_id not in text_groups:
                text_groups[ann.text_id] = {
                    'text': ann.text_content,
                    'annotations': []
                }
            text_groups[ann.text_id]['annotations'].append(ann)
            label_set.add(ann.label)
        
        # Create label mapping
        labels = sorted(list(label_set))
        label_to_id = {label: i for i, label in enumerate(['O'] + [f'B-{l}' for l in labels] + [f'I-{l}' for l in labels])}
        id_to_label = {v: k for k, v in label_to_id.items()}
        
        for text_id, text_data in text_groups.items():
            # Tokenize (simplified)
            tokens = text_data['text'].split()  # In practice, use proper tokenizer
            
            # Create labels using BIO scheme
            token_labels = ['O'] * len(tokens)
            
            # Map annotations to tokens (simplified)
            for ann in text_data['annotations']:
                # Find token indices (this is simplified - real implementation would be more robust)
                ann_tokens = ann.selected_text.split()
                if ann_tokens:
                    # Find where these tokens appear in the text
                    for i, token in enumerate(tokens):
                        if token == ann_tokens[0]:
                            token_labels[i] = f'B-{ann.label}'
                            for j in range(1, min(len(ann_tokens), len(tokens) - i)):
                                if i + j < len(tokens):
                                    token_labels[i + j] = f'I-{ann.label}'
                            break
            
            # Convert labels to IDs
            label_ids = [label_to_id.get(label, 0) for label in token_labels]
            
            dataset_entries.append({
                'id': text_id,
                'tokens': tokens,
                'ner_tags': label_ids
            })
        
        # Save as JSONL
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in dataset_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        # Save label mapping
        label_file = output_path.replace('.jsonl', '_labels.json')
        with open(label_file, 'w', encoding='utf-8') as f:
            json.dump({
                'label_to_id': label_to_id,
                'id_to_label': id_to_label
            }, f, indent=2, ensure_ascii=False)
        
        return {
            'format': 'huggingface_datasets',
            'task_type': 'token_classification',
            'total_examples': len(dataset_entries),
            'num_labels': len(label_to_id),
            'files': [output_path, label_file]
        }

class RelationExtractionExportFormat(ExportFormatBase):
    """Export format for relation extraction tasks."""
    
    def export_data(
        self, 
        annotations: List[AnnotationData], 
        output_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export relation extraction data."""
        
        relation_data = []
        
        # Group by text
        text_groups = {}
        for ann in annotations:
            if ann.text_id not in text_groups:
                text_groups[ann.text_id] = {
                    'text': ann.text_content,
                    'entities': [],
                    'relations': []
                }
            
            # Add entity
            text_groups[ann.text_id]['entities'].append({
                'id': ann.id,
                'start': ann.start_char,
                'end': ann.end_char,
                'text': ann.selected_text,
                'label': ann.label
            })
            
            # Add relations if present
            if ann.relations:
                text_groups[ann.text_id]['relations'].extend(ann.relations)
        
        # Convert to relation extraction format
        for text_id, text_data in text_groups.items():
            example = {
                'text': text_data['text'],
                'entities': text_data['entities'],
                'relations': []
            }
            
            # Process relations
            for relation in text_data['relations']:
                example['relations'].append({
                    'head': relation.get('source_annotation_id'),
                    'tail': relation.get('target_annotation_id'),
                    'relation': relation.get('relation_type'),
                    'confidence': relation.get('confidence_score', 1.0)
                })
            
            relation_data.append(example)
        
        # Save data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(relation_data, f, indent=2, ensure_ascii=False)
        
        return {
            'format': 'relation_extraction',
            'total_examples': len(relation_data),
            'file_path': output_path
        }

class ExportFormatFactory:
    """Factory for creating export format instances."""
    
    FORMATS = {
        'conll': CoNLLExportFormat,
        'spacy': SpaCyExportFormat,
        'huggingface': HuggingFaceExportFormat,
        'relation_extraction': RelationExtractionExportFormat,
    }
    
    @classmethod
    def create_exporter(
        self, 
        format_type: str, 
        config: Dict[str, Any] = None
    ) -> ExportFormatBase:
        """Create an export format instance."""
        
        if format_type not in self.FORMATS:
            raise ValueError(f"Unsupported export format: {format_type}")
        
        return self.FORMATS[format_type](config)

class AsyncExportProcessor:
    """Asynchronous export processing with progress tracking."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def process_export_job(self, job_id: int) -> Dict[str, Any]:
        """Process an export job asynchronously."""
        
        job = self.db.query(ExportJob).filter(ExportJob.id == job_id).first()
        if not job:
            raise ValueError(f"Export job {job_id} not found")
        
        try:
            # Update status to processing
            job.status = 'processing'
            job.progress_percentage = 0.0
            self.db.commit()
            
            # Get annotations to export
            annotations = await self._get_annotations_for_export(job)
            
            # Update progress
            job.progress_percentage = 25.0
            self.db.commit()
            
            # Get export format configuration
            export_format = self.db.query(ExportFormat).filter(
                ExportFormat.id == job.export_format_id
            ).first()
            
            # Create exporter
            exporter = ExportFormatFactory.create_exporter(
                format_type=export_format.format_type,
                config={
                    **export_format.transformation_rules,
                    **job.export_parameters
                }
            )
            
            # Update progress
            job.progress_percentage = 50.0
            self.db.commit()
            
            # Perform export
            output_path = f"exports/{job.job_uuid}.{export_format.format_type}"
            export_result = exporter.export_data(
                annotations=annotations,
                output_path=output_path,
                metadata={
                    'project_id': job.project_id,
                    'export_date': datetime.utcnow().isoformat(),
                    'requested_by': job.requested_by
                }
            )
            
            # Update job with results
            job.status = 'completed'
            job.progress_percentage = 100.0
            job.output_file_path = export_result['file_path']
            job.output_file_size = export_result.get('file_size', 0)
            job.completed_at = datetime.utcnow()
            
            self.db.commit()
            
            return export_result
            
        except Exception as e:
            # Update job with error
            job.status = 'failed'
            job.error_message = str(e)
            self.db.commit()
            raise
    
    async def _get_annotations_for_export(self, job: 'ExportJob') -> List[AnnotationData]:
        """Get annotations for export based on job configuration."""
        
        # Build query based on filter criteria
        query = self.db.query(Annotation).join(Text).filter(
            Text.project_id == job.project_id
        )
        
        # Apply filters
        if job.filter_criteria:
            filters = job.filter_criteria
            
            if 'text_ids' in filters:
                query = query.filter(Annotation.text_id.in_(filters['text_ids']))
            
            if 'label_ids' in filters:
                query = query.filter(Annotation.label_id.in_(filters['label_ids']))
            
            if 'annotator_ids' in filters:
                query = query.filter(Annotation.annotator_id.in_(filters['annotator_ids']))
            
            if 'date_from' in filters:
                query = query.filter(Annotation.created_at >= filters['date_from'])
            
            if 'date_to' in filters:
                query = query.filter(Annotation.created_at <= filters['date_to'])
        
        # Execute query and convert to AnnotationData
        annotations = []
        for ann in query.all():
            annotation_data = AnnotationData(
                id=ann.id,
                text_id=ann.text_id,
                text_content=ann.text.content,
                start_char=ann.start_char,
                end_char=ann.end_char,
                label=ann.label.name,
                selected_text=ann.selected_text,
                annotator_id=ann.annotator_id,
                confidence_score=ann.confidence_score,
                attributes=ann.metadata if job.include_metadata else None,
                created_at=ann.created_at.isoformat(),
                metadata=ann.metadata if job.include_metadata else None
            )
            
            # Add relations if requested
            if job.include_relations:
                relations = self.db.query(Relation).filter(
                    or_(
                        Relation.source_annotation_id == ann.id,
                        Relation.target_annotation_id == ann.id
                    )
                ).all()
                
                annotation_data.relations = [
                    {
                        'source_annotation_id': rel.source_annotation_id,
                        'target_annotation_id': rel.target_annotation_id,
                        'relation_type': rel.relation_type,
                        'confidence_score': rel.confidence_score
                    }
                    for rel in relations
                ]
            
            annotations.append(annotation_data)
        
        return annotations
```

### API Endpoints for Export
```python
@router.post("/export/create-job", response_model=ExportJobResponse)
async def create_export_job(
    export_request: ExportJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks
):
    """Create a new export job."""
    
    # Validate project access
    project = db.query(Project).filter(Project.id == export_request.project_id).first()
    if not project or not await check_project_access(project, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate export format
    export_format = db.query(ExportFormat).filter(
        ExportFormat.id == export_request.export_format_id
    ).first()
    if not export_format:
        raise HTTPException(status_code=404, detail="Export format not found")
    
    # Create export job
    export_job = ExportJob(
        project_id=export_request.project_id,
        requested_by=current_user.id,
        export_format_id=export_request.export_format_id,
        export_parameters=export_request.export_parameters or {},
        filter_criteria=export_request.filter_criteria or {},
        include_metadata=export_request.include_metadata,
        include_relations=export_request.include_relations,
        include_hierarchies=export_request.include_hierarchies
    )
    
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    
    # Start background processing
    background_tasks.add_task(process_export_job_task, export_job.id)
    
    return ExportJobResponse(**export_job.__dict__)

@router.get("/export/formats", response_model=List[ExportFormatResponse])
async def list_export_formats(
    framework: Optional[str] = None,
    task_type: Optional[str] = None,
    ml_ready: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List available export formats."""
    
    query = db.query(ExportFormat)
    
    if framework:
        # Filter by ML templates
        query = query.join(MLExportTemplate).filter(
            MLExportTemplate.framework == framework
        )
    
    if task_type:
        query = query.join(MLExportTemplate).filter(
            MLExportTemplate.task_type == task_type
        )
    
    if ml_ready is not None:
        query = query.filter(ExportFormat.is_ml_ready == ml_ready)
    
    formats = query.all()
    return [ExportFormatResponse(**fmt.__dict__) for fmt in formats]

@router.get("/export/templates/ml", response_model=List[MLExportTemplateResponse])
async def list_ml_export_templates(
    framework: Optional[str] = None,
    task_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List ML export templates."""
    
    query = db.query(MLExportTemplate).filter(MLExportTemplate.is_active == True)
    
    if framework:
        query = query.filter(MLExportTemplate.framework == framework)
    
    if task_type:
        query = query.filter(MLExportTemplate.task_type == task_type)
    
    templates = query.all()
    return [MLExportTemplateResponse(**tmpl.__dict__) for tmpl in templates]

async def process_export_job_task(job_id: int):
    """Background task to process export job."""
    
    db = SessionLocal()
    try:
        processor = AsyncExportProcessor(db)
        result = await processor.process_export_job(job_id)
        print(f"Export job {job_id} completed: {result}")
    except Exception as e:
        print(f"Export job {job_id} failed: {e}")
    finally:
        db.close()
```

This comprehensive ML/AI integration and export system provides seamless workflows from annotation to model training, supporting all major NLP frameworks and machine learning pipelines while maintaining data quality and traceability.