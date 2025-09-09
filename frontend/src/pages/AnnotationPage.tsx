import React, { useState, useEffect } from 'react';
import { AnnotationProvider } from '../contexts/AnnotationContext';
import AnnotationWorkspace from '../components/annotation/AnnotationWorkspace';
import { TextDocument } from '../types/annotation';

const AnnotationPage: React.FC = () => {
  const [currentDocument, setCurrentDocument] = useState<TextDocument | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Sample document for demo purposes
  useEffect(() => {
    // Simulate loading a document
    setTimeout(() => {
      const sampleDocument: TextDocument = {
        id: 'doc_1',
        title: 'Sample Legal Document - Contract Analysis',
        content: `CONFIDENTIAL EMPLOYMENT AGREEMENT

This Employment Agreement ("Agreement") is entered into as of January 15, 2024, between TechCorp Industries, Inc., a Delaware corporation ("Company"), and Sarah Michelle Johnson ("Employee").

RECITALS

WHEREAS, Company desires to employ Employee as Chief Technology Officer; and

WHEREAS, Employee desires to be employed by Company in such capacity and is willing to enter into this Agreement;

NOW, THEREFORE, in consideration of the mutual covenants contained herein, Company and Employee agree as follows:

1. EMPLOYMENT AND DUTIES

Company hereby employs Employee, and Employee hereby accepts employment with Company, as Chief Technology Officer. Employee shall report directly to the Chief Executive Officer and shall have such authority, duties, and responsibilities as may be assigned by the Board of Directors or Chief Executive Officer from time to time.

Employee agrees to devote Employee's full business time and attention to the affairs of Company and to perform Employee's duties faithfully, diligently, and to the best of Employee's ability. Employee shall not, without the prior written consent of Company, engage in any other business activity that would conflict with Employee's duties hereunder.

2. TERM

This Agreement shall commence on February 1, 2024, and shall continue for a term of three (3) years, unless sooner terminated in accordance with the provisions hereof. The term of this Agreement may be extended by mutual written agreement of the parties.

3. COMPENSATION

As compensation for services rendered hereunder, Company shall pay Employee:

(a) Base Salary: An annual base salary of Two Hundred Fifty Thousand Dollars ($250,000), payable in accordance with Company's standard payroll practices, subject to applicable withholdings and deductions.

(b) Performance Bonus: Employee shall be eligible for an annual performance bonus of up to Fifty Thousand Dollars ($50,000), based on achievement of performance goals to be established annually by the Board of Directors.

(c) Stock Options: Employee shall be granted options to purchase Twenty Thousand (20,000) shares of Company's common stock at an exercise price equal to the fair market value on the grant date, vesting over four (4) years with a one-year cliff.

4. BENEFITS

Employee shall be entitled to participate in all employee benefit plans and programs maintained by Company for its executives, including health insurance, dental insurance, retirement plans, and paid time off, in accordance with the terms of such plans.

5. CONFIDENTIALITY

Employee acknowledges that during the course of employment, Employee will have access to and learn about Confidential Information. "Confidential Information" includes, but is not limited to, technical data, trade secrets, know-how, research, product plans, products, services, customers, customer lists, markets, software, developments, inventions, processes, formulas, technology, designs, drawings, engineering, hardware configuration information, marketing, finances, or other business information disclosed to Employee.

Employee agrees to hold all Confidential Information in strictest confidence and not to disclose such information to any third party without the prior written consent of Company.

6. TERMINATION

This Agreement may be terminated:

(a) By Company for Cause, immediately upon written notice to Employee;
(b) By Company without Cause, upon thirty (30) days' written notice to Employee;
(c) By Employee, upon thirty (30) days' written notice to Company;
(d) Upon Employee's death or permanent disability.

Upon termination of employment for any reason, Employee shall immediately return all Company property, including all documents, materials, and Confidential Information.

7. GOVERNING LAW

This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of laws provisions.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

TECHCORP INDUSTRIES, INC.

By: _________________________
    Robert K. Stevens
    Chief Executive Officer

EMPLOYEE:

_____________________________
Sarah Michelle Johnson`,
        metadata: {
          createdAt: '2024-01-15T10:00:00Z',
          lastModified: '2024-01-15T14:30:00Z',
          documentType: 'employment_contract',
          jurisdiction: 'Delaware',
          practiceArea: 'Employment Law',
        },
        annotations: [
          {
            id: 'ann_1',
            textId: 'doc_1',
            startOffset: 180,
            endOffset: 202,
            text: 'TechCorp Industries, Inc.',
            labels: ['2'], // Organization
            confidence: 0.95,
            notes: 'Delaware corporation - employer entity',
            createdAt: new Date('2024-01-15T11:00:00Z'),
            updatedAt: new Date('2024-01-15T11:00:00Z'),
            createdBy: 'demo_user',
            status: 'validated',
          },
          {
            id: 'ann_2',
            textId: 'doc_1',
            startOffset: 235,
            endOffset: 256,
            text: 'Sarah Michelle Johnson',
            labels: ['1'], // Person
            confidence: 0.98,
            notes: 'Employee party to the contract',
            createdAt: new Date('2024-01-15T11:05:00Z'),
            updatedAt: new Date('2024-01-15T11:05:00Z'),
            createdBy: 'demo_user',
            status: 'validated',
          },
          {
            id: 'ann_3',
            textId: 'doc_1',
            startOffset: 367,
            endOffset: 392,
            text: 'Chief Technology Officer',
            labels: ['5'], // Event (role/position)
            confidence: 0.90,
            notes: 'Job title/position',
            createdAt: new Date('2024-01-15T11:10:00Z'),
            updatedAt: new Date('2024-01-15T11:10:00Z'),
            createdBy: 'demo_user',
            status: 'validated',
          },
          {
            id: 'ann_4',
            textId: 'doc_1',
            startOffset: 1015,
            endOffset: 1032,
            text: 'February 1, 2024',
            labels: ['4'], // Date
            confidence: 1.0,
            notes: 'Employment start date',
            createdAt: new Date('2024-01-15T11:15:00Z'),
            updatedAt: new Date('2024-01-15T11:15:00Z'),
            createdBy: 'demo_user',
            status: 'validated',
          },
          {
            id: 'ann_5',
            textId: 'doc_1',
            startOffset: 1359,
            endOffset: 1396,
            text: 'Two Hundred Fifty Thousand Dollars',
            labels: ['5'], // Event (compensation amount)
            confidence: 0.92,
            notes: 'Annual base salary amount',
            createdAt: new Date('2024-01-15T11:20:00Z'),
            updatedAt: new Date('2024-01-15T11:20:00Z'),
            createdBy: 'demo_user',
            status: 'pending',
          }
        ],
      };

      setCurrentDocument(sampleDocument);
      setIsLoading(false);
    }, 1000);
  }, []);

  const handleDocumentChange = (updatedDocument: TextDocument) => {
    setCurrentDocument(updatedDocument);
    // Here you would typically save to your backend API
    console.log('Document updated:', updatedDocument);
  };

  if (isLoading) {
    return (
      <div className="annotation-page-loading">
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <h2>Loading Document...</h2>
          <p>Preparing annotation workspace</p>
        </div>
      </div>
    );
  }

  if (!currentDocument) {
    return (
      <div className="annotation-page-error">
        <div className="error-content">
          <h2>Document Not Found</h2>
          <p>The requested document could not be loaded.</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  return (
    <AnnotationProvider>
      <div className="annotation-page">
        <AnnotationWorkspace
          document={currentDocument}
          onDocumentChange={handleDocumentChange}
        />
      </div>

      <style jsx>{`
        .annotation-page {
          height: 100vh;
          width: 100vw;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        }

        .annotation-page-loading,
        .annotation-page-error {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100vh;
          background: #f9fafb;
        }

        .loading-content,
        .error-content {
          text-align: center;
          max-width: 400px;
          padding: 40px;
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #e5e7eb;
          border-top: 4px solid #3b82f6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 20px;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .loading-content h2,
        .error-content h2 {
          color: #1f2937;
          margin-bottom: 8px;
          font-size: 24px;
          font-weight: 600;
        }

        .loading-content p,
        .error-content p {
          color: #6b7280;
          margin-bottom: 20px;
        }

        .error-content button {
          background: #3b82f6;
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.2s;
        }

        .error-content button:hover {
          background: #2563eb;
        }

        /* Global styles for the annotation interface */
        :global(body) {
          margin: 0;
          padding: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        }

        :global(*, *::before, *::after) {
          box-sizing: border-box;
        }

        :global(.annotation-highlight) {
          transition: all 0.2s ease;
        }

        :global(.annotation-highlight:hover) {
          transform: translateY(-1px);
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        /* Scrollbar styling */
        :global(.annotations-list::-webkit-scrollbar),
        :global(.text-area::-webkit-scrollbar) {
          width: 8px;
        }

        :global(.annotations-list::-webkit-scrollbar-track),
        :global(.text-area::-webkit-scrollbar-track) {
          background: #f1f1f1;
          border-radius: 4px;
        }

        :global(.annotations-list::-webkit-scrollbar-thumb),
        :global(.text-area::-webkit-scrollbar-thumb) {
          background: #c1c1c1;
          border-radius: 4px;
        }

        :global(.annotations-list::-webkit-scrollbar-thumb:hover),
        :global(.text-area::-webkit-scrollbar-thumb:hover) {
          background: #a1a1a1;
        }

        /* Focus styles for accessibility */
        :global(button:focus),
        :global(input:focus),
        :global(textarea:focus),
        :global(select:focus) {
          outline: 2px solid #3b82f6;
          outline-offset: 2px;
        }
      `}</style>
    </AnnotationProvider>
  );
};

export default AnnotationPage;