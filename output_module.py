from abc import ABC, abstractmethod
import threading
import queue
import time
from typing import Optional, TypeVar
from strategies.base_strategy import ImageProcessingStrategy, NoOpStrategy

# Generic type for ImageProcessingStrategy subclasses
StrategyType = TypeVar('StrategyType', bound=ImageProcessingStrategy)

class OutputModule(ABC):
    """Base class for all output modules (streaming, recording, timelapse)."""
    
    def __init__(self, name: str, max_queue_size: int = 300):
        self.name = name
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_frame = None
        self.fps = 10  # Default FPS
        self.frame_interval = 1.0 / self.fps  # Time between frames
        self.last_frame_time = 0
        self.processing_strategy: Optional[ImageProcessingStrategy] = None

    def start(self) -> bool:
        """Start the output module processing."""
        if self.is_running:
            return False
            
        self.is_running = True
        self.clear_queue()
        self.thread = threading.Thread(target=self.process_frames, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> bool:
        """Stop the output module processing."""
        if not self.is_running:
            return False
            
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.clear_queue()
        return True

    def clear_queue(self):
        """Clear the frame queue."""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    def add_frame(self, frame) -> bool:
        """Add a frame to the queue if running."""
        if not self.is_running:
            return False
            
        try:
            self.frame_queue.put(frame, block=False)
            return True
        except queue.Full:
            return False

    def set_fps(self, fps: int) -> bool:
        """Set the FPS for this output module."""
        if fps <= 0:
            print(f"Warning: Invalid FPS {fps} for module {self.name}. Keeping previous value {self.fps}.")
            return False
        self.fps = fps
        self.frame_interval = 1.0 / fps
        print(f"Module {self.name} FPS set to {self.fps}, Interval set to {self.frame_interval}")
        return True
    
    def set_frametime(self, frametime: float) -> bool:
        """Set the frame time (interval) for this output module."""
        if frametime <= 0:
            print(f"Warning: Invalid frametime {frametime} for module {self.name}. Keeping previous value {self.frame_interval}.")
            return False
        self.frame_interval = frametime
        self.fps = 1.0 / frametime
        print(f"Module {self.name} Interval set to {self.frame_interval}, FPS set to {self.fps}")
        return True

    def should_process_frame(self) -> bool:
        """Check if enough time has passed to process the next frame."""
        current_time = time.time()
        if current_time - self.last_frame_time >= self.frame_interval:
            self.last_frame_time = current_time
            return True
        return False

    def set_processing_strategy(self, strategy: StrategyType) -> None:
        """Set the image processing strategy."""
        self.processing_strategy = strategy
        print(f"Module {self.name} processing strategy set to {strategy.name if strategy else 'None'}")

    def process_frame(self, frame):
        """Process a single frame using the current strategy."""
        if self.processing_strategy:
            return self.processing_strategy.process_image(frame)
        return frame

    @abstractmethod
    def process_frames(self):
        """Process frames from the queue. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_frame(self):
        """Get the next frame. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_required_camera_fps(self) -> float:
        """Get the desired camera FPS for this output module.
        
        Returns:
            float: The required FPS (e.g., 25.0 for a 25 FPS stream, or 0.2 for a 5-second timelapse).
                   Returns 0.0 if the module is not active or has no specific requirement.
        """
        pass 