# Text Annotation System - Admin Interface

## Overview

This comprehensive admin interface provides powerful administrative functionality for managing the text annotation system. Academic administrators can manage users, projects, monitor system health, and maintain data integrity through a rich set of API endpoints.

## 🚀 Quick Start

### 1. Create Your First Admin User

Run the interactive admin user creation script:

```bash
cd /home/andreas/Code/annotation
python scripts/create_admin_user.py
```

### 2. Access the Admin Interface

Once the system is running, access the admin API documentation at:
- **API Documentation**: http://localhost:8000/api/docs
- **Alternative Docs**: http://localhost:8000/api/redoc

All admin endpoints are under the `/api/admin` prefix.

### 3. Authenticate

Use the admin credentials you created to get an access token via the login endpoint:

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "your_admin", "password": "your_password"}'
```

Use the returned token in the Authorization header for all admin requests:

```bash
Authorization: Bearer <your_token>
```

## 📋 Core Features

### User Management
- **List Users**: Advanced filtering, search, and pagination
- **Create Users**: Create user accounts with custom roles and permissions
- **Update Users**: Modify user information, roles, and status
- **Delete Users**: Remove users with optional force deletion
- **Bulk Operations**: Activate, deactivate, verify, promote, or demote multiple users
- **User Statistics**: Detailed activity and participation metrics

### Project Administration
- **Project Oversight**: View all projects with comprehensive statistics
- **Project Health Monitoring**: Health scores and recommendations
- **Project Management**: Update project settings and ownership
- **Bulk Project Operations**: Manage multiple projects efficiently

### System Analytics
- **System Overview**: Real-time statistics and resource usage
- **Timeline Analytics**: Historical trends and growth patterns
- **User Activity Monitoring**: Login patterns and engagement metrics
- **Performance Metrics**: System health and bottleneck identification

### Database Maintenance
- **Health Checks**: Comprehensive database connectivity and integrity tests
- **Data Cleanup**: Remove old logs and resolve orphaned records
- **Backup Utilities**: Data export in multiple formats
- **Integrity Monitoring**: Detect and report data inconsistencies

### Security & Audit
- **Audit Trail**: Complete log of all administrative actions
- **Security Events**: Monitor and resolve security incidents
- **Access Control**: Role-based permissions with admin/super-admin levels
- **Activity Monitoring**: Track suspicious patterns and anomalies

### Data Export/Import
- **System Data Export**: Export users, projects, annotations in JSON/CSV
- **Filtered Exports**: Date ranges and selective data inclusion
- **Audit Log Export**: Complete administrative action history
- **Configuration Backup**: Safe system configuration export

## 🔧 API Endpoints

### User Management
```
GET    /api/admin/users              # List users with filtering
POST   /api/admin/users              # Create new user
GET    /api/admin/users/{id}         # Get user details
PUT    /api/admin/users/{id}         # Update user
DELETE /api/admin/users/{id}         # Delete user
POST   /api/admin/users/bulk         # Bulk user operations
```

### Project Administration
```
GET    /api/admin/projects           # List projects
GET    /api/admin/projects/{id}      # Get project details
PUT    /api/admin/projects/{id}      # Update project
DELETE /api/admin/projects/{id}      # Delete project
```

### System Statistics
```
GET    /api/admin/statistics/overview     # System overview
GET    /api/admin/statistics/timeline     # Historical trends
```

### Database Maintenance
```
GET    /api/admin/health/database         # Database health check
POST   /api/admin/maintenance/cleanup     # Clean old records (super admin)
```

### Audit & Security
```
GET    /api/admin/audit-logs              # View audit trail
GET    /api/admin/security-events         # Security events
PUT    /api/admin/security-events/{id}/resolve  # Resolve security event
```

### Data Management
```
GET    /api/admin/export/system-data      # Export system data (super admin)
GET    /api/admin/config                  # View system configuration
GET    /api/admin/dashboard/summary       # Dashboard summary data
```

## 🛡️ Security Features

### Access Control
- **Admin Role**: Basic administrative privileges
- **Super Admin Role**: Full system control (first admin or explicitly granted)
- **Self-Protection**: Admins cannot modify their own critical privileges
- **Token-Based**: Secure JWT authentication for all endpoints

### Audit Trail
- **Complete Logging**: All admin actions automatically logged
- **Immutable Records**: Audit logs cannot be modified after creation
- **Detailed Context**: IP addresses, timestamps, and action details
- **Retention Policies**: Configurable log retention periods

### Data Protection
- **Sensitive Data Exclusion**: Passwords and secrets excluded from exports
- **Force Deletion Warnings**: Confirmation required for destructive operations
- **Dry Run Capability**: Test maintenance operations before execution
- **Backup Integration**: Automated backup before major operations

## 🔍 Monitoring & Analytics

### System Health
- **Real-time Metrics**: CPU, memory, and disk usage monitoring
- **Database Health**: Connection status and integrity checks
- **Performance Tracking**: Response times and bottleneck identification
- **Alert System**: Automated alerts for critical issues

### User Analytics
- **Activity Patterns**: Login frequency and session duration
- **Engagement Metrics**: Annotation activity and project participation
- **Growth Trends**: User registration and activation rates
- **Usage Statistics**: Feature adoption and system utilization

### Project Insights
- **Completion Rates**: Progress tracking and milestone analysis
- **Quality Metrics**: Inter-annotator agreement and consistency
- **Resource Usage**: Storage consumption and processing load
- **Collaboration Patterns**: Team interaction and workflow efficiency

## 🛠️ Administrative Tasks

### Daily Operations
1. **Monitor System Health**: Check `/api/admin/health/database`
2. **Review User Activity**: View `/api/admin/statistics/overview`
3. **Check Security Events**: Monitor `/api/admin/security-events`
4. **Audit Recent Actions**: Review `/api/admin/audit-logs`

### Weekly Tasks
1. **User Management**: Review new registrations and inactive users
2. **Project Health**: Analyze project progress and bottlenecks
3. **System Cleanup**: Clean old logs and temporary data
4. **Performance Review**: Analyze system performance trends

### Monthly Tasks
1. **Data Backup**: Export critical system data
2. **Security Review**: Comprehensive security audit
3. **User Analytics**: Generate user engagement reports
4. **System Optimization**: Database maintenance and cleanup

## 📊 Dashboard Features

The admin dashboard provides:

- **Real-time Statistics**: Live system metrics and counters
- **Activity Timeline**: Visual representation of system activity
- **Health Indicators**: System status and alert notifications
- **Quick Actions**: Common administrative tasks and shortcuts
- **Resource Monitoring**: System resource usage and capacity planning

## 🔧 Configuration

### Environment Variables

Key environment variables for admin functionality:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/annotation_db

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Admin Features
ADMIN_EMAIL_NOTIFICATIONS=true
AUDIT_LOG_RETENTION_DAYS=90
SECURITY_EVENT_AUTO_RESOLVE=false
```

