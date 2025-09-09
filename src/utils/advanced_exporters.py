"""
Advanced Export Utilities for Academic NLP/ML Research Formats

Implements exporters for various academic annotation formats commonly used
in NLP research and ML training pipelines.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from io import StringIO, BytesIO
from datetime import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict, OrderedDict
import zipfile
import os


class CoNLLUExporter:
    """CoNLL-U format exporter for Universal Dependencies."""
    
    def __init__(self):
        self.sent_id = 1
        
    def export_annotations_to_conllu(
        self,
        annotations: List,
        include_metadata: bool = True,
        tokenize_method: str = "whitespace"
    ) -> bytes:
        """
        Export annotations to CoNLL-U format.
        
        Args:
            annotations: List of annotation objects
            include_metadata: Include metadata in comments
            tokenize_method: Method for tokenization ('whitespace', 'simple')
        """
        output = StringIO()
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text  # Get text object
            text_content = text_obj.content
            
            if include_metadata:
                output.write(f"# sent_id = {self.sent_id}\n")
                output.write(f"# text = {text_content[:100]}{'...' if len(text_content) > 100 else ''}\n")
                output.write(f"# text_id = {text_id}\n")
                output.write(f"# project = {text_obj.project.name}\n")
                output.write(f"# annotations_count = {len(text_anns)}\n")
            
            # Simple tokenization
            tokens = self._tokenize_text(text_content, method=tokenize_method)
            
            # Create token-annotation mapping
            token_labels = self._map_annotations_to_tokens(tokens, text_anns, text_content)
            
            # Write CoNLL-U format
            for i, (token, start, end) in enumerate(tokens, 1):
                label = token_labels.get(i, 'O')
                lemma = token.lower()  # Simple lemmatization
                upos = self._get_simple_pos(token)
                
                # CoNLL-U columns: ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC
                row = [
                    str(i),           # ID
                    token,            # FORM
                    lemma,            # LEMMA
                    upos,             # UPOS
                    '_',              # XPOS
                    '_',              # FEATS
                    '_',              # HEAD
                    '_',              # DEPREL
                    '_',              # DEPS
                    f"NER={label}"    # MISC (our NER label)
                ]
                
                output.write('\t'.join(row) + '\n')
            
            output.write('\n')  # Empty line between sentences
            self.sent_id += 1
        
        return output.getvalue().encode('utf-8')
    
    def _tokenize_text(self, text: str, method: str = "whitespace") -> List[Tuple[str, int, int]]:
        """Simple tokenization with character positions."""
        if method == "whitespace":
            tokens = []
            start = 0
            for match in re.finditer(r'\S+', text):
                token = match.group()
                tokens.append((token, match.start(), match.end()))
            return tokens
        elif method == "simple":
            # More sophisticated tokenization
            pattern = r'\w+|[^\w\s]'
            tokens = []
            for match in re.finditer(pattern, text):
                token = match.group()
                tokens.append((token, match.start(), match.end()))
            return tokens
        else:
            raise ValueError(f"Unknown tokenization method: {method}")
    
    def _map_annotations_to_tokens(self, tokens, annotations, text):
        """Map annotations to tokens using BIO tagging."""
        token_labels = {}
        
        for ann in annotations:
            label_name = ann.label.name
            start_char = ann.start_char
            end_char = ann.end_char
            
            # Find overlapping tokens
            overlapping_tokens = []
            for i, (token, token_start, token_end) in enumerate(tokens, 1):
                if (token_start < end_char and token_end > start_char):
                    overlapping_tokens.append(i)
            
            # Apply BIO tagging
            for idx, token_id in enumerate(overlapping_tokens):
                if idx == 0:
                    token_labels[token_id] = f"B-{label_name}"
                else:
                    token_labels[token_id] = f"I-{label_name}"
        
        return token_labels
    
    def _get_simple_pos(self, token: str) -> str:
        """Simple POS tagging heuristics."""
        if re.match(r'^\d+$', token):
            return 'NUM'
        elif re.match(r'^[A-Z][a-z]*$', token):
            return 'PROPN'
        elif re.match(r'^[a-z]+$', token):
            return 'NOUN'  # Default to noun
        elif re.match(r'^[^\w\s]$', token):
            return 'PUNCT'
        else:
            return 'X'  # Unknown


class JSONNLPExporter:
    """JSON-NLP format exporter for linguistic annotations."""
    
    def export_annotations_to_json_nlp(
        self,
        annotations: List,
        include_metadata: bool = True,
        version: str = "1.0"
    ) -> bytes:
        """Export annotations to JSON-NLP format."""
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        documents = []
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text
            
            # Tokenize text
            tokens = self._tokenize_with_positions(text_obj.content)
            
            # Create entities from annotations
            entities = []
            for ann in text_anns:
                entity = {
                    "id": f"T{ann.id}",
                    "type": ann.label.name,
                    "start": ann.start_char,
                    "end": ann.end_char,
                    "text": ann.selected_text,
                    "confidence": ann.confidence_score,
                    "annotator": ann.annotator.username,
                    "validated": ann.is_validated == "approved"
                }
                
                if include_metadata and ann.metadata:
                    entity["metadata"] = ann.metadata
                
                entities.append(entity)
            
            # Create document structure
            document = {
                "meta": {
                    "DC.conformsTo": version,
                    "DC.created": datetime.utcnow().isoformat(),
                    "DC.date": text_obj.created_at.isoformat() if text_obj.created_at else None,
                    "DC.source": f"project:{text_obj.project.name}",
                    "DC.language": "en",  # Default to English
                    "document_id": str(text_id),
                    "title": text_obj.title
                },
                "text": text_obj.content,
                "tokens": [
                    {
                        "id": i,
                        "text": token,
                        "start": start,
                        "end": end,
                        "pos": self._get_simple_pos(token)
                    }
                    for i, (token, start, end) in enumerate(tokens)
                ],
                "entities": entities,
                "clauses": [],  # Not implemented in this version
                "sentences": self._detect_sentences(text_obj.content),
                "paragraphs": self._detect_paragraphs(text_obj.content)
            }
            
            if include_metadata:
                document["meta"]["annotation_stats"] = {
                    "total_entities": len(entities),
                    "entity_types": list(set(e["type"] for e in entities)),
                    "annotators": list(set(e["annotator"] for e in entities))
                }
            
            documents.append(document)
        
        result = {
            "meta": {
                "DC.conformsTo": version,
                "DC.created": datetime.utcnow().isoformat(),
                "DC.source": "Text Annotation System",
                "documents": len(documents)
            },
            "documents": documents
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8')
    
    def _tokenize_with_positions(self, text: str) -> List[Tuple[str, int, int]]:
        """Tokenize text preserving character positions."""
        tokens = []
        for match in re.finditer(r'\S+', text):
            tokens.append((match.group(), match.start(), match.end()))
        return tokens
    
    def _get_simple_pos(self, token: str) -> str:
        """Simple POS tagging."""
        if re.match(r'^\d+$', token):
            return 'CD'
        elif re.match(r'^[A-Z][a-z]*$', token):
            return 'NNP'
        elif token.lower() in {'the', 'a', 'an'}:
            return 'DT'
        elif token.lower() in {'is', 'was', 'are', 'were', 'be', 'been', 'being'}:
            return 'VB'
        else:
            return 'NN'
    
    def _detect_sentences(self, text: str) -> List[Dict]:
        """Simple sentence detection."""
        sentences = []
        for i, sent in enumerate(re.split(r'[.!?]+', text)):
            sent = sent.strip()
            if sent:
                start = text.find(sent)
                sentences.append({
                    "id": i,
                    "start": start,
                    "end": start + len(sent),
                    "text": sent
                })
        return sentences
    
    def _detect_paragraphs(self, text: str) -> List[Dict]:
        """Simple paragraph detection."""
        paragraphs = []
        current_pos = 0
        for i, para in enumerate(text.split('\n\n')):
            if para.strip():
                start = current_pos
                end = start + len(para)
                paragraphs.append({
                    "id": i,
                    "start": start,
                    "end": end,
                    "text": para.strip()
                })
            current_pos += len(para) + 2
        return paragraphs


class SpaCyExporter:
    """spaCy format exporter for training custom NLP models."""
    
    def export_annotations_to_spacy(
        self,
        annotations: List,
        format_type: str = "json",  # json or binary
        include_metadata: bool = True
    ) -> bytes:
        """Export annotations to spaCy training format."""
        
        if format_type == "json":
            return self._export_spacy_json(annotations, include_metadata)
        else:
            raise NotImplementedError("Binary spaCy format not implemented")
    
    def _export_spacy_json(self, annotations: List, include_metadata: bool) -> bytes:
        """Export to spaCy JSON format."""
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        training_data = []
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text
            text_content = text_obj.content
            
            # Create entities list in spaCy format
            entities = []
            for ann in text_anns:
                entities.append([
                    ann.start_char,
                    ann.end_char,
                    ann.label.name
                ])
            
            # spaCy training format
            example = {
                "text": text_content,
                "entities": entities
            }
            
            if include_metadata:
                example["meta"] = {
                    "text_id": text_id,
                    "project": text_obj.project.name,
                    "title": text_obj.title,
                    "annotators": list(set(ann.annotator.username for ann in text_anns)),
                    "created_at": text_obj.created_at.isoformat() if text_obj.created_at else None
                }
            
            training_data.append(example)
        
        # Create spaCy training config
        result = {
            "version": "3.4.0",
            "meta": {
                "lang": "en",
                "name": "custom_ner_model",
                "description": "NER model trained from annotation data",
                "created": datetime.utcnow().isoformat(),
                "total_examples": len(training_data)
            },
            "examples": training_data
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8')


class BRATExporter:
    """BRAT standoff format exporter for annotation tool compatibility."""
    
    def export_annotations_to_brat(
        self,
        annotations: List,
        include_metadata: bool = True
    ) -> bytes:
        """Export annotations to BRAT standoff format as ZIP file."""
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            
            for text_id, text_anns in texts_annotations.items():
                text_obj = text_anns[0].text
                filename_base = f"text_{text_id}_{text_obj.title[:20]}"
                filename_base = re.sub(r'[^\w\-_.]', '_', filename_base)
                
                # Write text file (.txt)
                txt_content = text_obj.content
                zipf.writestr(f"{filename_base}.txt", txt_content.encode('utf-8'))
                
                # Write annotation file (.ann)
                ann_content = self._create_brat_annotations(text_anns)
                zipf.writestr(f"{filename_base}.ann", ann_content.encode('utf-8'))
                
                # Write configuration file if metadata requested
                if include_metadata:
                    conf_content = self._create_brat_config(text_anns)
                    zipf.writestr(f"{filename_base}.conf", conf_content.encode('utf-8'))
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    def _create_brat_annotations(self, annotations: List) -> str:
        """Create BRAT annotation format."""
        lines = []
        
        # Text-bound annotations
        for i, ann in enumerate(annotations, 1):
            # T1    Label 0 5    text
            line = f"T{i}\t{ann.label.name} {ann.start_char} {ann.end_char}\t{ann.selected_text}"
            lines.append(line)
            
            # Add notes as comments if available
            if ann.notes:
                lines.append(f"#1\tAnnotatorNotes T{i}\t{ann.notes}")
        
        return '\n'.join(lines)
    
    def _create_brat_config(self, annotations: List) -> str:
        """Create BRAT configuration."""
        # Get unique labels
        labels = set(ann.label.name for ann in annotations)
        
        config_lines = [
            "[entities]",
            ""
        ]
        
        for label in sorted(labels):
            config_lines.append(label)
        
        config_lines.extend([
            "",
            "[relations]",
            "",
            "[events]",
            "",
            "[attributes]"
        ])
        
        return '\n'.join(config_lines)


class HuggingFaceExporter:
    """HuggingFace datasets format exporter for transformer training."""
    
    def export_annotations_to_huggingface(
        self,
        annotations: List,
        format_type: str = "json",  # json or arrow
        split_ratio: Dict[str, float] = None
    ) -> bytes:
        """Export annotations to HuggingFace datasets format."""
        
        if split_ratio is None:
            split_ratio = {"train": 0.8, "validation": 0.1, "test": 0.1}
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        # Create dataset examples
        examples = []
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text
            
            # Tokenize and align labels
            tokens, labels = self._tokenize_and_align_labels(text_obj.content, text_anns)
            
            example = {
                "id": str(text_id),
                "tokens": tokens,
                "ner_tags": labels,
                "text": text_obj.content,
                "meta": {
                    "project": text_obj.project.name,
                    "title": text_obj.title,
                    "text_id": text_id
                }
            }
            
            examples.append(example)
        
        # Split data
        import random
        random.shuffle(examples)
        
        n_train = int(len(examples) * split_ratio["train"])
        n_val = int(len(examples) * split_ratio["validation"])
        
        splits = {
            "train": examples[:n_train],
            "validation": examples[n_train:n_train + n_val],
            "test": examples[n_train + n_val:]
        }
        
        # Create dataset info
        label_names = list(set(
            label for ann in annotations 
            for label in [f"B-{ann.label.name}", f"I-{ann.label.name}"]
        )) + ["O"]
        
        dataset_info = {
            "description": "NER dataset from text annotation system",
            "version": "1.0.0",
            "splits": {split: len(data) for split, data in splits.items()},
            "features": {
                "id": "string",
                "tokens": "list[string]",
                "ner_tags": "list[int]",
                "text": "string",
                "meta": "dict"
            },
            "label_names": label_names,
            "label2id": {label: i for i, label in enumerate(label_names)},
            "id2label": {i: label for i, label in enumerate(label_names)}
        }
        
        result = {
            "dataset_info": dataset_info,
            "splits": {}
        }
        
        # Convert labels to IDs
        label2id = dataset_info["label2id"]
        for split_name, split_data in splits.items():
            processed_data = []
            for example in split_data:
                example_copy = example.copy()
                example_copy["ner_tags"] = [
                    label2id[label] for label in example["ner_tags"]
                ]
                processed_data.append(example_copy)
            result["splits"][split_name] = processed_data
        
        return json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8')
    
    def _tokenize_and_align_labels(self, text: str, annotations: List) -> Tuple[List[str], List[str]]:
        """Tokenize text and align with BIO labels."""
        # Simple whitespace tokenization
        tokens = []
        token_starts = []
        
        current_pos = 0
        for token in text.split():
            token_start = text.find(token, current_pos)
            tokens.append(token)
            token_starts.append(token_start)
            current_pos = token_start + len(token)
        
        # Initialize labels
        labels = ["O"] * len(tokens)
        
        # Apply BIO tagging
        for ann in annotations:
            label_name = ann.label.name
            start_char = ann.start_char
            end_char = ann.end_char
            
            # Find overlapping tokens
            first_token = True
            for i, token_start in enumerate(token_starts):
                token_end = token_start + len(tokens[i])
                
                if token_start < end_char and token_end > start_char:
                    if first_token:
                        labels[i] = f"B-{label_name}"
                        first_token = False
                    else:
                        labels[i] = f"I-{label_name}"
        
        return tokens, labels


class BIOBILOUExporter:
    """Bio/BILOU tagged sequence format exporter."""
    
    def export_annotations_to_bio(
        self,
        annotations: List,
        scheme: str = "BIO",  # BIO or BILOU
        format_type: str = "tsv"  # tsv or json
    ) -> bytes:
        """Export annotations in BIO/BILOU tagging scheme."""
        
        if scheme not in ["BIO", "BILOU"]:
            raise ValueError("Scheme must be 'BIO' or 'BILOU'")
        
        if format_type == "tsv":
            return self._export_bio_tsv(annotations, scheme)
        elif format_type == "json":
            return self._export_bio_json(annotations, scheme)
        else:
            raise ValueError("Format must be 'tsv' or 'json'")
    
    def _export_bio_tsv(self, annotations: List, scheme: str) -> bytes:
        """Export to TSV format with BIO/BILOU tags."""
        output = StringIO()
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        output.write("token\tlabel\tconfidence\tannotator\n")
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text
            text_content = text_obj.content
            
            # Tokenize
            tokens = self._tokenize_with_positions(text_content)
            
            # Apply tagging scheme
            if scheme == "BIO":
                token_labels = self._apply_bio_tagging(tokens, text_anns)
            else:  # BILOU
                token_labels = self._apply_bilou_tagging(tokens, text_anns)
            
            # Write tokens and labels
            for i, (token, start, end) in enumerate(tokens):
                label_info = token_labels.get(i, {"label": "O", "confidence": 1.0, "annotator": ""})
                
                output.write(f"{token}\t{label_info['label']}\t{label_info['confidence']}\t{label_info['annotator']}\n")
            
            output.write("\n")  # Sentence separator
        
        return output.getvalue().encode('utf-8')
    
    def _export_bio_json(self, annotations: List, scheme: str) -> bytes:
        """Export to JSON format with BIO/BILOU tags."""
        
        # Group annotations by text
        texts_annotations = defaultdict(list)
        for ann in annotations:
            texts_annotations[ann.text_id].append(ann)
        
        documents = []
        
        for text_id, text_anns in texts_annotations.items():
            text_obj = text_anns[0].text
            text_content = text_obj.content
            
            # Tokenize
            tokens = self._tokenize_with_positions(text_content)
            
            # Apply tagging scheme
            if scheme == "BIO":
                token_labels = self._apply_bio_tagging(tokens, text_anns)
            else:  # BILOU
                token_labels = self._apply_bilou_tagging(tokens, text_anns)
            
            # Create document
            document = {
                "text_id": text_id,
                "text": text_content,
                "title": text_obj.title,
                "project": text_obj.project.name,
                "tokens": [
                    {
                        "text": token,
                        "start": start,
                        "end": end,
                        "label": token_labels.get(i, {"label": "O", "confidence": 1.0, "annotator": ""})["label"],
                        "confidence": token_labels.get(i, {"label": "O", "confidence": 1.0, "annotator": ""})["confidence"],
                        "annotator": token_labels.get(i, {"label": "O", "confidence": 1.0, "annotator": ""})["annotator"]
                    }
                    for i, (token, start, end) in enumerate(tokens)
                ]
            }
            
            documents.append(document)
        
        result = {
            "format": f"{scheme}_{format_type}",
            "created_at": datetime.utcnow().isoformat(),
            "total_documents": len(documents),
            "documents": documents
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8')
    
    def _tokenize_with_positions(self, text: str) -> List[Tuple[str, int, int]]:
        """Tokenize text with character positions."""
        tokens = []
        for match in re.finditer(r'\S+', text):
            tokens.append((match.group(), match.start(), match.end()))
        return tokens
    
    def _apply_bio_tagging(self, tokens, annotations):
        """Apply BIO tagging scheme."""
        token_labels = {}
        
        for ann in annotations:
            label_name = ann.label.name
            start_char = ann.start_char
            end_char = ann.end_char
            
            overlapping_tokens = []
            for i, (token, token_start, token_end) in enumerate(tokens):
                if token_start < end_char and token_end > start_char:
                    overlapping_tokens.append(i)
            
            # Apply BIO tagging
            for idx, token_id in enumerate(overlapping_tokens):
                if idx == 0:
                    tag = f"B-{label_name}"
                else:
                    tag = f"I-{label_name}"
                
                token_labels[token_id] = {
                    "label": tag,
                    "confidence": ann.confidence_score,
                    "annotator": ann.annotator.username
                }
        
        return token_labels
    
    def _apply_bilou_tagging(self, tokens, annotations):
        """Apply BILOU tagging scheme."""
        token_labels = {}
        
        for ann in annotations:
            label_name = ann.label.name
            start_char = ann.start_char
            end_char = ann.end_char
            
            overlapping_tokens = []
            for i, (token, token_start, token_end) in enumerate(tokens):
                if token_start < end_char and token_end > start_char:
                    overlapping_tokens.append(i)
            
            # Apply BILOU tagging
            if len(overlapping_tokens) == 1:
                # Unit tag
                token_id = overlapping_tokens[0]
                token_labels[token_id] = {
                    "label": f"U-{label_name}",
                    "confidence": ann.confidence_score,
                    "annotator": ann.annotator.username
                }
            else:
                for idx, token_id in enumerate(overlapping_tokens):
                    if idx == 0:
                        tag = f"B-{label_name}"
                    elif idx == len(overlapping_tokens) - 1:
                        tag = f"L-{label_name}"
                    else:
                        tag = f"I-{label_name}"
                    
                    token_labels[token_id] = {
                        "label": tag,
                        "confidence": ann.confidence_score,
                        "annotator": ann.annotator.username
                    }
        
        return token_labels


class AdvancedExportManager:
    """Manager class for all advanced export formats."""
    
    def __init__(self):
        self.conllu_exporter = CoNLLUExporter()
        self.json_nlp_exporter = JSONNLPExporter()
        self.spacy_exporter = SpaCyExporter()
        self.brat_exporter = BRATExporter()
        self.huggingface_exporter = HuggingFaceExporter()
        self.bio_bilou_exporter = BIOBILOUExporter()
    
    def export_annotations(
        self,
        annotations: List,
        format_type: str,
        **kwargs
    ) -> bytes:
        """
        Export annotations to specified academic format.
        
        Supported formats:
        - conllu: CoNLL-U format
        - json-nlp: JSON-NLP format
        - spacy: spaCy training format
        - brat: BRAT standoff format
        - huggingface: HuggingFace datasets format
        - bio: BIO tagging format
        - bilou: BILOU tagging format
        """
        
        if format_type == "conllu":
            return self.conllu_exporter.export_annotations_to_conllu(annotations, **kwargs)
        
        elif format_type == "json-nlp":
            return self.json_nlp_exporter.export_annotations_to_json_nlp(annotations, **kwargs)
        
        elif format_type == "spacy":
            return self.spacy_exporter.export_annotations_to_spacy(annotations, **kwargs)
        
        elif format_type == "brat":
            return self.brat_exporter.export_annotations_to_brat(annotations, **kwargs)
        
        elif format_type == "huggingface":
            return self.huggingface_exporter.export_annotations_to_huggingface(annotations, **kwargs)
        
        elif format_type == "bio":
            return self.bio_bilou_exporter.export_annotations_to_bio(annotations, scheme="BIO", **kwargs)
        
        elif format_type == "bilou":
            return self.bio_bilou_exporter.export_annotations_to_bio(annotations, scheme="BILOU", **kwargs)
        
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def get_supported_formats(self) -> Dict[str, Dict[str, Any]]:
        """Get information about supported formats."""
        return {
            "conllu": {
                "name": "CoNLL-U",
                "description": "Universal Dependencies format for syntactic annotations",
                "file_extension": ".conllu",
                "use_case": "Syntactic parsing, dependency parsing research",
                "options": ["include_metadata", "tokenize_method"]
            },
            "json-nlp": {
                "name": "JSON-NLP",
                "description": "JSON format for linguistic annotations",
                "file_extension": ".json",
                "use_case": "General NLP research, tool interoperability",
                "options": ["include_metadata", "version"]
            },
            "spacy": {
                "name": "spaCy",
                "description": "spaCy training format for custom NLP models",
                "file_extension": ".json",
                "use_case": "Training spaCy NER models",
                "options": ["format_type", "include_metadata"]
            },
            "brat": {
                "name": "BRAT",
                "description": "BRAT standoff annotation format",
                "file_extension": ".zip",
                "use_case": "BRAT annotation tool compatibility",
                "options": ["include_metadata"]
            },
            "huggingface": {
                "name": "HuggingFace Datasets",
                "description": "HuggingFace datasets format for transformer training",
                "file_extension": ".json",
                "use_case": "Training transformer models (BERT, RoBERTa, etc.)",
                "options": ["format_type", "split_ratio"]
            },
            "bio": {
                "name": "BIO Tagging",
                "description": "BIO tagging scheme for sequence labeling",
                "file_extension": ".tsv/.json",
                "use_case": "Named Entity Recognition training",
                "options": ["format_type"]
            },
            "bilou": {
                "name": "BILOU Tagging",
                "description": "BILOU tagging scheme for sequence labeling",
                "file_extension": ".tsv/.json",
                "use_case": "Advanced Named Entity Recognition training",
                "options": ["format_type"]
            }
        }


# Memory storage for export formats implementation
EXPORT_FORMATS_MEMORY = {
    "implementation_date": datetime.utcnow().isoformat(),
    "version": "1.0.0",
    "formats_implemented": [
        "conllu", "json-nlp", "spacy", "brat", "huggingface", "bio", "bilou"
    ],
    "features": {
        "academic_formats": True,
        "ml_training_ready": True,
        "research_compatibility": True,
        "batch_processing": True,
        "metadata_support": True,
        "multi_annotator_support": True
    },
    "performance": {
        "optimized_tokenization": True,
        "memory_efficient": True,
        "streaming_support": False,  # Future enhancement
        "parallel_processing": False  # Future enhancement
    }
}