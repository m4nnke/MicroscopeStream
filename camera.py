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
        
        self.sensor_modes = [] # To store sensor capabilities
        self.max_sensor_resolution = None # Store max resolution
        
    def start(self) -> bool:
        """Start the camera and frame capture thread."""
        if self.is_running:
            return False
            
        try:
            self.camera = Picamera2()
            
            # Get sensor capabilities
            try:
                self.sensor_modes = self.camera.sensor_modes
                if self.sensor_modes:
                    # Find the mode with the largest area; typically the last one or one with largest 'size'
                    self.max_sensor_resolution = max(self.sensor_modes, key=lambda m: m['size'][0] * m['size'][1])['size']
                    print(f"Determined maximum sensor resolution: {self.max_sensor_resolution}")
                else:
                    print("Warning: Could not retrieve sensor modes. Max resolution capture might be limited.")
                    self.max_sensor_resolution = self.resolution # Fallback
            except Exception as e:
                print(f"Warning: Error fetching sensor modes: {e}. Max resolution capture might be limited.")
                self.max_sensor_resolution = self.resolution # Fallback

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
        if not self.camera or not hasattr(self.camera, 'camera_controls') or not self.camera.camera_controls:
            print("Camera or camera_controls not available for applying parameters.")
            return
        try:
            controls = {}

            # Brightness: self.brightness is -1.0 to 1.0 (from UI 0-100)
            min_br, max_br, _def_br = self.camera.camera_controls.get("Brightness", (-1.0, 1.0, 0.0))
            controls["Brightness"] = max(min_br, min(max_br, self.brightness))

            # Contrast: self.contrast is 0.0 to 4.0 (from UI 0-100 / 25.0)
            min_co, max_co, _def_co = self.camera.camera_controls.get("Contrast", (0.0, 4.0, 1.0)) # Default to 0-4 if not found, though it should be
            controls["Contrast"] = max(min_co, min(max_co, self.contrast))

            # Saturation: self.saturation is 0.0 to 4.0 (from UI 0-100 / 25.0)
            min_sa, max_sa, _def_sa = self.camera.camera_controls.get("Saturation", (0.0, 4.0, 1.0)) # Default to 0-4 if not found
            controls["Saturation"] = max(min_sa, min(max_sa, self.saturation))
            
            self.camera.set_controls(controls)
            print(f"Applied camera parameters via set_controls: Brightness={controls['Brightness']:.2f} (raw self.brightness: {self.brightness:.2f}), Contrast={controls['Contrast']:.2f}, Saturation={controls['Saturation']:.2f}")

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
        """Updates the camera's capture FPS.
        If the camera is running and FPS changes, it will restart the camera
        to apply the new FPS settings effectively."""
        if new_fps <= 0:
            print(f"Attempted to set invalid FPS: {new_fps}. Using 1.0 FPS instead.")
            new_fps = 1.0

        if self.current_capture_fps != new_fps:
            old_fps = self.current_capture_fps
            self.current_capture_fps = new_fps # Update the target FPS
            
            if self.is_running and self.camera: # If camera is active, restart it
                print(f"Camera capture FPS changed from {old_fps} to: {self.current_capture_fps}. Restarting camera to apply.")
                self.stop()
                # A small delay might sometimes be beneficial for resources to fully release,
                # though Picamera2's stop/start cycle should ideally manage this.
                # time.sleep(0.5) # Consider testing if this adds stability if issues arise.
                self.start() # This will re-initialize with the new self.current_capture_fps
            else:
                # If camera is not running, just update the value. self.start() will pick it up when called.
                print(f"Camera is not running. Capture FPS set to {self.current_capture_fps} for next start.")
        # else:
            # print(f"Camera FPS already at {new_fps}. No change needed.") # Optional: for debugging
            
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
            'exposure': exposure_ui # Placeholder, actual exposure value is not directly mapped to UI yet
        }
        
    @property
    def is_active(self) -> bool:
        """Check if any output module is actively processing."""
        return self.is_running and self.camera is not None 

    def _get_max_resolution_from_sensor(self):
        """Helper to query Picamera2 for max sensor resolution."""
        # This method assumes self.camera might not be initialized or could be None
        # or might be called before self.start() populates self.max_sensor_resolution
        if self.max_sensor_resolution: # Prefer already determined value
            return self.max_sensor_resolution

        temp_cam_instance = None
        try:
            if self.camera and hasattr(self.camera, 'sensor_modes'): # If global camera exists and has modes
                modes = self.camera.sensor_modes
            else: # Otherwise, create a temporary instance
                print("Creating temporary Picamera2 instance to query sensor modes.")
                temp_cam_instance = Picamera2()
                modes = temp_cam_instance.sensor_modes
            
            if modes:
                # Find the mode with the largest area
                max_res = max(modes, key=lambda m: m['size'][0] * m['size'][1])['size']
                print(f"Queried max sensor resolution: {max_res}")
                return max_res
            else:
                print("Could not retrieve sensor modes for max resolution.")
                return self.resolution # Fallback to current/default
        except Exception as e:
            print(f"Error dynamically getting sensor modes: {e}")
            return self.resolution # Fallback
        finally:
            if temp_cam_instance:
                temp_cam_instance.close()
                print("Closed temporary Picamera2 instance.")

    def capture_still_at_max_resolution(self):
        """
        Captures a still image at the camera's maximum sensor resolution.
        Temporarily adjusts camera settings if it's already running a stream.
        If camera is not running, it performs a one-off capture.
        Returns:
            A NumPy array representing the image, or None on failure.
        """
        target_max_res = self._get_max_resolution_from_sensor()
        if not target_max_res:
            print("Failed to determine target maximum resolution.")
            return None

        print(f"Attempting still capture at resolution: {target_max_res}")
        frame = None

        if self.is_running and self.camera and self.camera.started:
            print("Camera is active. Using switch_mode_and_capture_array for high-res still.")
            try:
                # switch_mode_and_capture_array handles state changes (stop, reconfigure, capture, restore, restart)
                still_config = self.camera.create_still_configuration(
                    main={"size": target_max_res, "format": "BGR888"}, # Use BGR888 for OpenCV compatibility
                    buffer_count=2, # Still recommended to have at least 2 for picamera2
                    # controls={"FrameDurationLimits": (100000, 100000)} # e.g., 10fps, tune as needed
                )
                # Preserve current transform if any (though still_config might reset it)
                # current_transform = self.camera.camera_configuration().get("transform")
                # if current_transform:
                # still_config["transform"] = current_transform
                
                # Apply current non-FPS parameters to the still_config's controls
                # This helps maintain brightness, contrast etc. for the still shot
                current_params_for_still = {}
                # Always apply contrast and saturation from current settings
                current_params_for_still["Contrast"] = max(0.0, min(self.camera.camera_controls["Contrast"][1], self.contrast))
                current_params_for_still["Saturation"] = max(0.0, min(self.camera.camera_controls["Saturation"][1], self.saturation))

                if self.exposure > 0: # If manual exposure is set for the stream
                    gain = 1.0 + (self.brightness + 1.0) * 1.5
                    # Ensure gain is within the camera's reported valid range for AnalogueGain
                    min_gain_cam, max_gain_cam = self.camera.camera_controls["AnalogueGain"]
                    current_params_for_still["AnalogueGain"] = max(min_gain_cam, min(max_gain_cam, gain))
                    current_params_for_still["ExposureTime"] = self.exposure
                # Else (self.exposure == 0, auto-exposure for stream):
                #   Do not set AnalogueGain or ExposureTime for the still.
                #   Rely on the camera's auto-exposure/auto-gain for the still capture.
                
                # Merge these with any controls already in still_config (like FrameDurationLimits)
                if 'controls' not in still_config:
                    still_config['controls'] = {}
                still_config['controls'].update(current_params_for_still)
                
                print(f"Configuring for still capture: {still_config}")

                frame = self.camera.switch_mode_and_capture_array(still_config, "main")
                print(f"Successfully captured {target_max_res} frame via switch_mode_and_capture_array.")
            except Exception as e:
                print(f"Error during switch_mode_and_capture_array: {e}")
                # switch_mode_and_capture_array should ideally restore the camera to its previous state.
                # If not, restarting the camera might be necessary if it's left in a bad state.
                # self.stop()
                # self.start() # This could be too disruptive.
                return None
        else:
            print("Camera is not running or not fully started. Performing one-off high-resolution capture.")
            temp_cam = None
            try:
                temp_cam = Picamera2()
                # Apply sensor modes to get max_res again for this instance if needed.
                sensor_modes_temp = temp_cam.sensor_modes
                if sensor_modes_temp:
                     actual_max_res_temp = max(sensor_modes_temp, key=lambda m: m['size'][0] * m['size'][1])['size']
                     if actual_max_res_temp != target_max_res:
                         print(f"Temporary camera max res {actual_max_res_temp} differs from expected {target_max_res}. Using {actual_max_res_temp}")
                         target_max_res = actual_max_res_temp
                
                still_config = temp_cam.create_still_configuration(
                    main={"size": target_max_res, "format": "BGR888"},
                    buffer_count=1 # For one-off capture, 1 buffer is fine
                )

                # Apply relevant parameters from self (brightness, contrast etc.) to the temporary camera's config
                # This mimics _apply_camera_parameters but for a temporary configuration
                controls_for_temp_cam = {}
                # Always apply contrast and saturation
                controls_for_temp_cam["Contrast"] = max(0.0, min(temp_cam.camera_controls["Contrast"][1], self.contrast))
                controls_for_temp_cam["Saturation"] = max(0.0, min(temp_cam.camera_controls["Saturation"][1], self.saturation))

                if self.exposure > 0: # If manual exposure was configured on the main Camera object
                    gain = 1.0 + (self.brightness + 1.0) * 1.5 # self.brightness is from the Camera class
                    min_gain_cam, max_gain_cam = temp_cam.camera_controls["AnalogueGain"]
                    controls_for_temp_cam["AnalogueGain"] = max(min_gain_cam, min(max_gain_cam, gain))
                    controls_for_temp_cam["ExposureTime"] = self.exposure
                # Else (self.exposure == 0):
                #   Rely on temp_cam's default auto-exposure/auto-gain.
                
                if 'controls' not in still_config:
                    still_config['controls'] = {}
                still_config['controls'].update(controls_for_temp_cam)

                print(f"Configuring temporary camera for still capture: {still_config}")
                temp_cam.configure(still_config)
                
                temp_cam.start()
                frame = temp_cam.capture_array("main") # Capture from "main" stream of still_config
                print(f"Successfully captured {target_max_res} frame via one-off capture.")
                temp_cam.stop()
            except Exception as e:
                print(f"Error during one-off high-resolution capture: {e}")
                return None
            finally:
                if temp_cam:
                    temp_cam.close()
                    print("Closed temporary Picamera2 instance for one-off capture.")
        
        return frame 