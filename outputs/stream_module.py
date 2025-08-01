import cv2
from outputs.output_module import OutputModule
import time
import threading

class StreamModule(OutputModule):
    """Handles MJPEG streaming of camera frames."""
    
    def __init__(self, name="stream"):
        super().__init__(name)
        self.jpeg_quality = 90
        self.frame_stats = {
            'frames_processed': 0,
            'frames_dropped': 0,
            'last_stats_time': time.time(),
            'actual_fps': 0.0
        }
        self.stats_lock = threading.Lock()
        
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
                
                # Update frame statistics
                with self.stats_lock:
                    self.frame_stats['frames_processed'] += 1
                    current_time = time.time()
                    if current_time - self.frame_stats['last_stats_time'] >= 1.0:
                        self.frame_stats['actual_fps'] = self.frame_stats['frames_processed'] / (current_time - self.frame_stats['last_stats_time'])
                        self.frame_stats['frames_processed'] = 0
                        self.frame_stats['last_stats_time'] = current_time
                        print(f"Stream actual FPS: {self.frame_stats['actual_fps']:.2f}")
                        
            except:
                with self.stats_lock:
                    self.frame_stats['frames_dropped'] += 1
                continue
                
    def get_frame(self):
        """Get the latest frame as JPEG bytes."""
        return self.last_frame if self.last_frame else b''
        
    def generate_frames(self):
        """Generator for streaming frames."""
        while self.is_running:
            # More precise timing with smaller buffer
            time.sleep(max(0, self.frame_interval - 0.005))
            frame = self.get_frame()
            if frame:
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def get_required_camera_fps(self) -> float:
        """Return the stream's configured FPS if running, otherwise 0."""
        if self.is_running:
            return float(self.fps) # self.fps is from OutputModule base class
        return 0.0
        
    def get_stats(self):
        """Get current streaming statistics."""
        with self.stats_lock:
            return self.frame_stats.copy() 