import cv2
import os
import time
from datetime import datetime
from output_module import OutputModule

class TimelapseManager(OutputModule):
    """Handles timelapse capture and video creation."""
    
    def __init__(self, name="timelapse", output_dir="timelapses"):
        super().__init__(name)
        self.output_dir = output_dir
        self.interval = 1  # Default: 1 second between frames
        self.duration = 300  # Default: 5 minutes
        self.min_frames = 100  # Minimum frames before creating video
        self.frames = []
        self.last_capture_time = 0
        self.start_time = 0
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def process_frames(self):
        """Process frames from the queue for timelapse."""
        self.start_time = time.time()
        
        while self.is_running:
            try:
                frame = self.frame_queue.get(timeout=1.0)

                self.frames.append(frame.copy())
                self.last_frame = frame
                self.last_capture_time = current_time
                    
                # Check if we should create a video
                if (len(self.frames) >= self.min_frames or 
                    current_time - self.start_time >= self.duration):
                    self._create_timelapse()
                        
            except:
                continue
                
    def get_frame(self):
        """Get the latest captured frame."""
        return self.last_frame
        
    def _create_timelapse(self):
        """Create a timelapse video from captured frames."""
        if not self.frames:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"timelapse_{timestamp}.mp4"
        output_path = os.path.join(self.output_dir, filename)
        
        # Get frame dimensions from first frame
        height, width = self.frames[0].shape[:2]
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            25,  # Output FPS
            (width, height)
        )
        
        # Write frames
        for frame in self.frames:
            writer.write(frame)
            
        writer.release()
        print("Timelapse video created: " + output_path)
        
        # Clear frames after creating video
        self.frames = []
        self.start_time = time.time()
        
    def get_status(self) -> dict:
        """Get current timelapse status."""
        current_time = time.time()
        return {
            'current_frames': len(self.frames),
            'next_capture_in': max(0, self.interval - (current_time - self.last_capture_time)),
            'next_video_in': max(0, self.duration - (current_time - self.start_time)),
            'interval': self.interval,
            'duration': self.duration,
            'min_frames': self.min_frames
        }
        
    def update_settings(self, **settings) -> bool:
        """Update timelapse settings."""
        updated = False
        
        if 'interval' in settings and settings['interval'] > 0:
            self.interval = settings['interval']
            updated = True
            
        if 'duration' in settings and settings['duration'] > 0:
            self.duration = settings['duration']
            updated = True
            
        if 'min_frames' in settings and settings['min_frames'] > 0:
            self.min_frames = settings['min_frames']
            updated = True
            
        return updated
        
    def stop(self) -> bool:
        """Stop timelapse and create final video if enough frames."""
        if not super().stop():
            return False
            
        if len(self.frames) >= self.min_frames:
            self._create_timelapse()
            
        return True 