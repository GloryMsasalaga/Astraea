from celery import shared_task
from django.utils import timezone
from .models import Document, ExtractedField, ProcessingJob
import logging
import os
import re
from decimal import Decimal
from datetime import datetime
import tempfile

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_document_ocr(self, document_id):
    """Process document with OCR and extract text"""
    
    try:
        document = Document.objects.get(id=document_id)
        job = ProcessingJob.objects.create(
            document=document,
            job_type='ocr',
            status='in_progress',
            task_id=self.request.id
        )
        job.started_at = timezone.now()
        job.save()
        
        # Update document status
        document.status = 'processing'
        document.save()
        
        # Perform OCR based on file type
        if document.file_extension.lower() == '.pdf':
            ocr_text = extract_text_from_pdf(document.file.path)
        else:
            ocr_text = extract_text_from_image(document.file.path)
        
        # If OCR fails or returns empty text, provide a placeholder
        if not ocr_text or len(ocr_text.strip()) < 5:
            ocr_text = f"Document processed on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}. OCR libraries not available or text extraction failed."
            document.confidence_score = 0.1  # Low confidence for placeholder text
        else:
            document.confidence_score = 0.85  # Normal confidence score
        
        # Update progress
        job.progress_percentage = 50
        job.save()
        
        # Store OCR results
        document.ocr_text = ocr_text
        document.save()
        
        # Update progress
        job.progress_percentage = 75
        job.save()
        
        # Extract fields from OCR text
        extract_fields_from_text.delay(document_id)
        
        # Complete job
        job.status = 'completed'
        job.progress_percentage = 100
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(f"OCR processing completed for document {document_id}")
        return {"status": "success", "document_id": str(document_id)}
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {"status": "error", "message": "Document not found"}
    
    except Exception as e:
        logger.error(f"OCR processing failed for document {document_id}: {str(e)}")
        
        # Update job status
        if 'job' in locals():
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()
        
        # Update document status
        if 'document' in locals():
            document.status = 'failed'
            document.save()
        
        return {"status": "error", "message": str(e)}


