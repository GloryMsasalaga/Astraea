from django.core.management.base import BaseCommand
from documents.tasks import extract_text_from_pdf, extract_text_from_image
import tempfile
import os

class Command(BaseCommand):
    help = 'Test OCR functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing OCR libraries...'))
        
        # Test import availability
        try:
            import PyPDF2
            self.stdout.write('✓ PyPDF2 imported successfully')
        except ImportError as e:
            self.stdout.write(f'✗ PyPDF2 import failed: {e}')
        
        try:
            import fitz
            self.stdout.write('✓ PyMuPDF (fitz) imported successfully')
        except ImportError as e:
            self.stdout.write(f'✗ PyMuPDF import failed: {e}')
        
        try:
            import pytesseract
            from PIL import Image
            self.stdout.write('✓ pytesseract and PIL imported successfully')
        except ImportError as e:
            self.stdout.write(f'✗ pytesseract/PIL import failed: {e}')
        
        # Test basic functionality
        try:
            # Create a dummy text file to simulate document processing
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write("Test document content for OCR testing")
                temp_file.flush()
                
                self.stdout.write(f'✓ Created test file: {temp_file.name}')
                
                # Clean up
                os.unlink(temp_file.name)
                self.stdout.write('✓ Test file cleaned up')
                
        except Exception as e:
            self.stdout.write(f'✗ File operations failed: {e}')
        
        self.stdout.write(self.style.SUCCESS('OCR library test completed!'))
