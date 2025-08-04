import cv2
import os
import time
from datetime import datetime
from outputs.output_module import OutputModule
import queue # For specific exception handling
import glob

class TimelapseModule(OutputModule):
    """Handles timelapse capture and video creation."""
    
    def __init__(self, name="timelapse", output_dir="timelapses"):
        super().__init__(name)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(script_dir, output_dir)
        self.output_dir = output_dir
        self.interval: float = 1.0  # Capture interval in seconds (also self.frame_interval in base class)
        self.duration: int = 300    # Timelapse duration in seconds
        self.min_frames: int = 10   # Min frames to create video
        self.session_dir = None     # Path to current session folder
        self.frame_count = 0        # Counter for frame filenames
        self.start_time = 0         # Timestamp when current timelapse capture started
        self.well_label = None  # Store well label for this session

    def start(self) -> bool:
        """Start the timelapse capture, clearing previous session."""
        if not super().start():
            return False
        # Create a unique session folder for this timelapse
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.output_dir, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        self.frame_count = 0
        self.start_time = time.time()
        print(f"TimelapseManager {self.name} started. Interval: {self.frame_interval}s, Duration: {self.duration}s, Session dir: {self.session_dir}")
        return True

    def process_frames(self):
        """Process frames from the queue for timelapse."""
        while self.is_running:
            try:
                original_frame = self.frame_queue.get(timeout=1.0) # Wait for a frame
                if original_frame is None:
                    continue

                # Apply image processing strategy from the base class
                processed_frame = self.process_frame(original_frame)
                self.last_frame = processed_frame # For get_frame()

                # Save frame to disk
                self.frame_count += 1
                frame_filename = os.path.join(self.session_dir, f"frame_{self.frame_count:05d}.jpg")
                cv2.imwrite(frame_filename, processed_frame)

                # Check if we should create a video
                current_time = time.time()
                if (self.duration > 0 and current_time - self.start_time >= self.duration):
                    self._create_timelapse()

            except queue.Empty:
                # This means no frame was available within the timeout.
                # Check if duration is met even if no new frame arrived, if is_running is false.
                if not self.is_running and self.start_time > 0:
                    if (self.duration > 0 and time.time() - self.start_time >= self.duration):
                        self._create_timelapse()
                continue
            except Exception as e:
                print(f"Error in TimelapseManager process_frames: {e}")
                continue

    def get_frame(self):
        """Get the latest captured (and processed) frame."""
        return self.last_frame

    def _create_timelapse(self):
        """Create a timelapse video from saved images in the session folder."""
        if not self.session_dir:
            print(f"Timelapse {self.name}: No session directory set. Cannot create video.")
            return
        # Find all frame images in the session folder
        img_files = sorted(glob.glob(os.path.join(self.session_dir, "frame_*.jpg")))
        if len(img_files) < self.min_frames:
            if img_files:
                print(f"Timelapse {self.name}: Not enough frames ({len(img_files)}/{self.min_frames}) to create video. Discarding.")
            self.start_time = 0
            return

        # Output video path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        well_label = self.well_label
        if well_label:
            video_filename = f"{well_label}_timelapse_{timestamp}.mp4"
        else:
            video_filename = f"timelapse_{timestamp}.mp4"
        output_path = os.path.join(self.session_dir, video_filename)

        # Get frame dimensions from first frame
        frame = cv2.imread(img_files[0])
        height, width = frame.shape[:2]
        output_fps = 25

        print(f"Timelapse {self.name}: Creating video {output_path} with {len(img_files)} frames at {output_fps} FPS.")
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                output_path,
                fourcc,
                output_fps,
                (width, height)
            )
            for img_file in img_files:
                img = cv2.imread(img_file)
                writer.write(img)
            writer.release()
            print(f"Timelapse {self.name}: Video created successfully: {output_path}")
        except Exception as e:
            print(f"Timelapse {self.name}: Error creating video {output_path}: {e}")
        self.start_time = time.time() if self.is_running else 0

    def set_well_label(self, well_label):
        self.well_label = well_label

    def get_status(self) -> dict:
        """Get current timelapse status."""
        current_time = time.time()
        next_capture_in = 0
        if self.is_running and self.last_frame_time > 0:
            next_capture_in = max(0, self.frame_interval - (current_time - self.last_frame_time))
        next_video_in = 0
        if self.is_running and self.start_time > 0 and self.duration > 0:
            next_video_in = max(0, self.duration - (current_time - self.start_time))
        # Count frames on disk for status
        frame_count = 0
        if self.session_dir and os.path.exists(self.session_dir):
            frame_count = len(glob.glob(os.path.join(self.session_dir, "frame_*.jpg")))
        return {
            'current_frames': frame_count,
            'interval': self.frame_interval,
            'duration': self.duration,
            'min_frames': self.min_frames,
            'output_dir': self.output_dir,
            'session_dir': self.session_dir,
            'next_capture_in': round(next_capture_in, 2),
            'next_video_in': round(next_video_in, 2),
            'time_elapsed': round(current_time - self.start_time if self.start_time > 0 else 0, 2)
        }

    def stop(self) -> bool:
        """Stop timelapse and create final video if enough frames."""
        was_running = self.is_running
        if not super().stop():
            if not was_running:
                return False
        print(f"TimelapseManager {self.name} stopping. Checking for final video creation.")
        # Ensure final video creation is attempted if conditions met
        if self.session_dir:
            img_files = sorted(glob.glob(os.path.join(self.session_dir, "frame_*.jpg")))
            if len(img_files) >= self.min_frames:
                self._create_timelapse()
            elif len(img_files) > 0:
                print(f"Timelapse {self.name}: Not enough frames ({len(img_files)}/{self.min_frames}) or duration not met. Discarding on stop.")
        self.start_time = 0
        return True

    def get_required_camera_fps(self) -> float:
        """Return the required camera FPS based on the timelapse interval."""
        if self.is_running and self.frame_interval > 0:
            return 1.0 / self.frame_interval
        return 0.0 