### Feature Flags

Control admin features through configuration:

```python
# In src/core/config.py
ADMIN_FEATURES = {
    "user_bulk_operations": True,
    "data_export": True,
    "system_maintenance": True,
    "advanced_analytics": True
}
```

## 🚨 Troubleshooting

### Common Issues

1. **403 Forbidden**: Ensure user has admin privileges
2. **Database Connection Errors**: Check DATABASE_URL configuration
3. **Token Expiration**: Refresh JWT tokens regularly
4. **Performance Issues**: Monitor system resources and optimize queries

### Support Commands

```bash
# Check admin users
python scripts/create_admin_user.py --list

# Database health check
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/admin/health/database

# System statistics
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/admin/statistics/overview
```

## 📚 Additional Resources

- **Full API Documentation**: `/docs/admin-api.md`
- **Test Suite**: `/tests/test_admin_api.py`
- **Helper Utilities**: `/src/utils/admin_helpers.py`
- **Security Guidelines**: Contact system administrator for security policies

## 🤝 Support

For technical support or questions about the admin interface:

1. Check the API documentation at `/api/docs`
2. Review system logs for error details
3. Use health check endpoints to diagnose issues
4. Contact system administrator for access problems

---

**Note**: This admin interface provides powerful system management capabilities. Use responsibly and follow your organization's security policies when managing user data and system configurations.