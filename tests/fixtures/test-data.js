/**
 * Test Data Fixtures
 * Centralized test data for consistent testing across all test suites
 */

export const testUsers = {
  student: {
    name: 'Alice Student',
    email: 'alice@university.edu',
    password: 'StudentPass123!',
    role: 'student',
    institution: 'Test University',
    profile: {
      major: 'Computer Science',
      year: 3
    }
  },
  
  instructor: {
    name: 'Dr. Bob Professor',
    email: 'bob.prof@university.edu',
    password: 'ProfessorPass123!',
    role: 'instructor',
    institution: 'Test University',
    profile: {
      department: 'Computer Science',
      title: 'Associate Professor'
    }
  },
  
  researcher: {
    name: 'Dr. Carol Researcher',
    email: 'carol.research@university.edu',
    password: 'ResearchPass123!',
    role: 'researcher',
    institution: 'Test University',
    profile: {
      specialization: 'Machine Learning',
      publications: 25
    }
  },
  
  admin: {
    name: 'System Admin',
    email: 'admin@university.edu',
    password: 'AdminPass123!',
    role: 'admin',
    institution: 'Test University',
    permissions: ['manage_users', 'system_config', 'data_export']
  }
};

export const testDocuments = {
  academicPaper: {
    title: 'Machine Learning in Education: A Comprehensive Survey',
    content: `Abstract
    
This paper presents a comprehensive survey of machine learning applications in educational technology. We examine various approaches including personalized learning systems, automated assessment, and intelligent tutoring systems.

Introduction

The integration of machine learning (ML) in education has gained significant momentum over the past decade. Educational institutions worldwide are adopting ML-powered solutions to enhance learning outcomes, streamline administrative processes, and provide personalized educational experiences.

Literature Review

Previous studies have demonstrated the effectiveness of ML in various educational contexts. Smith et al. (2020) showed that personalized learning algorithms improved student performance by 23% on average. Johnson and Brown (2021) explored the use of natural language processing for automated essay grading, achieving 94% accuracy compared to human graders.

Methodology

This survey employed a systematic literature review approach, analyzing 150 peer-reviewed papers published between 2018 and 2023. We categorized applications into five main areas: personalized learning, assessment, tutoring systems, learning analytics, and administrative automation.

Results

Our analysis reveals that personalized learning systems show the most promise, with 78% of studies reporting significant improvement in learning outcomes. Automated assessment tools demonstrated high accuracy rates, while intelligent tutoring systems showed particular effectiveness in STEM subjects.

Conclusion

Machine learning continues to transform education through innovative applications that enhance both teaching and learning processes. Future research should focus on ethical considerations, privacy protection, and ensuring equitable access to these technologies.

References

Smith, A., et al. (2020). Personalized Learning Algorithms in Higher Education. Journal of Educational Technology, 15(3), 45-62.

Johnson, M., & Brown, K. (2021). Automated Essay Grading Using NLP. Computers & Education, 175, 104-118.`,
    type: 'academic_paper',
    metadata: {
      authors: ['Dr. Jane Smith', 'Dr. John Doe'],
      journal: 'Educational Technology Review',
      year: 2023,
      doi: '10.1234/etr.2023.001',
      keywords: ['machine learning', 'education', 'personalized learning'],
      pages: '1-15',
      volume: 28,
      issue: 2
    },
    uploadDate: new Date('2023-01-15'),
    fileSize: 2048576, // 2MB
    mimeType: 'application/pdf'
  },
  
  shortArticle: {
    title: 'Quick Guide to Academic Writing',
    content: `Academic writing requires clarity, precision, and proper citation. Key principles include:

1. Clear thesis statement
2. Logical argument structure  
3. Evidence-based claims
4. Proper citations
5. Formal tone and style

Remember to always cite your sources and maintain academic integrity throughout your work.`,
    type: 'guide',
    metadata: {
      authors: ['Writing Center Staff'],
      category: 'academic_support',
      difficulty: 'beginner',
      estimatedReadTime: 2
    },
    uploadDate: new Date('2023-02-01'),
    fileSize: 4096, // 4KB
    mimeType: 'text/plain'
  }
};

