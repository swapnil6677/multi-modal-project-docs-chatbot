"""
File processing utilities for document handling
"""

import os
import hashlib
import logging
from typing import List, Tuple
from PyPDF2 import PdfReader
from PIL import Image
import google.generativeai as genai
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles file upload and processing operations"""
    
    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
        
        # Create upload folder if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        
        # Initialize Google AI for image processing
        from config import Config
        if Config.GOOGLE_API_KEY:
            genai.configure(api_key=Config.GOOGLE_API_KEY)
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def save_file(self, file: FileStorage) -> str:
        """Save uploaded file and return the file path"""
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(self.upload_folder, filename)
            file.save(file_path)
            logger.info(f"File saved: {file_path}")
            return file_path
        else:
            raise ValueError("Invalid file type or no file provided")
    
    def extract_text_from_pdf(self, pdf_file: FileStorage) -> Tuple[str, int]:
        """Extract text from PDF file and return text with page count"""
        logger.info(f"Extracting text from PDF: {pdf_file.filename}")
        
        try:
            pdf_file.seek(0)  # Reset file pointer
            reader = PdfReader(pdf_file)
            text = ""
            page_count = len(reader.pages)
            
            for page_num, page in enumerate(reader.pages):
                content = page.extract_text() or ""
                text += content
                logger.debug(f"Extracted text from page {page_num + 1}")
            
            logger.info(f"Total text length: {len(text)} characters from {page_count} pages")
            return text, page_count
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def extract_text_from_image(self, image_file: FileStorage) -> Tuple[str, int]:
        """Extract text from image file using Google Gemini Vision and return text with page count (1)"""
        logger.info(f"Extracting text from image: {image_file.filename}")
        
        try:
            # Reset file pointer and open image
            image_file.seek(0)
            image = Image.open(image_file)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            # Use Gemini Vision to extract text
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = """Please extract all text from this image. 
            Provide only the text content without any additional commentary or formatting.
            If there's no readable text, respond with 'No text found in image.'"""
            
            response = model.generate_content([prompt, image])
            text = response.text if response.text else "No text found in image."
            
            logger.info(f"Extracted text from image: {len(text)} characters")
            return text, 1  # Images are considered as 1 "page"
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            raise
    
    def process_file(self, file: FileStorage) -> Tuple[str, int]:
        """Process file based on its type and return text with page count"""
        filename = file.filename.lower()
        
        if filename.endswith('.pdf'):
            return self.extract_text_from_pdf(file)
        elif filename.endswith(('.jpg', '.jpeg', '.png')):
            return self.extract_text_from_image(file)
        else:
            raise ValueError(f"Unsupported file type: {filename}")
    
    def calculate_file_hash(self, text: str) -> str:
        """Calculate MD5 hash of text content for deduplication"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file from filesystem"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> dict:
        """Get file information"""
        try:
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                return {
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'created': stat.st_ctime
                }
            return None
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None
