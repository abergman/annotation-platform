# Technology Stack Recommendations
## Academic Text Annotation System Development

### Executive Summary

This document provides comprehensive technology stack recommendations for developing a custom text annotation system optimized for academic research teams. The recommendations are based on extensive analysis of existing tools, academic requirements, and modern development best practices.

## 1. Architecture Recommendations

### 1.1 System Architecture Pattern

**Recommended**: 3-Tier Microservices Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend       │    │  Backend API    │    │  Data Layer     │
│  (React/Vue.js) │◄──►│  (Django/Flask) │◄──►│  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  Cache Layer    │              │
         └──────────────►│  (Redis)        │◄─────────────┘
                        └─────────────────┘
```

**Benefits:**
- Clear separation of concerns
- Scalable and maintainable
- Technology flexibility
- Independent deployment capabilities

### 1.2 Deployment Architecture

**Recommended**: Containerized Deployment with Docker
```
                    Internet
                        │
                ┌───────────────┐
                │ Load Balancer │  ← Nginx/HAProxy
                │   (Nginx)     │
                └───────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
        ┌──────────┐        ┌──────────┐
        │   App    │        │   App    │  ← Django/Flask
        │ Server 1 │        │ Server 2 │
        └──────────┘        └──────────┘
              │                   │
              └─────────┬─────────┘
                        │
              ┌─────────────────┐
              │   Database      │  ← PostgreSQL
              │  (PostgreSQL)   │
              └─────────────────┘
                        │
              ┌─────────────────┐
              │     Cache       │  ← Redis
              │    (Redis)      │
              └─────────────────┘
