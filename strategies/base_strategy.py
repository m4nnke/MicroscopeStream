from abc import ABC, abstractmethod
import numpy as np

class ImageProcessingStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process_image(self, image: np.ndarray) -> np.ndarray:
        """
        Process the input image according to the strategy.
        
        Args:
            image (np.ndarray): Input image in OpenCV/numpy format
            
        Returns:
            np.ndarray: Processed image
        """
        pass

class NoOpStrategy(ImageProcessingStrategy):
    """Strategy that performs no processing on the image."""
    def __init__(self):
        super().__init__('none')

    def process_image(self, image: np.ndarray) -> np.ndarray:
        return image 