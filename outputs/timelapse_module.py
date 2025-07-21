import cv2
import os
import time
from datetime import datetime
from outputs.output_module import OutputModule
import queue # For specific exception handling

class TimelapseModule(OutputModule):
    """Handles timelapse capture and video creation."""
    
    def __init__(self, name="timelapse", output_dir="timelapses"):
        super().__init__(name)
        self.output_dir = output_dir
        # These will be configured by app.py via ConfigManager
        self.interval: float = 1.0  # Capture interval in seconds (also self.frame_interval in base class)
        self.duration: int = 300    # Timelapse duration in seconds
        self.min_frames: int = 10   # Min frames to create video
        
        self.frames = [] # Stores collected (and processed) frames
        self.start_time = 0 # Timestamp when current timelapse capture started
        
        # Output directory creation is handled by _create_timelapse or ensured by app.py
        
    def start(self) -> bool:
        """Start the timelapse capture, clearing previous frames."""
        if not super().start():
            return False
        self.frames = [] # Clear any old frames
        self.start_time = time.time()
        print(f"TimelapseManager {self.name} started. Interval: {self.frame_interval}s, Duration: {self.duration}s")
        return True

    def process_frames(self):
        """Process frames from the queue for timelapse."""
        # self.start_time is set in self.start()
        
        while self.is_running:
            try:
                original_frame = self.frame_queue.get(timeout=1.0) # Wait for a frame
                if original_frame is None:
                    continue

                # Apply image processing strategy from the base class
                processed_frame = self.process_frame(original_frame)
                
                self.frames.append(processed_frame.copy()) # Add processed frame
                self.last_frame = processed_frame # For get_frame()

                # Check if we should create a video
                current_time = time.time()
                if (self.duration > 0 and current_time - self.start_time >= self.duration) or \
                   (self.min_frames > 0 and len(self.frames) >= self.min_frames and not self.is_running): # Create if stopped and min_frames met
                    self._create_timelapse()
                        
            except queue.Empty:
                # This means no frame was available within the timeout.
                # Check if duration is met even if no new frame arrived, if is_running is false.
                if not self.is_running and self.start_time > 0: # if stopped
                    if (self.duration > 0 and time.time() - self.start_time >= self.duration) or \
                       (self.min_frames > 0 and len(self.frames) >= self.min_frames):
                        self._create_timelapse()
                continue # Continue waiting or exit if not running
            except Exception as e:
                print(f"Error in TimelapseManager process_frames: {e}")
                continue
                
    def get_frame(self):
        """Get the latest captured (and processed) frame."""
        return self.last_frame
        
    def _create_timelapse(self):
        """Create a timelapse video from captured frames."""
        if not self.frames or len(self.frames) < self.min_frames:
            if self.frames: # if some frames but not enough, and we are told to create
                 print(f"Timelapse {self.name}: Not enough frames ({len(self.frames)}/{self.min_frames}) to create video. Discarding.")
            self.frames = [] # Clear frames anyway
            self.start_time = 0 # Reset start time
            return

        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"timelapse_{timestamp}.mp4"
        output_path = os.path.join(self.output_dir, filename)
        
        # Get frame dimensions from first frame (should all be same)
        height, width = self.frames[0].shape[:2]
        
        # Video writer FPS - could be configurable
        output_fps = 25 
        
        print(f"Timelapse {self.name}: Creating video {output_path} with {len(self.frames)} frames at {output_fps} FPS.")
        
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                output_path,
                fourcc,
                output_fps, 
                (width, height)
            )
            
            for frame_to_write in self.frames:
                writer.write(frame_to_write)
            
            writer.release()
            print(f"Timelapse {self.name}: Video created successfully: {output_path}")
        except Exception as e:
            print(f"Timelapse {self.name}: Error creating video {output_path}: {e}")
        
        self.frames = [] # Clear frames after creating video
        self.start_time = time.time() if self.is_running else 0 # Reset start time only if still running
        
    def get_status(self) -> dict:
        """Get current timelapse status."""
        current_time = time.time()
        
        next_capture_in = 0
        if self.is_running and self.last_frame_time > 0: # last_frame_time from OutputModule
            next_capture_in = max(0, self.frame_interval - (current_time - self.last_frame_time))

        next_video_in = 0
        if self.is_running and self.start_time > 0 and self.duration > 0:
            next_video_in = max(0, self.duration - (current_time - self.start_time))
            
        return {
            'current_frames': len(self.frames),
            'interval': self.frame_interval, # This is the actual capture interval
            'duration': self.duration,
            'min_frames': self.min_frames,
            'output_dir': self.output_dir,
            'next_capture_in': round(next_capture_in, 2),
            'next_video_in': round(next_video_in, 2),
            'time_elapsed': round(current_time - self.start_time if self.start_time > 0 else 0, 2)
        }
        
    # update_settings method is removed as app.py directly sets attributes 
    # and calls set_frametime (which updates self.interval from OutputModule base)

    def stop(self) -> bool:
        """Stop timelapse and create final video if enough frames."""
        was_running = self.is_running
        if not super().stop(): # This sets self.is_running to False
            if not was_running: # If it was already stopped, no need to proceed
                 return False
        
        print(f"TimelapseManager {self.name} stopping. Checking for final video creation.")
        # Process any remaining frames that might have been added just before stop
        # Or rely on the process_frames loop's own check when is_running becomes false
        
        # Ensure final video creation is attempted if conditions met
        if len(self.frames) > 0 and ( (self.duration > 0 and time.time() - self.start_time >= self.duration) or \
             (self.min_frames > 0 and len(self.frames) >= self.min_frames) ):
            self._create_timelapse()
        elif len(self.frames) > 0 :
             print(f"Timelapse {self.name}: Not enough frames ({len(self.frames)}/{self.min_frames}) or duration not met. Discarding on stop.")
             self.frames = [] # Clear frames if not creating video

        self.start_time = 0 # Reset start time as it's stopped
        return True 

    def get_required_camera_fps(self) -> float:
        """Return the required camera FPS based on the timelapse interval."""
        if self.is_running and self.frame_interval > 0:
            return 1.0 / self.frame_interval
        return 0.0 