```

## 2. Backend Technology Stack

### 2.1 Framework Comparison and Recommendation

#### Primary Recommendation: Django 4.2+

**Justification:**
```python
# Django advantages for academic annotation systems
DJANGO_BENEFITS = {
    'user_management': 'Built-in authentication, authorization, and user management',
    'admin_interface': 'Auto-generated admin interface for data management',
    'orm': 'Powerful ORM with query optimization',
    'security': 'Built-in security features (CSRF, XSS, SQL injection protection)',
    'scalability': 'Proven scalability in large applications',
    'documentation': 'Comprehensive documentation and community',
    'academic_support': 'Used by many academic institutions'
}
```

**Key Features for Academic Use:**
- Django Admin for project management
- User groups and permissions system
- Built-in form validation and processing
- Extensive third-party packages ecosystem
- Database migration system

#### Alternative: Flask 2.3+ (for smaller projects)

**When to choose Flask:**
```python
FLASK_USE_CASES = {
    'prototypes': 'Rapid prototyping and MVP development',
    'custom_workflows': 'Highly customized annotation workflows',
    'microservices': 'Building specific microservices',
    'research_tools': 'Small-scale research tools',
    'api_services': 'Pure API backend services'
}
```

### 2.2 Database Recommendations

#### Primary Recommendation: PostgreSQL 15+

**Technical Justification:**
```sql
-- PostgreSQL features beneficial for annotation systems
CREATE TABLE annotations (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    annotation_data JSONB,  -- Flexible JSON storage
    full_text_vector tsvector,  -- Full-text search
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Full-text search index
CREATE INDEX annotations_fts_idx ON annotations 
USING GIN (full_text_vector);

-- JSON index for efficient querying
CREATE INDEX annotations_data_idx ON annotations 
USING GIN (annotation_data);
```

**Key Advantages:**
- JSONB support for flexible annotation data
- Full-text search capabilities
- Excellent multi-user concurrency
- ACID compliance
- Rich data type support
- Mature replication and backup solutions

#### Alternative: SQLite (development only)

**Limitations for Production:**
```python
SQLITE_LIMITATIONS = {
    'concurrency': 'No concurrent writes (single writer)',
    'user_management': 'No built-in user permissions',
    'scalability': 'Not suitable for multiple users',
    'backup': 'File-based backup only',
    'full_text': 'Limited full-text search capabilities'
}
```

### 2.3 Core Python Dependencies

```python
# requirements.txt for Django-based system
Django==4.2.7
djangorestframework==3.14.0
django-cors-headers==4.3.1
psycopg2-binary==2.9.7
redis==5.0.1
celery==5.3.4
django-celery-beat==2.5.0

# NLP and ML libraries
spacy==3.7.2
scikit-learn==1.3.2
pandas==2.1.3
numpy==1.24.3

# Authentication and security
django-allauth==0.57.0
djangorestframework-simplejwt==5.3.0
django-ratelimit==4.1.0

# File handling and export
openpyxl==3.1.2
xmltodict==0.13.0
python-docx==1.1.0

# Development and testing
pytest==7.4.3
pytest-django==4.7.0
black==23.11.0
flake8==6.1.0
mypy==1.7.1
```

### 2.4 API Design Recommendations

#### RESTful API with Django REST Framework

```python
# Example API structure
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing annotation projects
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def export_annotations(self, request, pk=None):
        """Export project annotations in various formats"""
        project = self.get_object()
        format_type = request.query_params.get('format', 'json')
        
        if format_type == 'conll':
            return Response(export_to_conll(project))
        elif format_type == 'spacy':
            return Response(export_to_spacy(project))
        else:
            return Response(export_to_json(project))
    
    @action(detail=True, methods=['post'])
    def calculate_agreement(self, request, pk=None):
        """Calculate inter-annotator agreement"""
        project = self.get_object()
        agreement_scores = calculate_kappa_scores(project)
        return Response(agreement_scores)
```

## 3. Frontend Technology Stack

### 3.1 Framework Recommendation

#### Primary Recommendation: React 18+

**Technical Justification:**
```javascript
// React advantages for annotation interfaces
const REACT_BENEFITS = {
    ecosystem: 'Largest ecosystem of UI components',
    performance: 'Virtual DOM for efficient updates',
    community: 'Extensive community and resources',
    flexibility: 'Component-based architecture',
    testing: 'Excellent testing tools and practices',
    typescript: 'Strong TypeScript support'
};
```

**Key Libraries for Annotation Interface:**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "@mui/material": "^5.14.18",
    "@mui/icons-material": "^5.14.18",
    "react-router-dom": "^6.20.1",
    "axios": "^1.6.2",
    "react-query": "^3.39.3",
    "zustand": "^4.4.7",
    "react-hook-form": "^7.47.0",
    "yup": "^1.3.3"
  }
}
```

#### Alternative: Vue.js 3+

**When to choose Vue.js:**
```javascript
const VUE_USE_CASES = {
    'team_preference': 'Team has Vue.js experience',
    'simpler_learning': 'Easier learning curve for new developers',
    'smaller_projects': 'Less complex annotation requirements',
    'rapid_development': 'Faster initial development'
};
```

### 3.2 UI Component Strategy

#### Recommended: Material-UI (MUI) for React

```javascript
// Example annotation interface component
import { Box, Paper, Typography, Chip } from '@mui/material';
import { useState } from 'react';

const AnnotationInterface = ({ document, annotations, onAnnotate }) => {
    const [selectedText, setSelectedText] = useState('');
    
    const handleTextSelection = () => {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            setSelectedText(range.toString());
        }
    };
    
    return (
        <Box sx={{ display: 'flex', height: '100vh' }}>
            <Paper sx={{ flex: 1, p: 2 }}>
                <Typography 
                    variant="body1"
                    onMouseUp={handleTextSelection}
                    sx={{ lineHeight: 2, userSelect: 'text' }}
                >
                    {document.content}
                </Typography>
            </Paper>
            <Box sx={{ width: 300, p: 2 }}>
                <Typography variant="h6">Annotations</Typography>
                {annotations.map(annotation => (
                    <Chip 
                        key={annotation.id}
                        label={annotation.label}
                        variant="outlined"
                        sx={{ m: 0.5 }}
                    />
                ))}
            </Box>
        </Box>
    );
};
```

### 3.3 State Management

#### Recommended: Zustand for React

```javascript
// Annotation state management
import { create } from 'zustand';

const useAnnotationStore = create((set, get) => ({
    currentDocument: null,
    annotations: [],
    selectedAnnotation: null,
    
    setCurrentDocument: (document) => 
        set({ currentDocument: document }),
    
    addAnnotation: (annotation) => 
        set(state => ({ 
            annotations: [...state.annotations, annotation] 
        })),
    
    updateAnnotation: (id, updates) => 
        set(state => ({
            annotations: state.annotations.map(ann => 
                ann.id === id ? { ...ann, ...updates } : ann
            )
        })),
    
    deleteAnnotation: (id) => 
        set(state => ({
            annotations: state.annotations.filter(ann => ann.id !== id)
        }))
}));
```

## 4. Infrastructure and DevOps

### 4.1 Containerization with Docker

#### Docker Configuration

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
```

```dockerfile
# Frontend Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Docker Compose for Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: annotation_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/annotation_db
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  celery:
    build: ./backend
    command: celery -A config worker -l info
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/annotation_db
      - REDIS_URL=redis://redis:6379/0

volumes:
  postgres_data:
```

### 4.2 Production Deployment

#### Kubernetes Deployment (Optional)

```yaml
# kubernetes/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: annotation-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: annotation-backend
  template:
    metadata:
      labels:
        app: annotation-backend
    spec:
      containers:
      - name: backend
        image: annotation-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

#### Simple Docker Swarm Alternative

```yaml
# docker-stack.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    deploy:
      replicas: 1
    configs:
      - nginx.conf

  backend:
    image: annotation-backend:latest
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    environment:
      - DATABASE_URL=${DATABASE_URL}

  db:
    image: postgres:15
    deploy:
      replicas: 1
      placement:
        constraints: [node.role == manager]
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

## 5. Development Tools and Workflow

### 5.1 Code Quality Tools

```python
# pyproject.toml - Python code quality configuration
[tool.black]
line-length = 88
target-version = ['py311']

[tool.flake8]
max-line-length = 88
extend-ignore = ["E203", "W503"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
addopts = "--cov --cov-report=html --cov-report=term-missing"
```

```json
// .eslintrc.json - Frontend code quality
{
  "extends": [
    "react-app",
    "react-app/jest",
    "@typescript-eslint/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "react-hooks/exhaustive-deps": "warn",
    "prefer-const": "error"
  }
}
```

### 5.2 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run tests
      run: npm test -- --coverage --watchAll=false
    
    - name: Build
      run: npm run build

  deploy:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Deploy to production
      run: |
        # Deployment commands here
        echo "Deploying to production"
```

## 6. Performance and Monitoring

### 6.1 Performance Optimization

#### Database Optimization

```python
# Django model optimization for annotations
from django.db import models
from django.contrib.postgres.indexes import GinIndex

class Annotation(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    start_char = models.IntegerField(db_index=True)
    end_char = models.IntegerField(db_index=True)
    label = models.CharField(max_length=100, db_index=True)
    text = models.TextField()
    metadata = models.JSONField(default=dict)
    
    class Meta:
        indexes = [
            GinIndex(fields=['metadata']),
            models.Index(fields=['document', 'start_char']),
            models.Index(fields=['label', 'document']),
        ]
        
    def __str__(self):
        return f"{self.label}: {self.text[:50]}"
```

#### Caching Strategy

```python
# Redis caching configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'annotation_cache'
    }
}

# Caching example
from django.core.cache import cache
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # Cache for 15 minutes
def project_statistics(request, project_id):
    cache_key = f"project_stats_{project_id}"
    stats = cache.get(cache_key)
    
    if not stats:
        stats = calculate_project_statistics(project_id)
        cache.set(cache_key, stats, 60 * 60)  # Cache for 1 hour
    
    return JsonResponse(stats)
```

### 6.2 Monitoring and Logging

```python
# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file'],
    },
}
```

## 7. Security Recommendations

### 7.1 Authentication and Authorization

```python
# Django settings for security
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# JWT configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://yourdomain.com",
]

# Security middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
]
```

### 7.2 Data Protection

```python
# Encryption for sensitive data
from cryptography.fernet import Fernet
import base64

class EncryptedTextField(models.TextField):
    """Custom field for encrypting sensitive text data"""
    
    def __init__(self, *args, **kwargs):
        self.encryption_key = kwargs.pop('encryption_key', None)
        super().__init__(*args, **kwargs)
    
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self.decrypt(value)
    
    def to_python(self, value):
        if isinstance(value, str):
            return self.decrypt(value)
        return value
    
    def get_prep_value(self, value):
        if value is None:
            return value
        return self.encrypt(value)
```

## 8. Testing Strategy

### 8.1 Backend Testing

```python
# Test configuration
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

class AnnotationAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.project = Project.objects.create(
            name='Test Project',
            created_by=self.user
        )
    
    def test_create_annotation(self):
        """Test annotation creation via API"""
        self.client.force_authenticate(user=self.user)
        data = {
            'start_char': 0,
            'end_char': 10,
            'label': 'PERSON',
            'text': 'John Smith'
        }
        response = self.client.post(
            f'/api/documents/{self.document.id}/annotations/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Annotation.objects.count(), 1)
    
    def test_inter_annotator_agreement(self):
        """Test Cohen's kappa calculation"""
        # Create test annotations from two users
        annotations_user1 = ['PERSON', 'ORG', 'PERSON', 'O']
        annotations_user2 = ['PERSON', 'O', 'PERSON', 'O']
        
        kappa_score = calculate_cohen_kappa(annotations_user1, annotations_user2)
        self.assertGreater(kappa_score, 0)
```

### 8.2 Frontend Testing

```javascript
// React component testing
import { render, screen, fireEvent } from '@testing-library/react';
import { AnnotationInterface } from '../components/AnnotationInterface';

describe('AnnotationInterface', () => {
    const mockDocument = {
        id: 1,
        content: 'John Smith works at OpenAI.'
    };
    
    const mockAnnotations = [
        { id: 1, start_char: 0, end_char: 10, label: 'PERSON', text: 'John Smith' }
    ];
    
    test('renders document content', () => {
        render(
            <AnnotationInterface 
                document={mockDocument}
                annotations={mockAnnotations}
                onAnnotate={jest.fn()}
            />
        );
        
        expect(screen.getByText('John Smith works at OpenAI.')).toBeInTheDocument();
    });
    
    test('displays existing annotations', () => {
        render(
            <AnnotationInterface 
                document={mockDocument}
                annotations={mockAnnotations}
                onAnnotate={jest.fn()}
            />
        );
        
        expect(screen.getByText('PERSON')).toBeInTheDocument();
    });
});
```

## 9. Migration and Integration

### 9.1 Data Migration from Existing Tools

```python
# Migration script example for BRAT format
def migrate_from_brat(brat_directory, project_id):
    """Migrate annotations from BRAT format"""
    import os
    
    for filename in os.listdir(brat_directory):
        if filename.endswith('.txt'):
            # Read text file
            text_file = os.path.join(brat_directory, filename)
            ann_file = os.path.join(brat_directory, filename.replace('.txt', '.ann'))
            
            with open(text_file, 'r') as f:
                content = f.read()
            
            # Create document
            document = Document.objects.create(
                project_id=project_id,
                filename=filename,
                content=content
            )
            
            # Read annotations
            if os.path.exists(ann_file):
                with open(ann_file, 'r') as f:
                    for line in f:
                        if line.startswith('T'):  # Text annotation
                            parts = line.strip().split('\t')
                            ann_info = parts[1].split()
                            label = ann_info[0]
                            start_char = int(ann_info[1])
                            end_char = int(ann_info[2])
                            text = parts[2]
                            
                            Annotation.objects.create(
                                document=document,
                                start_char=start_char,
                                end_char=end_char,
                                label=label,
                                text=text
                            )
```

### 9.2 spaCy Integration

```python
# spaCy export functionality
def export_to_spacy_format(project):
    """Export project annotations to spaCy DocBin format"""
    import spacy
    from spacy.tokens import DocBin
    
    nlp = spacy.blank("en")
    doc_bin = DocBin()
    
    for document in project.documents.all():
        doc = nlp(document.content)
        
        # Create entity spans
        entities = []
        for annotation in document.annotations.all():
            span = doc.char_span(
                annotation.start_char, 
                annotation.end_char, 
                label=annotation.label
            )
            if span:
                entities.append(span)
        
        # Set entities
        doc.ents = entities
        doc_bin.add(doc)
    
    return doc_bin.to_bytes()

# spaCy model training integration
def train_spacy_model(project, output_path):
    """Train a spaCy model using project annotations"""
    training_data = export_to_spacy_format(project)
    
    # Save training data
    with open(f"{output_path}/train.spacy", "wb") as f:
        f.write(training_data)
    
    # Create config file
    config = {
        "system": {"gpu_allocator": "pytorch", "seed": 0},
        "nlp": {"lang": "en", "pipeline": ["tok2vec", "ner"]},
        "components": {
            "tok2vec": {"factory": "tok2vec"},
            "ner": {"factory": "ner"}
        },
        "training": {
            "dev_corpus": "corpora.dev",
            "train_corpus": "corpora.train",
            "seed": 0,
            "gpu_allocator": "pytorch",
            "dropout": 0.1,
            "accumulate_gradient": 1,
            "patience": 1600,
            "max_epochs": 0,
            "max_steps": 20000,
            "eval_frequency": 200,
            "frozen_components": [],
            "before_to_disk": None
        }
    }
    
    # Save config and run training
    # Implementation details for spaCy v3 training...
```

This comprehensive technology stack recommendation provides a solid foundation for developing a modern, scalable, and academically-focused text annotation system. The recommendations balance proven technologies with modern development practices, ensuring both reliability and future-proofing for academic research needs.