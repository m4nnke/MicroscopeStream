import cv2
import numpy as np
from .base_strategy import ProcessingStrategy
from datetime import datetime

class EdgeDetectionStrategy(ProcessingStrategy):
    """Strategy that performs edge detection on the image."""
    def __init__(self):
        super().__init__('edges')
        self.low_threshold = 50
        self.high_threshold = 150

    def process_image(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, self.low_threshold, self.high_threshold)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

class GrayscaleStrategy(ProcessingStrategy):
    """Strategy that converts the image to grayscale."""
    def __init__(self):
        super().__init__('grayscale')

    def process_image(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

class ThresholdStrategy(ProcessingStrategy):
    """Strategy that applies thresholding to the image."""
    def __init__(self):
        super().__init__('threshold')
        self.threshold = 128
        self.max_value = 255
        self.method = cv2.THRESH_BINARY

    def process_image(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, self.threshold, self.max_value, self.method)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

class ContrastEnhancementStrategy(ProcessingStrategy):
    """Strategy that enhances image contrast using CLAHE."""
    def __init__(self):
        super().__init__('contrast')
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))

    def process_image(self, image: np.ndarray) -> np.ndarray:
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        cl = self.clahe.apply(l)
        
        # Merge channels and convert back to BGR
        enhanced = cv2.merge([cl, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR) 

class TimestampStrategy(ProcessingStrategy):
    """Strategy that adds a timestamp to the image."""
    def __init__(self):
        super().__init__('timestamp')
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 1.0
        self.font_thickness = 2
        self.text_color = (255, 255, 255)  # White color
        self.text_position = (10, 30)  # Top-left corner with some padding

    def process_image(self, image: np.ndarray) -> np.ndarray:
        # Create a copy of the image to avoid modifying the original
        processed_image = image.copy()
        
        # Get current timestamp with milliseconds
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds (3 digits)
        
        # Add timestamp text to the image
        cv2.putText(
            processed_image,
            timestamp,
            self.text_position,
            self.font,
            self.font_scale,
            self.text_color,
            self.font_thickness
        )
        
        return processed_image 