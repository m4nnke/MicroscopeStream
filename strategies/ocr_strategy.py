import cv2
import numpy as np
import pytesseract
from PIL import Image
from io import BytesIO
from .base_strategy import ProcessingStrategy

class OCRStrategy(ProcessingStrategy):
    def __init__(self):
        """Initialize OCR strategy with default parameters."""
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.5
        self.font_color = (0, 255, 0)  # Green color
        self.line_thickness = 1

    def process_image(self, image: np.ndarray) -> np.ndarray:
        """
        Process image using OCR and overlay detected text.
        
        Args:
            image (np.ndarray): Input image in OpenCV/numpy format
            
        Returns:
            np.ndarray: Image with OCR text overlaid
        """
        # Convert OpenCV image to PIL Image for OCR
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # Extract text using pytesseract
        text = pytesseract.image_to_string(pil_image)
        
        # Create a copy of the image to draw on
        result_image = image.copy()
        
        # Split text into lines and draw each line
        y_position = 30
        for line in text.split('\n'):
            if line.strip():  # Only process non-empty lines
                cv2.putText(
                    result_image,
                    line,
                    (10, y_position),
                    self.font,
                    self.font_scale,
                    self.font_color,
                    self.line_thickness
                )
                y_position += 20
                
        return result_image 