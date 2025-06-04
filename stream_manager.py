import cv2
from output_module import OutputModule
import time

class StreamManager(OutputModule):
    """Handles MJPEG streaming of camera frames."""
    
    def __init__(self, name="stream"):
        super().__init__(name)
        self.jpeg_quality = 90
        
    def process_frames(self):
        """Process frames from the queue for streaming."""
        while self.is_running:
            try:
                frame = self.frame_queue.get(timeout=1.0)
                # Apply image processing strategy
                processed_frame = self.process_frame(frame)
                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                self.last_frame = buffer.tobytes()
            except:
                continue
                
    def get_frame(self):
        """Get the latest frame as JPEG bytes."""
        return self.last_frame if self.last_frame else b''
        
    def generate_frames(self):
        """Generator for streaming frames."""
        while self.is_running:
            time.sleep(max(0, self.frame_interval - 0.01))
            frame = self.get_frame()
            if frame:
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n') 