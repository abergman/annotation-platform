"""
Export Utilities

Functions for exporting annotation data in various formats.
"""

import json
import csv
import xml.etree.ElementTree as ET
from io import StringIO, BytesIO
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime


def export_annotations_to_json(
    annotations: List,
    include_metadata: bool = True,
    include_context: bool = False
) -> bytes:
    """Export annotations to JSON format."""
    
    data = {
        "export_info": {
            "format": "json",
            "exported_at": datetime.utcnow().isoformat(),
            "total_annotations": len(annotations),
            "include_metadata": include_metadata,
            "include_context": include_context
        },
        "annotations": []
    }
    
    for annotation in annotations:
        ann_data = {
            "id": annotation.id,
            "text_id": annotation.text_id,
            "text_title": annotation.text.title,
            "project_id": annotation.text.project_id,
            "project_name": annotation.text.project.name,
            "start_char": annotation.start_char,
            "end_char": annotation.end_char,
            "selected_text": annotation.selected_text,
            "label_id": annotation.label_id,
            "label_name": annotation.label.name,
            "label_color": annotation.label.color,
            "annotator_id": annotation.annotator_id,
            "annotator_username": annotation.annotator.username,
            "confidence_score": annotation.confidence_score,
            "is_validated": annotation.is_validated,
            "validation_notes": annotation.validation_notes,
            "notes": annotation.notes,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
            "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
        
        if include_context:
            ann_data.update({
                "context_before": annotation.context_before,
                "context_after": annotation.context_after
            })
        
        if include_metadata:
            ann_data["metadata"] = annotation.metadata
        
        data["annotations"].append(ann_data)
    
    return json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')


def export_annotations_to_csv(
    annotations: List,
    include_metadata: bool = True,
    include_context: bool = False
) -> bytes:
    """Export annotations to CSV format."""
    
    output = StringIO()
    
    # Define CSV headers
    headers = [
        "id", "text_id", "text_title", "project_id", "project_name",
        "start_char", "end_char", "selected_text", "label_id", "label_name",
        "label_color", "annotator_id", "annotator_username", "confidence_score",
        "is_validated", "validation_notes", "notes", "created_at", "updated_at"
    ]
    
    if include_context:
        headers.extend(["context_before", "context_after"])
    
    if include_metadata:
        headers.append("metadata")
    
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    
    for annotation in annotations:
        row = {
            "id": annotation.id,
            "text_id": annotation.text_id,
            "text_title": annotation.text.title,
            "project_id": annotation.text.project_id,
            "project_name": annotation.text.project.name,
            "start_char": annotation.start_char,
            "end_char": annotation.end_char,
            "selected_text": annotation.selected_text,
            "label_id": annotation.label_id,
            "label_name": annotation.label.name,
            "label_color": annotation.label.color,
            "annotator_id": annotation.annotator_id,
            "annotator_username": annotation.annotator.username,
            "confidence_score": annotation.confidence_score,
            "is_validated": annotation.is_validated,
            "validation_notes": annotation.validation_notes,
            "notes": annotation.notes,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
            "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
        
        if include_context:
            row.update({
                "context_before": annotation.context_before,
                "context_after": annotation.context_after
            })
        
        if include_metadata:
            row["metadata"] = json.dumps(annotation.metadata) if annotation.metadata else None
        
        writer.writerow(row)
    
    return output.getvalue().encode('utf-8')


def export_annotations_to_xlsx(
    annotations: List,
    include_metadata: bool = True,
    include_context: bool = False
) -> bytes:
    """Export annotations to Excel XLSX format."""
    
    # Prepare data for DataFrame
    data = []
    
    for annotation in annotations:
        row = {
            "ID": annotation.id,
            "Text ID": annotation.text_id,
            "Text Title": annotation.text.title,
            "Project ID": annotation.text.project_id,
            "Project Name": annotation.text.project.name,
            "Start Char": annotation.start_char,
            "End Char": annotation.end_char,
            "Selected Text": annotation.selected_text,
            "Label ID": annotation.label_id,
            "Label Name": annotation.label.name,
            "Label Color": annotation.label.color,
            "Annotator ID": annotation.annotator_id,
            "Annotator Username": annotation.annotator.username,
            "Confidence Score": annotation.confidence_score,
            "Is Validated": annotation.is_validated,
            "Validation Notes": annotation.validation_notes,
            "Notes": annotation.notes,
            "Created At": annotation.created_at.isoformat() if annotation.created_at else None,
            "Updated At": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
        
        if include_context:
            row.update({
                "Context Before": annotation.context_before,
                "Context After": annotation.context_after
            })
        
        if include_metadata:
            row["Metadata"] = json.dumps(annotation.metadata) if annotation.metadata else None
        
        data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Write to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Annotations', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Annotations']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return output.getvalue()


def export_annotations_to_xml(
    annotations: List,
    include_metadata: bool = True,
    include_context: bool = False
) -> bytes:
    """Export annotations to XML format."""
    
    root = ET.Element("annotations")
    
    # Add export information
    export_info = ET.SubElement(root, "export_info")
    ET.SubElement(export_info, "format").text = "xml"
    ET.SubElement(export_info, "exported_at").text = datetime.utcnow().isoformat()
    ET.SubElement(export_info, "total_annotations").text = str(len(annotations))
    ET.SubElement(export_info, "include_metadata").text = str(include_metadata).lower()
    ET.SubElement(export_info, "include_context").text = str(include_context).lower()
    
    # Add annotations
    annotations_elem = ET.SubElement(root, "annotation_list")
    
    for annotation in annotations:
        ann_elem = ET.SubElement(annotations_elem, "annotation")
        ann_elem.set("id", str(annotation.id))
        
        # Basic annotation data
        ET.SubElement(ann_elem, "text_id").text = str(annotation.text_id)
        ET.SubElement(ann_elem, "text_title").text = annotation.text.title
        ET.SubElement(ann_elem, "project_id").text = str(annotation.text.project_id)
        ET.SubElement(ann_elem, "project_name").text = annotation.text.project.name
        ET.SubElement(ann_elem, "start_char").text = str(annotation.start_char)
        ET.SubElement(ann_elem, "end_char").text = str(annotation.end_char)
        ET.SubElement(ann_elem, "selected_text").text = annotation.selected_text
        
        # Label information
        label_elem = ET.SubElement(ann_elem, "label")
        ET.SubElement(label_elem, "id").text = str(annotation.label_id)
        ET.SubElement(label_elem, "name").text = annotation.label.name
        ET.SubElement(label_elem, "color").text = annotation.label.color
        
        # Annotator information
        annotator_elem = ET.SubElement(ann_elem, "annotator")
        ET.SubElement(annotator_elem, "id").text = str(annotation.annotator_id)
        ET.SubElement(annotator_elem, "username").text = annotation.annotator.username
        
        # Annotation details
        ET.SubElement(ann_elem, "confidence_score").text = str(annotation.confidence_score)
        ET.SubElement(ann_elem, "is_validated").text = annotation.is_validated
        if annotation.validation_notes:
            ET.SubElement(ann_elem, "validation_notes").text = annotation.validation_notes
        if annotation.notes:
            ET.SubElement(ann_elem, "notes").text = annotation.notes
        
        # Timestamps
        if annotation.created_at:
            ET.SubElement(ann_elem, "created_at").text = annotation.created_at.isoformat()
        if annotation.updated_at:
            ET.SubElement(ann_elem, "updated_at").text = annotation.updated_at.isoformat()
        
        # Context (if requested)
        if include_context:
            context_elem = ET.SubElement(ann_elem, "context")
            if annotation.context_before:
                ET.SubElement(context_elem, "before").text = annotation.context_before
            if annotation.context_after:
                ET.SubElement(context_elem, "after").text = annotation.context_after
        
        # Metadata (if requested)
        if include_metadata and annotation.metadata:
            metadata_elem = ET.SubElement(ann_elem, "metadata")
            for key, value in annotation.metadata.items():
                meta_item = ET.SubElement(metadata_elem, "item")
                meta_item.set("key", str(key))
                meta_item.text = str(value)
    
    # Convert to string and return as bytes
    xml_str = ET.tostring(root, encoding='unicode', method='xml')
    
    # Pretty print the XML
    try:
        import xml.dom.minidom
        dom = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        # Remove empty lines
        pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
        return pretty_xml.encode('utf-8')
    except:
        # Fallback to non-pretty XML
        return xml_str.encode('utf-8')