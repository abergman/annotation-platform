"""
Export API Routes

Data export endpoints for annotations and project data in various formats.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io
import json
import csv
import pandas as pd
from datetime import datetime

from src.core.database import get_db
from src.core.security import get_current_user
from src.core.config import settings
from src.models.user import User
from src.models.project import Project
from src.models.annotation import Annotation
from src.utils.export_utils import (
    export_annotations_to_json,
    export_annotations_to_csv,
    export_annotations_to_xlsx,
    export_annotations_to_xml
)

router = APIRouter()


# Pydantic models
class ExportRequest(BaseModel):
    format: str  # json, csv, xlsx, xml
    project_id: Optional[int] = None
    text_id: Optional[int] = None
    label_id: Optional[int] = None
    annotator_id: Optional[int] = None
    include_metadata: bool = True
    include_context: bool = False
    validated_only: bool = False


class ExportResponse(BaseModel):
    export_id: str
    format: str
    status: str
    created_at: str
    download_url: Optional[str] = None


@router.post("/annotations", response_model=ExportResponse)
async def export_annotations(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export annotations in various formats."""
    
    # Validate format
    if export_request.format not in settings.EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format. Supported formats: {settings.EXPORT_FORMATS}"
        )
    
    # Build query with access control
    query = db.query(Annotation).join(Annotation.text).join(Annotation.text.has(project=True))
    
    # Access control: only annotations from accessible projects
    accessible_projects = db.query(Project).filter(
        (Project.owner_id == current_user.id) | (Project.is_public == True)
    ).all()
    
    project_ids = [p.id for p in accessible_projects]
    if not project_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No accessible projects found"
        )
    
    # Apply filters
    if export_request.project_id:
        if export_request.project_id not in project_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        query = query.filter(Annotation.text.has(project_id=export_request.project_id))
    else:
        query = query.filter(Annotation.text.has(project_id__in=project_ids))
    
    if export_request.text_id:
        query = query.filter(Annotation.text_id == export_request.text_id)
    
    if export_request.label_id:
        query = query.filter(Annotation.label_id == export_request.label_id)
    
    if export_request.annotator_id:
        query = query.filter(Annotation.annotator_id == export_request.annotator_id)
    
    if export_request.validated_only:
        query = query.filter(Annotation.is_validated == "approved")
    
    # Get annotations
    annotations = query.all()
    
    if not annotations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No annotations found matching the criteria"
        )
    
    # Generate export
    export_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{current_user.id}"
    
    try:
        if export_request.format == "json":
            content = export_annotations_to_json(
                annotations, 
                include_metadata=export_request.include_metadata,
                include_context=export_request.include_context
            )
            media_type = "application/json"
            filename = f"{export_id}.json"
            
        elif export_request.format == "csv":
            content = export_annotations_to_csv(
                annotations,
                include_metadata=export_request.include_metadata,
                include_context=export_request.include_context
            )
            media_type = "text/csv"
            filename = f"{export_id}.csv"
            
        elif export_request.format == "xlsx":
            content = export_annotations_to_xlsx(
                annotations,
                include_metadata=export_request.include_metadata,
                include_context=export_request.include_context
            )
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{export_id}.xlsx"
            
        elif export_request.format == "xml":
            content = export_annotations_to_xml(
                annotations,
                include_metadata=export_request.include_metadata,
                include_context=export_request.include_context
            )
            media_type = "application/xml"
            filename = f"{export_id}.xml"
        
        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(content))
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/project/{project_id}/summary")
async def export_project_summary(
    project_id: int,
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export project summary with statistics."""
    
    # Verify project access
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.owner_id != current_user.id and not project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project"
        )
    
    # Collect project statistics
    total_texts = len(project.texts)
    total_annotations = sum(len(text.annotations) for text in project.texts)
    total_labels = len(project.labels)
    
    # Annotation statistics by label
    label_stats = {}
    for label in project.labels:
        label_stats[label.name] = {
            "count": len(label.annotations),
            "color": label.color,
            "description": label.description
        }
    
    # Annotation statistics by annotator
    annotator_stats = {}
    for text in project.texts:
        for annotation in text.annotations:
            username = annotation.annotator.username
            if username not in annotator_stats:
                annotator_stats[username] = 0
            annotator_stats[username] += 1
    
    # Validation statistics
    validation_stats = {
        "pending": 0,
        "approved": 0,
        "rejected": 0
    }
    
    for text in project.texts:
        for annotation in text.annotations:
            validation_stats[annotation.is_validated] += 1
    
    summary = {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "owner": project.owner.username
        },
        "statistics": {
            "total_texts": total_texts,
            "total_annotations": total_annotations,
            "total_labels": total_labels,
            "average_annotations_per_text": round(total_annotations / total_texts, 2) if total_texts > 0 else 0
        },
        "label_distribution": label_stats,
        "annotator_distribution": annotator_stats,
        "validation_status": validation_stats,
        "exported_at": datetime.utcnow().isoformat()
    }
    
    if format == "json":
        return Response(
            content=json.dumps(summary, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=project_{project_id}_summary.json"
            }
        )
    else:  # CSV
        # Flatten summary for CSV export
        rows = []
        
        # Basic stats
        rows.append(["Metric", "Value"])
        rows.append(["Project Name", summary["project"]["name"]])
        rows.append(["Total Texts", summary["statistics"]["total_texts"]])
        rows.append(["Total Annotations", summary["statistics"]["total_annotations"]])
        rows.append(["Total Labels", summary["statistics"]["total_labels"]])
        rows.append(["Avg Annotations/Text", summary["statistics"]["average_annotations_per_text"]])
        rows.append(["", ""])  # Empty row
        
        # Label distribution
        rows.append(["Label", "Count"])
        for label, stats in summary["label_distribution"].items():
            rows.append([label, stats["count"]])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=project_{project_id}_summary.csv"
            }
        )