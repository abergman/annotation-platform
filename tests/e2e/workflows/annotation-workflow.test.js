/**
 * End-to-End Tests - Annotation Workflow
 * Tests complete user workflows from registration to collaboration
 */

import puppeteer from 'puppeteer';
import { testUsers, testDocuments, testProjects } from '../../fixtures/test-data.js';

describe('End-to-End Annotation Workflow Tests', () => {
  let browser;
  let page;
  let studentPage;
  let instructorPage;

  // Mock application URLs (would be real URLs in production)
  const baseUrl = 'http://localhost:3000';
  const mockUrls = {
    home: `${baseUrl}`,
    login: `${baseUrl}/login`,
    register: `${baseUrl}/register`,
    dashboard: `${baseUrl}/dashboard`,
    document: (id) => `${baseUrl}/document/${id}`,
    project: (id) => `${baseUrl}/project/${id}`,
    profile: `${baseUrl}/profile`
  };

  beforeAll(async () => {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
  });

  afterAll(async () => {
    if (browser) {
      await browser.close();
    }
  });

  beforeEach(async () => {
    page = await browser.newPage();
    
    // Set viewport for consistent testing
    await page.setViewport({ width: 1280, height: 720 });
    
    // Mock API responses for testing
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      if (req.url().includes('/api/')) {
        req.respond(mockApiResponse(req));
      } else {
        req.continue();
      }
    });
  });

  afterEach(async () => {
    if (page && !page.isClosed()) {
      await page.close();
    }
    if (studentPage && !studentPage.isClosed()) {
      await studentPage.close();
    }
    if (instructorPage && !instructorPage.isClosed()) {
      await instructorPage.close();
    }
  });

  // Mock API response helper
  function mockApiResponse(req) {
    const url = req.url();
    const method = req.method();

    // Authentication endpoints
    if (url.includes('/api/auth/login')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            user: { id: '1', ...testUsers.student },
            accessToken: 'mock-jwt-token',
            refreshToken: 'mock-refresh-token'
          }
        })
      };
    }

    if (url.includes('/api/auth/register')) {
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            user: { id: '2', name: 'New User', email: 'new@test.com', role: 'student' },
            accessToken: 'mock-jwt-token'
          }
        })
      };
    }

    // Documents endpoints
    if (url.includes('/api/documents')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: [
            { id: '1', ...testDocuments.academicPaper },
            { id: '2', ...testDocuments.shortArticle }
          ]
        })
      };
    }

    // Annotations endpoints
    if (url.includes('/api/annotations')) {
      if (method === 'POST') {
        return {
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              id: Date.now().toString(),
              ...JSON.parse(req.postData()),
              userId: '1',
              createdAt: new Date().toISOString()
            }
          })
        };
      }

      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: [
            {
              id: '1',
              text: 'Sample annotation',
              content: 'This is a test annotation',
              startPosition: 100,
              endPosition: 120,
              type: 'highlight',
              userId: '1'
            }
          ]
        })
      };
    }

    // Projects endpoints
    if (url.includes('/api/projects')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: [testProjects.classProject]
        })
      };
    }

    // Default response
    return {
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Not found' })
    };
  }

  describe('User Registration and Authentication Workflow', () => {
    it('should complete full user registration flow', async () => {
      // Navigate to registration page
      await page.goto(mockUrls.register);
      await page.waitForSelector('[data-testid=\"register-form\"]', { timeout: 5000 });

      // Fill registration form
      await page.type('[data-testid=\"name-input\"]', 'Test Student');
      await page.type('[data-testid=\"email-input\"]', 'test.student@university.edu');
      await page.type('[data-testid=\"password-input\"]', 'SecurePassword123!');
      await page.select('[data-testid=\"role-select\"]', 'student');

      // Submit form
      await page.click('[data-testid=\"register-button\"]');

      // Wait for registration success
      await page.waitForSelector('[data-testid=\"success-message\"]', { timeout: 10000 });

      // Verify redirect to dashboard
      await page.waitForNavigation();
      expect(page.url()).toBe(mockUrls.dashboard);

      // Verify user is logged in
      const userInfo = await page.$('[data-testid=\"user-info\"]');
      expect(userInfo).not.toBeNull();
    });

    it('should handle registration validation errors', async () => {
      await page.goto(mockUrls.register);
      await page.waitForSelector('[data-testid=\"register-form\"]');

      // Submit form without required fields
      await page.click('[data-testid=\"register-button\"]');

      // Check for validation errors
      const nameError = await page.$('[data-testid=\"name-error\"]');
      const emailError = await page.$('[data-testid=\"email-error\"]');
      const passwordError = await page.$('[data-testid=\"password-error\"]');

      expect(nameError).not.toBeNull();
      expect(emailError).not.toBeNull();
      expect(passwordError).not.toBeNull();
    });

    it('should complete login flow', async () => {
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');

      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');

      await page.waitForNavigation();
      expect(page.url()).toBe(mockUrls.dashboard);
    });

    it('should handle login validation errors', async () => {
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');

      // Try login with invalid credentials
      await page.type('[data-testid=\"email-input\"]', 'invalid@email.com');
      await page.type('[data-testid=\"password-input\"]', 'wrongpassword');
      await page.click('[data-testid=\"login-button\"]');

      // Check for error message
      const errorMessage = await page.waitForSelector('[data-testid=\"error-message\"]');
      expect(errorMessage).not.toBeNull();

      const errorText = await page.evaluate(el => el.textContent, errorMessage);
      expect(errorText).toContain('Invalid credentials');
    });
  });

  describe('Document Upload and Management Workflow', () => {
    beforeEach(async () => {
      // Login first
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();
    });

    it('should upload a document successfully', async () => {
      // Navigate to document upload
      await page.click('[data-testid=\"upload-document-button\"]');
      await page.waitForSelector('[data-testid=\"upload-modal\"]');

      // Fill document information
      await page.type('[data-testid=\"document-title\"]', 'Test Academic Paper');
      await page.type('[data-testid=\"document-description\"]', 'A sample paper for testing');

      // Simulate file upload
      const fileInput = await page.$('[data-testid=\"file-input\"]');
      await fileInput.uploadFile('tests/fixtures/sample-document.pdf');

      // Submit upload
      await page.click('[data-testid=\"upload-submit\"]');

      // Wait for upload success
      await page.waitForSelector('[data-testid=\"upload-success\"]', { timeout: 15000 });

      // Verify document appears in list
      await page.waitForSelector('[data-testid=\"document-list\"]');
      const documentTitles = await page.$$eval('[data-testid=\"document-title\"]', 
        elements => elements.map(el => el.textContent)
      );
      expect(documentTitles).toContain('Test Academic Paper');
    });

    it('should validate document upload requirements', async () => {
      await page.click('[data-testid=\"upload-document-button\"]');
      await page.waitForSelector('[data-testid=\"upload-modal\"]');

      // Try to submit without required fields
      await page.click('[data-testid=\"upload-submit\"]');

      // Check validation errors
      const titleError = await page.$('[data-testid=\"title-error\"]');
      const fileError = await page.$('[data-testid=\"file-error\"]');

      expect(titleError).not.toBeNull();
      expect(fileError).not.toBeNull();
    });
  });

  describe('Annotation Creation and Management Workflow', () => {
    beforeEach(async () => {
      // Login and navigate to document
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();
      
      // Go to document view
      await page.goto(mockUrls.document('1'));
      await page.waitForSelector('[data-testid=\"document-viewer\"]');
    });

    it('should create a highlight annotation', async () => {
      // Select text in document
      await page.evaluate(() => {
        const textNode = document.querySelector('[data-testid=\"document-content\"]').firstChild;
        const range = document.createRange();
        range.setStart(textNode, 10);
        range.setEnd(textNode, 30);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      });

      // Click highlight button
      await page.click('[data-testid=\"highlight-button\"]');

      // Fill annotation form
      await page.waitForSelector('[data-testid=\"annotation-form\"]');
      await page.type('[data-testid=\"annotation-content\"]', 'This is an important concept');
      await page.click('[data-testid=\"tag-input\"]');
      await page.type('[data-testid=\"tag-input\"]', 'important');
      await page.keyboard.press('Enter');

      // Submit annotation
      await page.click('[data-testid=\"save-annotation\"]');

      // Verify annotation is created
      await page.waitForSelector('[data-testid=\"annotation-highlight\"]');
      const highlights = await page.$$('[data-testid=\"annotation-highlight\"]');
      expect(highlights.length).toBeGreaterThan(0);
    });

    it('should create a comment annotation', async () => {
      // Select text
      await page.evaluate(() => {
        const textNode = document.querySelector('[data-testid=\"document-content\"]').firstChild;
        const range = document.createRange();
        range.setStart(textNode, 50);
        range.setEnd(textNode, 80);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      });

      // Click comment button
      await page.click('[data-testid=\"comment-button\"]');

      // Fill comment form
      await page.waitForSelector('[data-testid=\"annotation-form\"]');
      await page.type('[data-testid=\"annotation-content\"]', 'This section needs clarification. The methodology is unclear.');
      await page.select('[data-testid=\"annotation-type\"]', 'comment');

      // Submit annotation
      await page.click('[data-testid=\"save-annotation\"]');

      // Verify comment is created
      await page.waitForSelector('[data-testid=\"annotation-comment\"]');
      const comments = await page.$$('[data-testid=\"annotation-comment\"]');
      expect(comments.length).toBeGreaterThan(0);
    });

    it('should edit an existing annotation', async () => {
      // First create an annotation
      await page.evaluate(() => {
        const textNode = document.querySelector('[data-testid=\"document-content\"]').firstChild;
        const range = document.createRange();
        range.setStart(textNode, 10);
        range.setEnd(textNode, 30);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      });

      await page.click('[data-testid=\"highlight-button\"]');
      await page.waitForSelector('[data-testid=\"annotation-form\"]');
      await page.type('[data-testid=\"annotation-content\"]', 'Original content');
      await page.click('[data-testid=\"save-annotation\"]');
      await page.waitForSelector('[data-testid=\"annotation-highlight\"]');

      // Edit the annotation
      await page.click('[data-testid=\"annotation-highlight\"]');
      await page.click('[data-testid=\"edit-annotation\"]');

      // Update content
      await page.click('[data-testid=\"annotation-content\"]', { clickCount: 3 });
      await page.type('[data-testid=\"annotation-content\"]', 'Updated annotation content');
      await page.click('[data-testid=\"save-annotation\"]');

      // Verify update
      await page.waitForTimeout(1000);
      await page.click('[data-testid=\"annotation-highlight\"]');
      const content = await page.$eval('[data-testid=\"annotation-content\"]', el => el.value);
      expect(content).toBe('Updated annotation content');
    });

    it('should delete an annotation', async () => {
      // Create annotation first
      await page.evaluate(() => {
        const textNode = document.querySelector('[data-testid=\"document-content\"]').firstChild;
        const range = document.createRange();
        range.setStart(textNode, 10);
        range.setEnd(textNode, 30);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      });

      await page.click('[data-testid=\"highlight-button\"]');
      await page.waitForSelector('[data-testid=\"annotation-form\"]');
      await page.type('[data-testid=\"annotation-content\"]', 'To be deleted');
      await page.click('[data-testid=\"save-annotation\"]');
      await page.waitForSelector('[data-testid=\"annotation-highlight\"]');

      // Delete annotation
      await page.click('[data-testid=\"annotation-highlight\"]');
      await page.click('[data-testid=\"delete-annotation\"]');

      // Confirm deletion
      await page.click('[data-testid=\"confirm-delete\"]');

      // Verify deletion
      await page.waitForTimeout(1000);
      const highlights = await page.$$('[data-testid=\"annotation-highlight\"]');
      expect(highlights.length).toBe(0);
    });
  });

  describe('Collaboration Workflow', () => {
    it('should enable multi-user collaboration', async () => {
      // Set up two browser contexts for different users
      studentPage = await browser.newPage();
      instructorPage = await browser.newPage();

      await studentPage.setViewport({ width: 1280, height: 720 });
      await instructorPage.setViewport({ width: 1280, height: 720 });

      // Set up request interception for both pages
      await studentPage.setRequestInterception(true);
      await instructorPage.setRequestInterception(true);

      studentPage.on('request', (req) => {
        if (req.url().includes('/api/')) {
          req.respond(mockApiResponse(req));
        } else {
          req.continue();
        }
      });

      instructorPage.on('request', (req) => {
        if (req.url().includes('/api/')) {
          req.respond(mockApiResponse(req));
        } else {
          req.continue();
        }
      });

      // Login as student
      await studentPage.goto(mockUrls.login);
      await studentPage.waitForSelector('[data-testid=\"login-form\"]');
      await studentPage.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await studentPage.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await studentPage.click('[data-testid=\"login-button\"]');
      await studentPage.waitForNavigation();

      // Login as instructor
      await instructorPage.goto(mockUrls.login);
      await instructorPage.waitForSelector('[data-testid=\"login-form\"]');
      await instructorPage.type('[data-testid=\"email-input\"]', testUsers.instructor.email);
      await instructorPage.type('[data-testid=\"password-input\"]', testUsers.instructor.password);
      await instructorPage.click('[data-testid=\"login-button\"]');
      await instructorPage.waitForNavigation();

      // Both navigate to same document
      await studentPage.goto(mockUrls.document('1'));
      await instructorPage.goto(mockUrls.document('1'));

      await studentPage.waitForSelector('[data-testid=\"document-viewer\"]');
      await instructorPage.waitForSelector('[data-testid=\"document-viewer\"]');

      // Student creates annotation
      await studentPage.evaluate(() => {
        const textNode = document.querySelector('[data-testid=\"document-content\"]').firstChild;
        const range = document.createRange();
        range.setStart(textNode, 10);
        range.setEnd(textNode, 30);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      });

      await studentPage.click('[data-testid=\"highlight-button\"]');
      await studentPage.waitForSelector('[data-testid=\"annotation-form\"]');
      await studentPage.type('[data-testid=\"annotation-content\"]', 'Student annotation');
      await studentPage.click('[data-testid=\"save-annotation\"]');
      await studentPage.waitForSelector('[data-testid=\"annotation-highlight\"]');

      // Instructor should see the annotation (simulated real-time update)
      await instructorPage.reload();
      await instructorPage.waitForSelector('[data-testid=\"document-viewer\"]');
      await instructorPage.waitForSelector('[data-testid=\"annotation-highlight\"]');

      // Instructor replies to annotation
      await instructorPage.click('[data-testid=\"annotation-highlight\"]');
      await instructorPage.click('[data-testid=\"reply-button\"]');
      await instructorPage.type('[data-testid=\"reply-content\"]', 'Good observation! Can you elaborate?');
      await instructorPage.click('[data-testid=\"submit-reply\"]');

      // Verify collaboration features work
      const replies = await instructorPage.$$('[data-testid=\"annotation-reply\"]');
      expect(replies.length).toBeGreaterThan(0);
    });

    it('should handle permission-based access', async () => {
      // Login as student
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();

      // Try to access instructor-only features
      await page.goto(mockUrls.project('1'));
      await page.waitForSelector('[data-testid=\"project-view\"]');

      // Student should not see moderation buttons
      const moderateButtons = await page.$$('[data-testid=\"moderate-annotation\"]');
      expect(moderateButtons.length).toBe(0);

      // Student should not see export buttons
      const exportButtons = await page.$$('[data-testid=\"export-annotations\"]');
      expect(exportButtons.length).toBe(0);
    });
  });

  describe('Data Export Workflow', () => {
    beforeEach(async () => {
      // Login as instructor (has export permissions)
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.instructor.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.instructor.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();
    });

    it('should export annotations in CSV format', async () => {
      await page.goto(mockUrls.project('1'));
      await page.waitForSelector('[data-testid=\"project-view\"]');

      // Click export button
      await page.click('[data-testid=\"export-annotations\"]');
      await page.waitForSelector('[data-testid=\"export-modal\"]');

      // Select CSV format
      await page.select('[data-testid=\"export-format\"]', 'csv');
      await page.click('[data-testid=\"export-submit\"]');

      // Wait for download (simulated)
      await page.waitForSelector('[data-testid=\"export-success\"]');

      const successMessage = await page.$eval('[data-testid=\"export-success\"]', el => el.textContent);
      expect(successMessage).toContain('CSV export completed');
    });

    it('should export annotations in JSON format', async () => {
      await page.goto(mockUrls.project('1'));
      await page.waitForSelector('[data-testid=\"project-view\"]');

      await page.click('[data-testid=\"export-annotations\"]');
      await page.waitForSelector('[data-testid=\"export-modal\"]');

      await page.select('[data-testid=\"export-format\"]', 'json');
      await page.click('[data-testid=\"export-submit\"]');

      await page.waitForSelector('[data-testid=\"export-success\"]');

      const successMessage = await page.$eval('[data-testid=\"export-success\"]', el => el.textContent);
      expect(successMessage).toContain('JSON export completed');
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle network errors gracefully', async () => {
      // Simulate network error
      await page.setOfflineMode(true);

      await page.goto(mockUrls.dashboard);

      // Should show offline message
      await page.waitForSelector('[data-testid=\"offline-notice\"]', { timeout: 10000 });
      const offlineMessage = await page.$eval('[data-testid=\"offline-notice\"]', el => el.textContent);
      expect(offlineMessage).toContain('offline');

      // Restore connection
      await page.setOfflineMode(false);
      await page.reload();

      // Offline notice should disappear
      const offlineNotice = await page.$('[data-testid=\"offline-notice\"]');
      expect(offlineNotice).toBeNull();
    });

    it('should handle session expiration', async () => {
      // Login first
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();

      // Simulate token expiration by intercepting requests
      await page.setRequestInterception(true);
      page.on('request', (req) => {
        if (req.url().includes('/api/')) {
          req.respond({
            status: 401,
            contentType: 'application/json',
            body: JSON.stringify({ error: 'Token expired' })
          });
        } else {
          req.continue();
        }
      });

      // Try to perform an action
      await page.click('[data-testid=\"upload-document-button\"]');

      // Should redirect to login
      await page.waitForNavigation();
      expect(page.url()).toBe(mockUrls.login);
    });

    it('should handle large document loading', async () => {
      await page.goto(mockUrls.login);
      await page.waitForSelector('[data-testid=\"login-form\"]');
      await page.type('[data-testid=\"email-input\"]', testUsers.student.email);
      await page.type('[data-testid=\"password-input\"]', testUsers.student.password);
      await page.click('[data-testid=\"login-button\"]');
      await page.waitForNavigation();

      // Navigate to large document
      await page.goto(mockUrls.document('large-doc'));

      // Should show loading indicator
      const loadingIndicator = await page.waitForSelector('[data-testid=\"document-loading\"]');
      expect(loadingIndicator).not.toBeNull();

      // Should eventually load document
      await page.waitForSelector('[data-testid=\"document-content\"]', { timeout: 30000 });
      
      // Loading indicator should disappear
      const loadingAfter = await page.$('[data-testid=\"document-loading\"]');
      expect(loadingAfter).toBeNull();
    });
  });
});