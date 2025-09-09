# Text Annotation System

A comprehensive Python-based text annotation system built with FastAPI and PostgreSQL, designed for academic research workflows with multi-user collaboration support.

## Features

- **Multi-user Authentication**: Secure user registration and JWT-based authentication
- **Project Management**: Create and manage annotation projects with access controls
- **Text Processing**: Upload and process various file formats (TXT, DOCX, PDF, CSV)
- **Rich Annotations**: Create text span annotations with labels, confidence scores, and validation
- **Hierarchical Labels**: Support for nested label categories with visual customization
- **Export Capabilities**: Export data in multiple formats (JSON, CSV, XLSX, XML)
- **Access Control**: Project-based permissions with public/private settings
- **Validation Workflow**: Annotation approval and rejection system

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip or poetry

### Installation

1. **Clone and setup the project:**
   ```bash
   git clone <repository-url>
   cd annotation
   pip install -r requirements.txt
   ```

2. **Database setup:**
   ```bash
   # Create PostgreSQL database
   createdb annotation_db
   createuser annotation_user --password
   ```

3. **Environment configuration:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and settings
   ```

4. **Run the application:**
   ```bash
   python -m uvicorn src.main:app --reload
   ```

5. **Access the API:**
   - API Documentation: http://localhost:8000/api/docs
   - Health Check: http://localhost:8000/health

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get user profile
- `PUT /api/auth/me` - Update user profile

### Projects
- `POST /api/projects/` - Create project
- `GET /api/projects/` - List projects
- `GET /api/projects/{id}` - Get project
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

### Texts
- `POST /api/texts/` - Create text document
- `POST /api/texts/upload` - Upload text file
- `GET /api/texts/` - List texts
- `GET /api/texts/{id}` - Get text
- `PUT /api/texts/{id}` - Update text
- `DELETE /api/texts/{id}` - Delete text

### Annotations
- `POST /api/annotations/` - Create annotation
- `GET /api/annotations/` - List annotations
- `GET /api/annotations/{id}` - Get annotation
- `PUT /api/annotations/{id}` - Update annotation
- `PUT /api/annotations/{id}/validate` - Validate annotation
- `DELETE /api/annotations/{id}` - Delete annotation

### Labels
- `POST /api/labels/` - Create label
- `GET /api/labels/` - List labels
- `GET /api/labels/{id}` - Get label
- `PUT /api/labels/{id}` - Update label
- `DELETE /api/labels/{id}` - Delete label
- `GET /api/labels/project/{id}/hierarchy` - Get label hierarchy

### Export
- `POST /api/export/annotations` - Export annotations
- `GET /api/export/project/{id}/summary` - Export project summary

## Architecture

### Database Models
- **User**: Authentication and profile management
- **Project**: Annotation project organization
- **Text**: Document storage and metadata
- **Annotation**: Text span annotations with labels
- **Label**: Hierarchical annotation categories

### Core Components
- **FastAPI Application**: RESTful API with automatic OpenAPI docs
- **SQLAlchemy Models**: Database ORM with PostgreSQL backend
- **JWT Authentication**: Secure token-based authentication
- **File Processing**: Multi-format text extraction utilities
- **Export System**: Multiple output formats for data analysis

### Security Features
- Password hashing with bcrypt
- JWT token authentication
- Project-based access controls
- Input validation and sanitization
- File upload security checks

## Configuration

Key environment variables in `.env`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/annotation_db

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File uploads
MAX_FILE_SIZE=10485760  # 10MB
UPLOAD_DIR=uploads
EXPORT_DIR=exports

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
black src/
isort src/
flake8 src/
```

### Database Migrations
```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Setup
- Use environment variables for configuration
- Enable SSL/HTTPS in production
- Set up database connection pooling
- Configure reverse proxy (nginx)
- Set up monitoring and logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.