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
        
        if 'fps' in settings and settings['fps'] > 0:
            self.fps = settings['fps']
            updated = True
            
        if 'resolution' in settings:
            width, height = settings['resolution']
            if width > 0 and height > 0:
                self.resolution = (width, height)
                # Resolution changes require reconfiguration
                if self.camera and self.is_running:
                    self.stop()
                    self.start()
                return True
                
        if 'brightness' in settings:
            # Convert 0-100 to -1.0 to 1.0
            self.brightness = (float(settings['brightness']) / 50.0) - 1.0
            updated = True
            
        if 'contrast' in settings:
            # Convert 0-100 to 0.0 to 4.0
            self.contrast = float(settings['contrast']) / 25.0
            updated = True
            
        if 'saturation' in settings:
            # Convert 0-100 to 0.0 to 4.0
            self.saturation = float(settings['saturation']) / 25.0
            updated = True
            
        #if 'exposure' in settings:
            # Convert exposure value to microseconds
            #ev = int(settings['exposure'])
            #if ev < 0:  # Auto exposure
                #self.exposure = 0
            #else:
                #self.exposure = int(1000 * (2 ** ev))  # Convert EV to microseconds
            #updated = True
            
        if updated and self.camera and self.is_running:
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