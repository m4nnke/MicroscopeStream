import threading
import time
from typing import Optional, List
import numpy as np
from picamera2 import Picamera2
import libcamera
from output_module import OutputModule

class Camera:
    """Camera handling and frame capture using picamera2."""
    
    def __init__(self):
        self.camera = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.output_modules: List[OutputModule] = []
        
        # Camera settings
        self.fps = 10
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
            # Initialize camera
            self.camera = Picamera2()
            
            # Create preview configuration
            preview_config = self.camera.create_preview_configuration(
                main={"size": self.resolution, "format": "BGR888"},
                buffer_count=2  # Use 2 buffers for better performance
            )
            
            # Configure camera transform (in case image needs to be flipped)
            preview_config["transform"] = libcamera.Transform(hflip=0, vflip=0)
            
            # Set frame rate
            frame_time = int(1000000 / self.fps)  # Convert fps to frame duration in microseconds
            preview_config["controls"] = {
                "FrameDurationLimits": (frame_time, frame_time)
            }
            
            # Apply configuration
            self.camera.configure(preview_config)
            
            # Apply initial camera controls
            self._apply_camera_settings()
            
            # Start camera
            self.camera.start()

            self.camera.set_controls({"AeEnable": True})
            
            # Start capture thread
            self.is_running = True
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
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
        frame_interval = 1.0 / self.fps
        
        while self.is_running and self.camera:
            current_time = time.time()
            elapsed = current_time - last_frame_time
            
            # Maintain FPS
            if elapsed < frame_interval:
                time.sleep(min(frame_interval - elapsed, 1/(self.fps*1.5)))  # Small sleep to prevent CPU overuse
                continue
                
            # Capture frame
            frame = self.camera.capture_array("main")
            print("Frame captured", (current_time - last_frame_time)*self.fps)
            
            # Distribute frame to all active output modules
            for module in self.output_modules:
                if module.is_running and module.should_process_frame():
                    module.add_frame(frame.copy())
                    
            last_frame_time = current_time
            
    def _apply_camera_settings(self):
        """Apply current settings to the camera."""
        if not self.camera:
            return
            
        try:
            # Create controls dictionary
            controls = {}
            
            # Frame rate control
            frame_time = int(1000000 / self.fps)  # Convert fps to frame duration
            controls["FrameDurationLimits"] = (frame_time, frame_time)
            
            # Exposure control
       
            controls["AeEnable"] = True  # Auto exposure

            # Brightness control (maps to AnalogueGain)
            # Map -1.0 to 1.0 to appropriate gain range (e.g., 1.0 to 4.0)
            gain = 1.0 + (self.brightness + 1.0) * 1.5  # Maps to 1.0-4.0
            controls["AnalogueGain"] = max(1.0, min(4.0, gain))
            
            # Contrast control
            controls["Contrast"] = max(0.0, min(4.0, self.contrast))
            
            # Saturation control
            controls["Saturation"] = max(0.0, min(4.0, self.saturation))
            
            # Apply controls
            self.camera.set_controls(controls)
            
        except Exception as e:
            print(f"Error applying camera settings: {e}")
            
    def update_settings(self, **settings) -> bool:
        """Update camera settings."""
        updated = False
        restart_required = False
        
        if 'fps' in settings and settings['fps'] > 0:
            if self.fps != settings['fps']:
                self.fps = settings['fps']
                updated = True
                # FPS changes that affect FrameDurationLimits might need restart or reconfiguration
                # For now, assuming _apply_camera_settings is sufficient if camera is running.
                # If not, a restart might be needed here.
            
        if 'resolution' in settings:
            new_resolution = tuple(settings['resolution'])
            if self.resolution != new_resolution:
                width, height = new_resolution
                if width > 0 and height > 0:
                    self.resolution = new_resolution
                    updated = True
                    restart_required = True # Resolution changes require camera restart
                
        # Expecting UI values (0-100) and converting to internal camera control values
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

        # if 'exposure_ui' in settings: # Placeholder for exposure UI if implemented
        #     # Convert exposure_ui (e.g., EV steps or 0 for auto) to self.exposure (microseconds)
        #     # Example: if settings['exposure_ui'] == 0: self.exposure = 0 else: self.exposure = convert_ev_to_microseconds(settings['exposure_ui'])
        #     updated = True

        if restart_required and self.is_running:
            print("Camera restart required due to settings change.")
            self.stop()
            self.start()
            # updated is already true if restart_required
            return True # Return after restart

        if updated and self.camera and self.is_running:
            print("Applying camera settings on-the-fly.")
            self._apply_camera_settings()
            
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
            'fps': self.fps,
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