@shared_task(bind=True)
def extract_fields_from_text(self, document_id):
    """Extract structured fields from OCR text"""
    
    try:
        document = Document.objects.get(id=document_id)
        job = ProcessingJob.objects.create(
            document=document,
            job_type='field_extraction',
            status='in_progress',
            task_id=self.request.id
        )
        job.started_at = timezone.now()
        job.save()
        
        ocr_text = document.ocr_text
        if not ocr_text:
            raise ValueError("No OCR text available for field extraction")
        
        # Extract fields using regex patterns
        extracted_fields = []
        
        # Extract dates
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
            r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b'
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, ocr_text, re.IGNORECASE)
            for match in matches:
                extracted_fields.append({
                    'field_type': 'date',
                    'field_name': 'Date',
                    'field_value': match.group(1),
                    'confidence_score': 0.8
                })
        
        # Extract amounts
        amount_patterns = [
            r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*USD',
            r'Total:?\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'Amount:?\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in amount_patterns:
            matches = re.finditer(pattern, ocr_text, re.IGNORECASE)
            for match in matches:
                extracted_fields.append({
                    'field_type': 'amount',
                    'field_name': 'Amount',
                    'field_value': match.group(1),
                    'confidence_score': 0.85
                })
        
        # Extract invoice numbers
        invoice_patterns = [
            r'Invoice\s*#?:?\s*([A-Z0-9\-]+)',
            r'INV\s*#?:?\s*([A-Z0-9\-]+)',
            r'Receipt\s*#?:?\s*([A-Z0-9\-]+)'
        ]
        
        for pattern in invoice_patterns:
            matches = re.finditer(pattern, ocr_text, re.IGNORECASE)
            for match in matches:
                extracted_fields.append({
                    'field_type': 'invoice_number',
                    'field_name': 'Invoice Number',
                    'field_value': match.group(1),
                    'confidence_score': 0.9
                })
        
        # Extract vendor/company names (basic pattern)
        vendor_patterns = [
            r'(?:From|To|Bill To|Vendor):?\s*([A-Za-z\s&.,]+?)(?:\n|$)',
            r'^([A-Z][A-Za-z\s&.,]+(?:Inc|LLC|Corp|Company|Co\.))',
        ]
        
        for pattern in vendor_patterns:
            matches = re.finditer(pattern, ocr_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                vendor_name = match.group(1).strip()
                if len(vendor_name) > 3:  # Filter out very short matches
                    extracted_fields.append({
                        'field_type': 'vendor',
                        'field_name': 'Vendor',
                        'field_value': vendor_name,
                        'confidence_score': 0.7
                    })
        
        # Save extracted fields to database
        field_objects = []
        for field_data in extracted_fields:
            field_obj = ExtractedField(
                document=document,
                field_type=field_data['field_type'],
                field_name=field_data['field_name'],
                field_value=field_data['field_value'],
                confidence_score=field_data['confidence_score']
            )
            field_objects.append(field_obj)
        
        # Bulk create fields
        if field_objects:
            ExtractedField.objects.bulk_create(field_objects)
        
        # Update job progress
        job.progress_percentage = 100
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()
        
        # Update document status
        document.status = 'completed'
        document.processed_at = timezone.now()
        document.save()
        
        logger.info(f"Field extraction completed for document {document_id}. Extracted {len(field_objects)} fields.")
        return {
            "status": "success", 
            "document_id": str(document_id),
            "fields_extracted": len(field_objects)
        }
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {"status": "error", "message": "Document not found"}
    
    except Exception as e:
        logger.error(f"Field extraction failed for document {document_id}: {str(e)}")
        
        # Update job status
        if 'job' in locals():
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()
        
        # Update document status
        if 'document' in locals():
            document.status = 'failed'
            document.save()
        
        return {"status": "error", "message": str(e)}


def extract_text_from_pdf(file_path):
    """Extract text from PDF using pytesseract (for image-based PDFs) or PyPDF2"""
    
    try:
        # First try to extract text directly from PDF
        try:
            import PyPDF2
        except ImportError:
            logger.warning("PyPDF2 not installed. Falling back to OCR.")
            return extract_text_from_pdf_with_ocr(file_path)
        
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        # If direct extraction yields minimal text, use OCR
        if len(text.strip()) < 50:
            return extract_text_from_pdf_with_ocr(file_path)
        
        return text
        
    except Exception as e:
        logger.warning(f"Direct PDF text extraction failed: {e}. Falling back to OCR.")
        return extract_text_from_pdf_with_ocr(file_path)


def extract_text_from_pdf_with_ocr(file_path):
    """Extract text from PDF using OCR (for image-based PDFs)"""
    
    try:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Cannot perform OCR on PDF.")
            return ""
            
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.error("pytesseract or PIL not installed. Cannot perform OCR.")
            return ""
        
        text = ""
        pdf_document = fitz.open(file_path)
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # Convert page to image
            pix = page.get_pixmap()
            img_data = pix.tobytes("ppm")
            
            # Create PIL Image from bytes
            with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as temp_file:
                temp_file.write(img_data)
                temp_file.flush()
                
                # Extract text using OCR
                page_text = pytesseract.image_to_string(Image.open(temp_file.name))
                text += page_text + "\n"
                
                # Clean up temp file
                os.unlink(temp_file.name)
        
        pdf_document.close()
        return text
        
    except Exception as e:
        logger.error(f"OCR PDF extraction failed: {e}")
        return ""


def extract_text_from_image(file_path):
    """Extract text from image using pytesseract"""
    
    try:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.error("pytesseract or PIL not installed. Cannot perform OCR on images.")
            return ""
        
        # Open image and extract text
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        
        return text
        
    except Exception as e:
        logger.error(f"Image OCR extraction failed: {e}")
        return ""
