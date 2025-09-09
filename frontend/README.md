# Text Annotation System - Frontend

A modern React-based frontend for the Text Annotation System, built with TypeScript, Tailwind CSS, and designed for academic research workflows.

## Features

- **Authentication System**: Secure JWT-based authentication with login/register
- **Project Management**: Create and manage annotation projects
- **Text Annotation**: Interactive text highlighting and labeling interface
- **Label Management**: Hierarchical label system with customization
- **Multi-user Support**: Collaborative annotation workflows
- **Export Functionality**: Export annotations in multiple formats (JSON, CSV, XLSX, XML)
- **Responsive Design**: Mobile-friendly interface
- **Real-time Updates**: Live collaboration features

## Technology Stack

- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS with Headless UI components
- **Routing**: React Router v6
- **HTTP Client**: Axios with interceptors
- **State Management**: React Context API + useReducer
- **Authentication**: JWT tokens with refresh mechanism
- **Build Tool**: Vite for fast development and building
- **Development**: ESLint + Prettier for code quality

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── auth/           # Authentication components
│   │   ├── common/         # Shared components
│   │   ├── projects/       # Project management components
│   │   ├── texts/          # Text management components
│   │   ├── annotations/    # Annotation workspace components
│   │   ├── labels/         # Label management components
│   │   └── export/         # Export functionality components
│   ├── pages/              # Page components
│   ├── contexts/           # React contexts
│   ├── hooks/              # Custom hooks
│   ├── services/           # API services
│   ├── types/              # TypeScript type definitions
│   └── utils/              # Utility functions
├── public/                 # Static assets
└── package.json           # Dependencies and scripts
```

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Backend API server running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Run type checking
npm run type-check
```

### Environment Variables

Create a `.env` file in the frontend directory:

```
VITE_API_BASE_URL=http://localhost:8000
```

## API Integration

The frontend communicates with the FastAPI backend through:

- **Authentication**: `/api/auth/*` endpoints
- **Projects**: `/api/projects/*` endpoints
- **Texts**: `/api/texts/*` endpoints
- **Annotations**: `/api/annotations/*` endpoints
- **Labels**: `/api/labels/*` endpoints
- **Export**: `/api/export/*` endpoints

## Key Components

### Authentication Flow
- `AuthContext` manages authentication state
- `LoginForm` and `RegisterForm` handle user authentication
- Protected routes ensure secure access

### Project Management
- `ProjectList` displays available projects
- `ProjectForm` handles project creation/editing
- `ProjectDashboard` shows project statistics

### Annotation Workspace
- `TextHighlighter` handles text selection and highlighting
- `AnnotationForm` creates and edits annotations
- `LabelManager` manages annotation categories

## State Management

The application uses React Context API for state management:

- **AuthContext**: User authentication and profile data
- **ProjectContext**: Current project state and operations
- **NotificationContext**: Toast notifications and error handling

## Styling

The application uses Tailwind CSS with:

- Custom design system with consistent colors and spacing
- Responsive breakpoints for mobile-first design
- Component utilities for buttons, cards, and forms
- Accessibility features with ARIA labels and keyboard navigation

## Development Status

### ✅ Completed
- Project structure and configuration
- Authentication system (login/register)
- API service layer with TypeScript types
- Main dashboard layout
- Basic routing and navigation
- Responsive design foundation

### 🚧 In Development
- Project management interface
- Text annotation workspace
- Label management system
- Export functionality
- User profile management

### 📋 Planned Features
- Real-time collaboration
- Advanced text highlighting
- Annotation validation workflow
- Inter-annotator agreement metrics
- Batch operations
- Advanced search and filtering

## Contributing

1. Follow the established code style and TypeScript conventions
2. Use the existing component patterns and utilities
3. Ensure responsive design across all screen sizes
4. Add proper error handling and loading states
5. Include accessibility features (ARIA labels, keyboard navigation)

## Build and Deployment

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

The built files will be in the `dist` directory, ready for deployment to any static hosting service.