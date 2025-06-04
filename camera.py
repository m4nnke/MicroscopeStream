import threading
import time
from typing import Optional, List
import numpy as np
from picamera2 import Picamera2
import libcamera
from output_module import OutputModule

# --- Global Configuration ---
DEFAULT_IDLE_CAMERA_FPS = 1/20  # FPS when no modules are active (e.g., 1 frame every 20 seconds)
# --- End Global Configuration ---

class Camera:
    """Camera handling and frame capture using picamera2."""
    
    def __init__(self):
        self.camera = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.output_modules: List[OutputModule] = []
        
        # Camera settings
        self.current_capture_fps = DEFAULT_IDLE_CAMERA_FPS # Use the defined constant
        self.resolution = (1920, 1080)  # Default Full HD
        self.brightness = 0.0  # Range: -1.0 to 1.0
        self.contrast = 1.0    # Range: 0.0 to 4.0
        self.saturation = 1.0  # Range: 0.0 to 4.0
        self.exposure = 0      # In microseconds, 0 for auto
        
    def start(self) -> bool:
        """Start the camera and frame capture thread."""
        if self.is_running:
            return False
            
        try:
            self.camera = Picamera2()
            preview_config = self.camera.create_preview_configuration(
                main={"size": self.resolution, "format": "BGR888"},
                buffer_count=2
            )
            preview_config["transform"] = libcamera.Transform(hflip=0, vflip=0)
            self.camera.configure(preview_config)
            
            self._apply_camera_parameters() # Apply non-FPS settings
            
            self.camera.start()
            print("Camera hardware started.")

            # Apply FPS limits after camera has started
            self._apply_camera_fps_limits(self.current_capture_fps)
            print(f"Initial FPS limits applied: {self.current_capture_fps} FPS")
            
            self.is_running = True
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            print("Capture thread started.")
            return True
            
        except Exception as e:
            print(f"Error starting camera: {e}")
            if self.camera:
                self.camera.close()
                self.camera = None
            return False
            
    def stop(self) -> bool:
        """Stop the camera and release resources."""
        if not self.is_running:
            return False
            
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
        if self.camera:
            try:
                self.camera.stop()
                self.camera.close()
            except:
                pass
            self.camera = None
            
        return True
        
    def add_output_module(self, module: OutputModule) -> bool:
        """Add an output module to receive frames."""
        if module not in self.output_modules:
            self.output_modules.append(module)
            return True
        return False
        
    def remove_output_module(self, module: OutputModule) -> bool:
        """Remove an output module."""
        if module in self.output_modules:
            self.output_modules.remove(module)
            return True
        return False
        
    def _capture_frames(self):
        """Continuously capture frames and distribute to output modules."""
        last_frame_time = 0
        # frame_interval will be dynamic based on self.current_capture_fps
        
        while self.is_running and self.camera:
            frame_interval = 1.0 / self.current_capture_fps
            current_time = time.time()
            elapsed = current_time - last_frame_time
            
            # Maintain FPS
            if elapsed < frame_interval:
                # Sleep for a short duration, ensuring it's positive
                # and capped to avoid excessively long sleeps if fps is very low.
                sleep_duration = frame_interval - elapsed
                if self.current_capture_fps > 0: # Avoid division by zero
                     time.sleep(max(0.001, min(sleep_duration, 1.0 / self.current_capture_fps)))
                else: # If FPS is zero, perhaps a longer, but still capped sleep
                    time.sleep(0.1)

                continue
                
            # Capture frame
            try:
                frame = self.camera.capture_array("main")
                print(f"Frame captured at {current_time}, interval: {elapsed:.4f}s, target_fps: {self.current_capture_fps}")
            except Exception as e:
                print(f"Error capturing frame: {e}")
                # Attempt to recover or log error, possibly break loop if critical
                if "Camera has been stopped" in str(e) or "Camera is not streaming" in str(e):
                    print("Camera appears to be stopped or not streaming. Stopping capture.")
                    self.is_running = False # Stop the loop
                time.sleep(0.1) # Avoid busy-looping on error
                continue

            # Distribute frame to all active output modules
            for module in self.output_modules:
                if module.is_running and module.should_process_frame():
                    module.add_frame(frame.copy())
                    
            last_frame_time = current_time
            
    def _apply_camera_parameters(self):
        """Apply non-FPS camera parameters like brightness, contrast, saturation."""
        if not self.camera:
            return
        try:
            controls = {}
            gain = 1.0 + (self.brightness + 1.0) * 1.5
            controls["AnalogueGain"] = max(1.0, min(4.0, gain))
            controls["Contrast"] = max(0.0, min(4.0, self.contrast))
            controls["Saturation"] = max(0.0, min(4.0, self.saturation))
            self.camera.set_controls(controls)
            print(f"Applied camera parameters: Brightness={self.brightness}, Contrast={self.contrast}, Saturation={self.saturation}")
        except Exception as e:
            print(f"Error applying camera parameters: {e}")

    def _apply_camera_fps_limits(self, target_fps: float):
        """Apply FPS-specific FrameDurationLimits to the camera."""
        if not self.camera:
            return
        try:
            controls = {}
            effective_fps = target_fps
            if effective_fps <= 0:
                print(f"Target FPS is {effective_fps}, defaulting to 1.0 for FrameDurationLimits.")
                effective_fps = 1.0
            
            frame_time = int(1000000 / effective_fps)
            controls["FrameDurationLimits"] = (frame_time, frame_time)
            self.camera.set_controls(controls)
            print(f"Applied FrameDurationLimits for {effective_fps} FPS (frame time: {frame_time} us)")
        except Exception as e:
            print(f"Error applying FrameDurationLimits for {target_fps} FPS: {e}")
            
    def update_capture_fps(self, new_fps: float):
        """Updates the camera's capture FPS."""
        if new_fps <= 0:
            print(f"Attempted to set invalid FPS: {new_fps}. Using 1.0 FPS instead.")
            new_fps = 1.0

        if self.current_capture_fps != new_fps:
            self.current_capture_fps = new_fps
            print(f"Camera capture FPS updated to: {self.current_capture_fps}")
            if self.camera and self.is_running:
                self._apply_camera_fps_limits(self.current_capture_fps) # Only apply FPS limits
            
    def update_settings(self, **settings) -> bool:
        """Update camera settings."""
        updated = False
        restart_required = False
        
        # FPS is no longer set directly here, handled by update_capture_fps
            
        if 'resolution' in settings:
            new_resolution = tuple(settings['resolution'])
            if self.resolution != new_resolution:
                width, height = new_resolution
                if width > 0 and height > 0:
                    self.resolution = new_resolution
                    updated = True
                    restart_required = True 
                
        if 'brightness_ui' in settings:
            new_brightness_internal = (float(settings['brightness_ui']) / 50.0) - 1.0
            if self.brightness != new_brightness_internal:
                self.brightness = new_brightness_internal
                updated = True
            
        if 'contrast_ui' in settings:
            new_contrast_internal = float(settings['contrast_ui']) / 25.0
            if self.contrast != new_contrast_internal:
                self.contrast = new_contrast_internal
                updated = True
            
        if 'saturation_ui' in settings:
            new_saturation_internal = float(settings['saturation_ui']) / 25.0
            if self.saturation != new_saturation_internal:
                self.saturation = new_saturation_internal
                updated = True

        if restart_required and self.is_running:
            print("Camera restart required due to settings change.")
            self.stop()
            self.start()
            return True 

        if updated and self.camera and self.is_running:
            print("Applying non-FPS camera settings on-the-fly.")
            self._apply_camera_parameters() # Apply only non-FPS parameters
            
        return updated
        
    def get_settings(self) -> dict:
        """Get current camera settings."""
        # Convert internal values back to UI ranges
        brightness_ui = int((self.brightness + 1.0) * 50.0)  # -1.0 to 1.0 -> 0 to 100
        contrast_ui = int(self.contrast * 25.0)    # 0.0 to 4.0 -> 0 to 100
        saturation_ui = int(self.saturation * 25.0)  # 0.0 to 4.0 -> 0 to 100
        
        # Convert exposure from microseconds to EV
        if self.exposure == 0:
            exposure_ui = 0  # Auto exposure
        else:
            exposure_ui = int(np.log2(self.exposure / 1000))
            
        return {
            # 'fps': self.fps, # FPS removed
            'resolution': self.resolution,
            'brightness': brightness_ui,
            'contrast': contrast_ui,
            'saturation': saturation_ui,
            'exposure': exposure_ui
        }
        
    @property
    def is_active(self) -> bool:
        """Check if camera is active."""
        return self.is_running and self.camera is not None 