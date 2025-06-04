import cv2
import os
from datetime import datetime
from output_module import OutputModule

class StorageManager(OutputModule):
    """Handles video recording and saving."""
    
    def __init__(self, name="storage", output_dir="recordings"):
        super().__init__(name)
        self.output_dir = output_dir
        self.writer = None
        self.current_file = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def process_frames(self):
        """Process frames from the queue for recording."""
        while self.is_running:
            try:
                frame = self.frame_queue.get(timeout=1.0)
                self._ensure_writer(frame)
                self.writer.write(frame)
                self.last_frame = frame
            except:
                continue
                
    def get_frame(self):
        """Get the latest recorded frame."""
        return self.last_frame
        
    def _ensure_writer(self, frame):
        """Ensure video writer is initialized."""
        if self.writer is None:
            height, width = frame.shape[:2]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}.mp4"
            self.current_file = os.path.join(self.output_dir, filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(
                self.current_file,
                fourcc,
                self.fps,
                (width, height)
            )
            
    def stop(self) -> bool:
        """Stop recording and release resources."""
        if not super().stop():
            return False
            
        if self.writer:
            self.writer.release()
            self.writer = None
            print("Video recording stopped: " + self.current_file)

        return True 