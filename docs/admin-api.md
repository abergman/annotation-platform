# Admin API Documentation

## Overview

The Admin API provides comprehensive administrative functionality for managing the text annotation system. It includes user management, project administration, system statistics, database maintenance, audit logging, and data export capabilities.

## Authentication

All admin endpoints require authentication with admin privileges. Include the JWT token in the Authorization header:

```http
Authorization: Bearer <your_jwt_token>
```

### Access Levels

- **Admin**: Basic administrative privileges (`is_admin = True`)
- **Super Admin**: Full administrative privileges (first admin user or explicitly granted)

## Base URL

All admin endpoints are prefixed with `/api/admin`

## User Management

### List Users

```http
GET /api/admin/users
```

**Query Parameters:**
- `skip` (int, default: 0): Number of records to skip
- `limit` (int, default: 100, max: 1000): Number of records to return
- `search` (string): Search by username, email, or full name
- `role` (string): Filter by user role
- `is_active` (bool): Filter by active status
- `is_admin` (bool): Filter by admin status
- `sort_by` (string): Sort by field (username, email, created_at, last_login)
- `sort_order` (string): Sort order (asc, desc)

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "username": "john_doe",
      "email": "john@example.com",
      "full_name": "John Doe",
      "institution": "University",
      "role": "researcher",
      "is_active": true,
      "is_verified": false,
      "created_at": "2024-01-01T00:00:00",
      "last_login": "2024-01-15T10:30:00"
    }
  ],
  "pagination": {
    "total": 150,
    "skip": 0,
    "limit": 100,
    "pages": 2
  }
}
```

### Create User

```http
POST /api/admin/users
```

**Request Body:**
```json
{
  "username": "new_user",
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "New User",
  "institution": "University",
  "role": "researcher",
  "is_active": true,
  "is_verified": false,
  "is_admin": false
}
```

### Get User Details

```http
GET /api/admin/users/{user_id}
```

**Response includes additional statistics:**
```json
{
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "project_count": 5,
    "annotation_count": 150,
    "recent_activity": []
  }
}
```

### Update User

```http
PUT /api/admin/users/{user_id}
```

**Request Body (all fields optional):**
```json
{
  "username": "updated_username",
  "email": "updated@example.com",
  "full_name": "Updated Name",
  "institution": "New Institution",
  "role": "annotator",
  "is_active": true,
  "is_verified": true,
  "is_admin": false
}
```

### Delete User

```http
DELETE /api/admin/users/{user_id}?force=false
```

**Query Parameters:**
- `force` (bool): Force delete even if user has associated data

### Bulk User Operations

```http
POST /api/admin/users/bulk
```

**Request Body:**
```json
{
  "user_ids": [1, 2, 3, 4],
  "operation": "activate",
  "role": "researcher"
}
```

**Available Operations:**
- `activate`: Set users as active
- `deactivate`: Set users as inactive
- `verify`: Mark users as verified
- `unverify`: Mark users as unverified
- `delete`: Delete users
- `promote`: Grant admin privileges (super admin only)
- `demote`: Revoke admin privileges (super admin only)

## Project Administration

### List Projects

```http
GET /api/admin/projects
```

**Query Parameters:**
- `skip`, `limit`: Pagination
- `search`: Search by name or description
- `owner_id`: Filter by owner ID
- `is_active`: Filter by active status
- `is_public`: Filter by public status
- `sort_by`: Sort by field (name, created_at, updated_at)
- `sort_order`: Sort order (asc, desc)

### Get Project Details

```http
GET /api/admin/projects/{project_id}
```

**Response includes comprehensive statistics:**
```json
{
  "project": {
    "id": 1,
    "name": "Research Project",
    "description": "Project description",
    "owner_username": "john_doe",
    "statistics": {
      "text_count": 100,
      "label_count": 10,
      "total_annotations": 500,
      "unique_annotators": 5,
      "annotator_activity": [
        {"username": "annotator1", "annotation_count": 200}
      ]
    }
  }
}
```

### Update Project

```http
PUT /api/admin/projects/{project_id}
```

### Delete Project

```http
DELETE /api/admin/projects/{project_id}?force=false
```

## System Statistics

### System Overview

```http
GET /api/admin/statistics/overview
```

**Response:**
```json
{
  "overview": {
    "total_users": 150,
    "active_users": 120,
    "total_projects": 25,
    "active_projects": 20,
    "total_texts": 1000,
    "total_annotations": 5000,
    "total_labels": 100
  },
  "recent_activity": {
    "new_users_30d": 10,
    "new_projects_30d": 3,
    "new_annotations_30d": 200,
    "users_with_recent_login": 80
  },
  "top_annotators": [],
  "most_active_projects": [],
  "system_resources": {
    "disk_usage": {
      "total": 1000000000,
      "used": 400000000,
      "free": 600000000,
      "percent": 40.0
    },
    "memory_usage": {
      "total": 8000000000,
      "used": 3000000000,
      "available": 5000000000,
      "percent": 37.5
    }
  }
}
```

### System Timeline

```http
GET /api/admin/statistics/timeline?days=30
```

**Query Parameters:**
- `days` (int, 1-365): Number of days to include

## Database Maintenance

### Database Health Check

```http
GET /api/admin/health/database
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "checks": {
    "connectivity": {"status": "ok", "message": "Database connection successful"},
    "table_users": {"status": "ok", "count": 150, "message": "Table users accessible with 150 records"},
    "data_integrity": {"status": "ok", "orphaned_annotations": 0, "orphaned_texts": 0},
    "database_size": {"status": "ok", "size": "45 MB"}
  }
}
```

### Database Cleanup (Super Admin Only)

```http
POST /api/admin/maintenance/cleanup?dry_run=true&max_age_days=90
```

**Query Parameters:**
- `dry_run` (bool, default: true): Perform dry run without actual cleanup
- `max_age_days` (int, default: 90): Maximum age in days for log entries

## Audit Log Management

### Get Audit Logs

```http
GET /api/admin/audit-logs
```

**Query Parameters:**
- `skip`, `limit`: Pagination
- `admin_id`: Filter by admin user ID
- `action`: Filter by action type
- `target_type`: Filter by target type
- `start_date`, `end_date`: Date range filtering

### Get Security Events

```http
GET /api/admin/security-events
```

**Query Parameters:**
- `skip`, `limit`: Pagination
- `event_type`: Filter by event type
- `severity`: Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
- `resolved`: Filter by resolution status
- `start_date`, `end_date`: Date range filtering

### Resolve Security Event

```http
PUT /api/admin/security-events/{event_id}/resolve?resolution_notes=Fixed the issue
```

## Data Export

### Export System Data (Super Admin Only)

```http
GET /api/admin/export/system-data
```

**Query Parameters:**
- `format` (string): Export format (json, csv)
- `include_users` (bool): Include user data
- `include_projects` (bool): Include project data
- `include_annotations` (bool): Include annotation data
- `include_audit_logs` (bool): Include audit logs
- `start_date`, `end_date`: Date range filtering

**Response:** File download with appropriate content type

## Configuration Management

### Get System Configuration

```http
GET /api/admin/config
```

**Response:**
```json
{
  "configuration": {
    "application": {
      "app_name": "Text Annotation System",
      "debug": false,
      "host": "0.0.0.0",
      "port": 8000
    },
    "features": {
      "max_file_size": 10485760,
      "allowed_extensions": [".txt", ".docx", ".pdf", ".csv"],
      "max_annotations_per_text": 1000,
      "max_labels_per_project": 100,
      "export_formats": ["json", "csv", "xlsx", "xml"]
    },
    "security": {
      "access_token_expire_minutes": 30,
      "algorithm": "HS256"
    },
    "cors": {
      "allowed_origins": ["http://localhost:3000", "http://localhost:8080"]
    }
  }
}
```

## Dashboard Data

### Dashboard Summary

```http
GET /api/admin/dashboard/summary
```

**Response:**
```json
{
  "totals": {
    "users": 150,
    "active_users": 120,
    "projects": 25,
    "active_projects": 20,
    "annotations": 5000,
    "texts": 1000
  },
  "recent": {
    "new_users_today": 2,
    "new_projects_week": 1,
    "new_annotations_week": 50,
    "recent_logins": 30
  },
  "alerts": {
    "inactive_users": 30,
    "unresolved_security_events": 2
  },
  "recent_activity": {
    "users": [],
    "projects": []
  }
}
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin privileges required"
}
```

### 404 Not Found
```json
{
  "detail": "User not found"
}
```

### 400 Bad Request
```json
{
  "detail": "Username already exists"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Security Features

### Audit Trail
All administrative actions are automatically logged in the audit trail with:
- Admin user information
- Action performed
- Target resource
- Timestamp
- Additional details

### Access Control
- Role-based access control with admin/super admin levels
- Prevents admins from modifying their own privileges
- Super admin privileges required for sensitive operations

### Data Protection
- Sensitive data (passwords) excluded from exports
- Optional force deletion with warnings
- Dry run capability for maintenance operations

## Rate Limiting

Admin endpoints may be subject to rate limiting. Include appropriate delays between requests if you encounter 429 responses.

## Examples

### Create Multiple Users
```python
import requests

headers = {"Authorization": "Bearer your_admin_token"}
users_to_create = [
    {"username": "researcher1", "email": "r1@example.com", "password": "secure123", "role": "researcher"},
    {"username": "annotator1", "email": "a1@example.com", "password": "secure123", "role": "annotator"}
]

for user_data in users_to_create:
    response = requests.post("http://localhost:8000/api/admin/users", json=user_data, headers=headers)
    print(f"Created user: {response.json()}")
```

### Export User Data
```python
import requests

headers = {"Authorization": "Bearer your_super_admin_token"}
response = requests.get(
    "http://localhost:8000/api/admin/export/system-data?format=json&include_users=true", 
    headers=headers
)

with open("users_export.json", "wb") as f:
    f.write(response.content)
```

### Monitor System Health
```python
import requests

headers = {"Authorization": "Bearer your_admin_token"}

# Check database health
db_health = requests.get("http://localhost:8000/api/admin/health/database", headers=headers)
print(f"Database Status: {db_health.json()['status']}")

# Get system overview
overview = requests.get("http://localhost:8000/api/admin/statistics/overview", headers=headers)
stats = overview.json()
print(f"Total Users: {stats['overview']['total_users']}")
print(f"Active Users: {stats['overview']['active_users']}")
```