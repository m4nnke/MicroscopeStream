import cv2
import os
from datetime import datetime
from outputs.output_module import OutputModule
import queue # For specific exception handling

class StorageModule(OutputModule):
    """Handles video recording and saving."""
    
    def __init__(self, name="storage", output_dir="recordings"):
        super().__init__(name)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(script_dir, output_dir)
        self.writer = None
        self.current_file = None
        self.well_label = None  # Store well label for this session
        
        # Create output directory if it doesn't exist
        # This should ideally be done once at startup or when output_dir changes
        # For now, let app.py ensure this via ConfigManager if dirs are dynamic
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
    def process_frames(self):
        """Process frames from the queue for recording."""
        while self.is_running:
            try:
                original_frame = self.frame_queue.get(timeout=1.0)
                if original_frame is None: # Should not happen with current queue logic but good check
                    continue

                # Apply image processing strategy from the base class
                processed_frame = self.process_frame(original_frame)
                
                self._ensure_writer(processed_frame) # Ensure writer is initialized with correct frame dimensions
                
                if self.writer:
                    self.writer.write(processed_frame)
                    self.last_frame = processed_frame # Store the processed frame if needed for get_frame
                else:
                    print(f"Error: StorageManager writer not initialized for {self.current_file}")

            except queue.Empty:
                continue # Normal timeout, no frame in queue
            except Exception as e:
                print(f"Error in StorageManager process_frames: {e}")
                # Consider stopping or re-initializing writer on certain errors
                continue
                
    def get_frame(self):
        """Get the latest recorded frame."""
        return self.last_frame
        
    def _ensure_writer(self, frame_for_dims):
        """Ensure video writer is initialized using dimensions from the provided frame."""
        if self.writer is None:
            # Create output directory if it doesn't exist (e.g. if changed at runtime)
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir, exist_ok=True)

            height, width = frame_for_dims.shape[:2]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            well_label = self.well_label
            if well_label:
                filename = f"{well_label}_video_{timestamp}.mp4"
            else:
                filename = f"video_{timestamp}.mp4"
            self.current_file = os.path.join(self.output_dir, filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            # Use actual self.fps from OutputModule, which is configured by ConfigManager
            actual_fps = self.fps 
            print(f"Initializing StorageManager writer for {self.current_file} at {actual_fps} FPS, Res: {width}x{height}")
            self.writer = cv2.VideoWriter(
                self.current_file,
                fourcc,
                actual_fps, 
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

    def get_required_camera_fps(self) -> float:
        """Return the storage module's configured FPS if running, otherwise 0."""
        if self.is_running:
            return float(self.fps) # self.fps is from OutputModule base class
        return 0.0 

    def set_well_label(self, well_label):
        self.well_label = well_label 