export const testAnnotations = {
  highlight: {
    text: 'machine learning applications in educational technology',
    content: 'Key focus area of this survey - important for literature review',
    startPosition: 142,
    endPosition: 195,
    tags: ['key_concept', 'literature_review'],
    type: 'highlight',
    category: 'concept',
    confidence: 0.95,
    isPublic: true
  },
  
  comment: {
    text: 'Smith et al. (2020) showed that personalized learning algorithms improved student performance by 23%',
    content: 'This statistic is crucial - need to verify the methodology behind this claim. Check if sample size was adequate.',
    startPosition: 856,
    endPosition: 953,
    tags: ['citation', 'needs_verification', 'methodology'],
    type: 'comment',
    category: 'analysis',
    confidence: 0.87,
    isPublic: false,
    priority: 'high'
  },
  
  question: {
    text: 'ethical considerations, privacy protection',
    content: 'What specific ethical frameworks are being referenced here? GDPR compliance? FERPA?',
    startPosition: 2845,
    endPosition: 2883,
    tags: ['ethics', 'privacy', 'compliance', 'question'],
    type: 'question',
    category: 'clarification',
    confidence: 0.78,
    isPublic: true,
    resolved: false
  },
  
  suggestion: {
    text: 'Future research should focus on',
    content: 'Consider adding: accessibility concerns, digital divide implications, and teacher training requirements',
    startPosition: 2823,
    endPosition: 2850,
    tags: ['suggestion', 'future_work', 'accessibility'],
    type: 'suggestion',
    category: 'improvement',
    confidence: 0.92,
    isPublic: true,
    votes: 3
  }
};

export const testProjects = {
  classProject: {
    name: 'CS 401 Research Paper Analysis',
    description: 'Collaborative annotation of machine learning research papers for advanced computer science course',
    type: 'class_assignment',
    settings: {
      allowPublicAnnotations: true,
      requireModeration: false,
      allowAnonymous: false,
      annotationTypes: ['highlight', 'comment', 'question'],
      maxAnnotationsPerUser: 50,
      deadlineDate: new Date('2023-12-15')
    },
    permissions: {
      'instructor': ['read', 'write', 'moderate', 'export'],
      'student': ['read', 'write', 'comment'],
      'ta': ['read', 'write', 'moderate']
    }
  },
  
  researchProject: {
    name: 'AI Ethics Literature Review',
    description: 'Systematic review of AI ethics literature with collaborative annotation',
    type: 'research',
    settings: {
      allowPublicAnnotations: false,
      requireModeration: true,
      allowAnonymous: true,
      annotationTypes: ['highlight', 'comment', 'question', 'suggestion', 'critique'],
      maxAnnotationsPerUser: 100,
      exportFormats: ['csv', 'json', 'pdf']
    },
    permissions: {
      'researcher': ['read', 'write', 'moderate', 'export', 'admin'],
      'collaborator': ['read', 'write', 'comment']
    }
  }
};

export const testExportData = {
  csvFormat: `"ID","Document","User","Type","Text","Content","Tags","Timestamp","Position"
"1","Machine Learning Survey","alice@university.edu","highlight","machine learning applications","Key concept","key_concept,literature_review","2023-03-15T10:30:00Z","142-195"
"2","Machine Learning Survey","bob.prof@university.edu","comment","Smith et al. (2020)","Verify methodology","citation,needs_verification","2023-03-15T11:15:00Z","856-953"`,
  
  jsonFormat: {
    metadata: {
      exportDate: '2023-03-20T14:30:00Z',
      totalAnnotations: 2,
      documentTitle: 'Machine Learning Survey',
      exportedBy: 'admin@university.edu'
    },
    annotations: [
      {
        id: '1',
        type: 'highlight',
        text: 'machine learning applications',
        content: 'Key concept',
        tags: ['key_concept', 'literature_review'],
        user: 'alice@university.edu',
        timestamp: '2023-03-15T10:30:00Z',
        position: { start: 142, end: 195 }
      }
    ]
  }
};

export const testPerformanceData = {
  largeDocument: {
    title: 'Performance Test Document',
    content: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(10000), // ~550KB
    annotations: Array.from({ length: 1000 }, (_, i) => ({
      text: `sample text ${i}`,
      content: `annotation content ${i}`,
      startPosition: i * 50,
      endPosition: (i * 50) + 20,
      tags: [`tag${i % 10}`],
      type: i % 4 === 0 ? 'highlight' : i % 3 === 0 ? 'comment' : 'note'
    }))
  }
};