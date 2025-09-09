"""
Unit Tests for Text Processing Utilities

Tests file processing, text cleaning, and statistics calculation.
"""

import pytest
import io
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException, UploadFile

from src.utils.text_processor import (
    process_text_file, process_docx_file, process_pdf_file, 
    process_csv_file, clean_text, calculate_text_stats,
    process_uploaded_file
)


class TestTextFileProcessing:
    """Test cases for text file processing."""

    @pytest.mark.unit
    def test_process_text_file_utf8(self):
        """Test processing UTF-8 text file."""
        content = "This is a test text file with UTF-8 encoding.".encode('utf-8')
        result = process_text_file(content)
        
        assert result == "This is a test text file with UTF-8 encoding."

    @pytest.mark.unit
    def test_process_text_file_unicode(self):
        """Test processing text file with Unicode characters."""
        content = "Test with Unicode: café, naïve, résumé".encode('utf-8')
        result = process_text_file(content)
        
        assert "café" in result
        assert "naïve" in result
        assert "résumé" in result

    @pytest.mark.unit
    def test_process_text_file_latin1_fallback(self):
        """Test fallback to Latin-1 encoding."""
        # Create content that's valid Latin-1 but not UTF-8
        content = bytes([0xE9, 0xE8, 0xE7])  # Latin-1 accented characters
        
        with patch('src.utils.text_processor.content.decode') as mock_decode:
            # First call (UTF-8) raises exception
            mock_decode.side_effect = [UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid'), "test"]
            
            result = process_text_file(content)
            
            # Should try Latin-1 after UTF-8 fails
            assert mock_decode.call_count >= 2

    @pytest.mark.unit
    def test_process_text_file_error_handling(self):
        """Test error handling in text file processing."""
        # Test with None content
        with pytest.raises(AttributeError):
            process_text_file(None)

    @pytest.mark.unit
    def test_process_text_file_empty(self):
        """Test processing empty text file."""
        content = b""
        result = process_text_file(content)
        
        assert result == ""


class TestDocxFileProcessing:
    """Test cases for DOCX file processing."""

    @pytest.mark.unit
    @patch('src.utils.text_processor.docx.Document')
    def test_process_docx_file_paragraphs(self, mock_document):
        """Test processing DOCX file with paragraphs."""
        # Mock document structure
        mock_doc = Mock()
        mock_paragraph1 = Mock()
        mock_paragraph1.text = "First paragraph"
        mock_paragraph2 = Mock()
        mock_paragraph2.text = "Second paragraph"
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        mock_doc.tables = []
        
        mock_document.return_value = mock_doc
        
        content = b"mock docx content"
        result = process_docx_file(content)
        
        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "First paragraph\nSecond paragraph" == result

    @pytest.mark.unit
    @patch('src.utils.text_processor.docx.Document')
    def test_process_docx_file_with_tables(self, mock_document):
        """Test processing DOCX file with tables."""
        # Mock document with table
        mock_doc = Mock()
        mock_doc.paragraphs = []
        
        # Mock table structure
        mock_cell1 = Mock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = Mock()
        mock_cell2.text = "Cell 2"
        mock_row = Mock()
        mock_row.cells = [mock_cell1, mock_cell2]
        mock_table = Mock()
        mock_table.rows = [mock_row]
        mock_doc.tables = [mock_table]
        
        mock_document.return_value = mock_doc
        
        content = b"mock docx content"
        result = process_docx_file(content)
        
        assert "Cell 1 | Cell 2" == result

    @pytest.mark.unit
    @patch('src.utils.text_processor.docx.Document')
    def test_process_docx_file_error(self, mock_document):
        """Test DOCX file processing error handling."""
        mock_document.side_effect = Exception("Invalid DOCX file")
        
        content = b"invalid docx content"
        with pytest.raises(ValueError, match="Failed to process DOCX file"):
            process_docx_file(content)

    @pytest.mark.unit
    @patch('src.utils.text_processor.docx.Document')
    def test_process_docx_file_empty_paragraphs(self, mock_document):
        """Test processing DOCX with empty paragraphs."""
        mock_doc = Mock()
        mock_empty_para = Mock()
        mock_empty_para.text = "   "  # Whitespace only
        mock_valid_para = Mock()
        mock_valid_para.text = "Valid paragraph"
        mock_doc.paragraphs = [mock_empty_para, mock_valid_para]
        mock_doc.tables = []
        
        mock_document.return_value = mock_doc
        
        content = b"mock docx content"
        result = process_docx_file(content)
        
        assert result == "Valid paragraph"


class TestPdfFileProcessing:
    """Test cases for PDF file processing."""

    @pytest.mark.unit
    @patch('src.utils.text_processor.PyPDF2.PdfReader')
    def test_process_pdf_file_success(self, mock_pdf_reader):
        """Test successful PDF processing."""
        # Mock PDF structure
        mock_page = Mock()
        mock_page.extract_text.return_value = "This is PDF page content"
        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        content = b"mock pdf content"
        result = process_pdf_file(content)
        
        assert result == "This is PDF page content"

    @pytest.mark.unit
    @patch('src.utils.text_processor.PyPDF2.PdfReader')
    def test_process_pdf_file_multiple_pages(self, mock_pdf_reader):
        """Test PDF processing with multiple pages."""
        # Mock multiple pages
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Page 2 content"
        mock_reader = Mock()
        mock_reader.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader
        
        content = b"mock pdf content"
        result = process_pdf_file(content)
        
        assert "Page 1 content\nPage 2 content" == result

    @pytest.mark.unit
    @patch('src.utils.text_processor.PyPDF2.PdfReader')
    def test_process_pdf_file_no_text(self, mock_pdf_reader):
        """Test PDF with no extractable text."""
        mock_page = Mock()
        mock_page.extract_text.return_value = ""
        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        content = b"mock pdf content"
        with pytest.raises(ValueError, match="No text could be extracted from PDF"):
            process_pdf_file(content)

    @pytest.mark.unit
    @patch('src.utils.text_processor.PyPDF2.PdfReader')
    def test_process_pdf_file_error(self, mock_pdf_reader):
        """Test PDF processing error handling."""
        mock_pdf_reader.side_effect = Exception("Invalid PDF file")
        
        content = b"invalid pdf content"
        with pytest.raises(ValueError, match="Failed to process PDF file"):
            process_pdf_file(content)


class TestCsvFileProcessing:
    """Test cases for CSV file processing."""

    @pytest.mark.unit
    @patch('src.utils.text_processor.pd.read_csv')
    def test_process_csv_file_success(self, mock_read_csv):
        """Test successful CSV processing."""
        # Mock DataFrame
        mock_df = Mock()
        mock_df.iterrows.return_value = [
            (0, {"Name": "John Doe", "Age": 30, "City": "New York"}),
            (1, {"Name": "Jane Smith", "Age": 25, "City": "Boston"})
        ]
        mock_read_csv.return_value = mock_df
        
        content = b"Name,Age,City\nJohn Doe,30,New York\nJane Smith,25,Boston"
        result = process_csv_file(content)
        
        assert "Name: John Doe" in result
        assert "Age: 30" in result
        assert "City: New York" in result

    @pytest.mark.unit
    @patch('src.utils.text_processor.pd.read_csv')
    def test_process_csv_file_with_na_values(self, mock_read_csv):
        """Test CSV processing with NaN values."""
        import pandas as pd
        
        mock_df = Mock()
        mock_df.iterrows.return_value = [
            (0, {"Name": "John", "Age": pd.NA, "City": "New York"}),
        ]
        mock_read_csv.return_value = mock_df
        
        # Mock pd.notna
        with patch('src.utils.text_processor.pd.notna', side_effect=lambda x: x is not pd.NA):
            content = b"Name,Age,City\nJohn,,New York"
            result = process_csv_file(content)
            
            assert "Name: John" in result
            assert "Age:" not in result  # Should skip NaN values
            assert "City: New York" in result

    @pytest.mark.unit
    @patch('src.utils.text_processor.pd.read_csv')
    def test_process_csv_file_empty(self, mock_read_csv):
        """Test CSV with no valid data."""
        mock_df = Mock()
        mock_df.iterrows.return_value = []
        mock_read_csv.return_value = mock_df
        
        content = b"empty csv content"
        with pytest.raises(ValueError, match="No text data found in CSV file"):
            process_csv_file(content)

    @pytest.mark.unit
    @patch('src.utils.text_processor.pd.read_csv')
    def test_process_csv_file_error(self, mock_read_csv):
        """Test CSV processing error handling."""
        mock_read_csv.side_effect = Exception("Invalid CSV file")
        
        content = b"invalid csv content"
        with pytest.raises(ValueError, match="Failed to process CSV file"):
            process_csv_file(content)


class TestTextCleaning:
    """Test cases for text cleaning functionality."""

    @pytest.mark.unit
    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        text = "  This is a test   text  with extra    spaces.  \n\n  Another line.  \n  "
        result = clean_text(text)
        
        assert result == "This is a test text with extra spaces.\nAnother line."

    @pytest.mark.unit
    def test_clean_text_empty(self):
        """Test cleaning empty text."""
        assert clean_text("") == ""
        assert clean_text(None) == ""
        assert clean_text("   ") == ""

    @pytest.mark.unit
    def test_clean_text_newlines(self):
        """Test text cleaning with multiple newlines."""
        text = "Line 1\n\n\nLine 2\n\n\n\nLine 3"
        result = clean_text(text)
        
        assert result == "Line 1\nLine 2\nLine 3"

    @pytest.mark.unit
    def test_clean_text_tabs_and_spaces(self):
        """Test cleaning text with tabs and spaces."""
        text = "Word1\t\tWord2    Word3\n\tTabbed line   "
        result = clean_text(text)
        
        assert "Word1 Word2 Word3" in result
        assert "Tabbed line" in result


class TestTextStatistics:
    """Test cases for text statistics calculation."""

    @pytest.mark.unit
    def test_calculate_text_stats_basic(self):
        """Test basic text statistics calculation."""
        text = "This is a test. It has two sentences!"
        stats = calculate_text_stats(text)
        
        assert stats["word_count"] == 8
        assert stats["character_count"] == len(text)
        assert stats["sentence_count"] == 2
        assert stats["paragraph_count"] == 1
        assert stats["average_words_per_sentence"] == 4.0

    @pytest.mark.unit
    def test_calculate_text_stats_empty(self):
        """Test statistics for empty text."""
        stats = calculate_text_stats("")
        
        assert stats["word_count"] == 0
        assert stats["character_count"] == 0
        assert stats["sentence_count"] == 0
        assert stats["paragraph_count"] == 0
        assert stats["average_words_per_sentence"] == 0

    @pytest.mark.unit
    def test_calculate_text_stats_multiple_paragraphs(self):
        """Test statistics with multiple paragraphs."""
        text = "First paragraph.\n\nSecond paragraph with more words here.\n\nThird paragraph!"
        stats = calculate_text_stats(text)
        
        assert stats["paragraph_count"] == 3
        assert stats["sentence_count"] == 3
        assert stats["word_count"] > 10

    @pytest.mark.unit
    def test_calculate_text_stats_no_sentences(self):
        """Test statistics for text without sentence endings."""
        text = "This text has no sentence endings"
        stats = calculate_text_stats(text)
        
        assert stats["sentence_count"] == 1  # Should default to 1
        assert stats["word_count"] == 7

    @pytest.mark.unit
    def test_calculate_text_stats_various_punctuation(self):
        """Test sentence counting with various punctuation."""
        text = "Question? Exclamation! Statement. Another statement."
        stats = calculate_text_stats(text)
        
        assert stats["sentence_count"] == 4
        assert stats["word_count"] == 6


class TestFileUploadProcessing:
    """Test cases for upload file processing."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_uploaded_file_txt(self):
        """Test processing uploaded text file."""
        # Mock UploadFile
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.read.return_value = b"Test content"
        mock_file.seek.return_value = None
        
        result = await process_uploaded_file(mock_file, ".txt")
        
        assert result == "Test content"
        mock_file.read.assert_called_once()
        mock_file.seek.assert_called_once_with(0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_uploaded_file_unsupported(self):
        """Test processing unsupported file type."""
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.read.return_value = b"content"
        mock_file.seek.return_value = None
        
        with pytest.raises(HTTPException, match="Failed to process file"):
            await process_uploaded_file(mock_file, ".unknown")

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch('src.utils.text_processor.process_docx_file')
    async def test_process_uploaded_file_docx(self, mock_process_docx):
        """Test processing uploaded DOCX file."""
        mock_process_docx.return_value = "DOCX content"
        
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.read.return_value = b"docx content"
        mock_file.seek.return_value = None
        
        result = await process_uploaded_file(mock_file, ".docx")
        
        assert result == "DOCX content"
        mock_process_docx.assert_called_once_with(b"docx content")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_uploaded_file_error_handling(self):
        """Test error handling in file upload processing."""
        mock_file = AsyncMock(spec=UploadFile)
        mock_file.read.side_effect = Exception("File read error")
        mock_file.seek.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await process_uploaded_file(mock_file, ".txt")
        
        assert exc_info.value.status_code == 400
        assert "Failed to process file" in exc_info.value.detail
        # Should still call seek even after error
        mock_file.seek.assert_called_once_with(0)