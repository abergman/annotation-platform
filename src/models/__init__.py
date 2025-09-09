"""
Database Models Package

Import all models for easy access and ensuring they're registered with SQLAlchemy.
"""

from src.core.database import Base
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.annotation import Annotation
from src.models.label import Label
from src.models.audit_log import AuditLog, SystemLog, SecurityEvent

# Import additional models if they exist
try:
    from src.models.agreement import Agreement
except ImportError:
    Agreement = None

try:
    from src.models.batch_models import BatchOperation, BatchOperationItem
except ImportError:
    BatchOperation = None
    BatchOperationItem = None

try:
    from src.models.conflict import Conflict
except ImportError:
    Conflict = None

__all__ = [
    "Base",
    "User", 
    "Project",
    "Text",
    "Annotation", 
    "Label",
    "AuditLog",
    "SystemLog",
    "SecurityEvent"
]

# Add optional models to __all__ if they exist
if Agreement:
    __all__.append("Agreement")
if BatchOperation:
    __all__.extend(["BatchOperation", "BatchOperationItem"])
if Conflict:
    __all__.append("Conflict")