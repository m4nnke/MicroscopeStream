from strategies.base_strategy import NoOpStrategy
from strategies.image_strategies import (
    EdgeDetectionStrategy,
    GrayscaleStrategy,
    ThresholdStrategy,
    ContrastEnhancementStrategy
)

# Define available processing strategies
PROCESSING_STRATEGIES = {
    'none': NoOpStrategy(),
    'edges': EdgeDetectionStrategy(),
    'grayscale': GrayscaleStrategy(),
    'threshold': ThresholdStrategy(),
    'contrast': ContrastEnhancementStrategy(),
    # 'ocr': OCRStrategy() # If you have it
}

class ConfigManager:
    def __init__(self):
        self.settings = {
            "camera": {
                "fps": 10,
                "resolution": (1920, 1080), # Default Full HD
                "brightness": 0.0,  # Range: -1.0 to 1.0 for camera internal, UI might be 0-100
                "contrast": 1.0,    # Range: 0.0 to 4.0 for camera internal, UI might be 0-100
                "saturation": 1.0,  # Range: 0.0 to 4.0 for camera internal, UI might be 0-100
                "exposure": 0,      # In microseconds, 0 for auto
                # UI specific representations (0-100)
                "brightness_ui": 50, 
                "contrast_ui": 25, 
                "saturation_ui": 25,
                "exposure_ui": 0 # 0 for auto, could map to EV values for UI
            },
            "stream": {
                "fps": 10,
                "jpeg_quality": 90,
                "processing_strategy_name": "none" 
            },
            "storage": {
                "fps": 1, # Target FPS for recording
                "frame_interval": 1.0, # Derived from FPS, interval between frames to save
                "output_dir": "recordings",
                "processing_strategy_name": "none"
            },
            "timelapse": {
                "interval": 5,  # Seconds between frames
                "duration": 300, # Seconds for total timelapse duration before creating video
                "min_frames": 10, # Min frames before creating video (if duration not met but stopped)
                "output_dir": "timelapses",
                "processing_strategy_name": "none"
            },
            "available_processing_modes": list(PROCESSING_STRATEGIES.keys())
        }

    def get_settings(self):
        """Return all current settings."""
        return self.settings

    def get_camera_settings(self):
        return self.settings["camera"]

    def get_stream_settings(self):
        return self.settings["stream"]

    def get_storage_settings(self):
        return self.settings["storage"]

    def get_timelapse_settings(self):
        return self.settings["timelapse"]
    
    def get_processing_strategy(self, module_name: str):
        """Gets the strategy object for a given module."""
        strategy_name = self.settings.get(module_name, {}).get("processing_strategy_name", "none")
        return PROCESSING_STRATEGIES.get(strategy_name, PROCESSING_STRATEGIES['none'])

    def update_settings(self, new_settings):
        """
        Update settings. new_settings is a dict that can be partial.
        It will be merged into the existing settings.
        Also ensures camera FPS is sufficient for output modules.
        """
        # Deep update for camera, stream, storage, timelapse
        for key in ["camera", "stream", "storage", "timelapse"]:
            if key in new_settings:
                # Ensure FPS/Interval values are positive before updating
                if key == "camera" and "fps" in new_settings[key] and new_settings[key]["fps"] <= 0:
                    print(f"Warning: Invalid camera FPS ({new_settings[key]['fps']}) provided. Ignoring.")
                    new_settings[key].pop("fps") # Remove invalid FPS to keep current or let auto-adjust
                elif key == "stream" and "fps" in new_settings[key] and new_settings[key]["fps"] <= 0:
                    print(f"Warning: Invalid stream FPS ({new_settings[key]['fps']}) provided. Ignoring.")
                    new_settings[key].pop("fps")
                elif key == "storage" and "fps" in new_settings[key] and new_settings[key]["fps"] <= 0:
                    print(f"Warning: Invalid storage FPS ({new_settings[key]['fps']}) provided. Ignoring.")
                    new_settings[key].pop("fps")
                elif key == "timelapse" and "interval" in new_settings[key] and new_settings[key]["interval"] <= 0:
                    print(f"Warning: Invalid timelapse interval ({new_settings[key]['interval']}) provided. Ignoring.")
                    new_settings[key].pop("interval")

                self.settings[key].update(new_settings[key])
        
        # Special handling for camera brightness/contrast/saturation UI values
        if "camera" in new_settings:
            cam_set = self.settings["camera"]
            if 'brightness_ui' in new_settings["camera"]:
                # Convert 0-100 to -1.0 to 1.0
                cam_set['brightness'] = (float(new_settings["camera"]['brightness_ui']) / 50.0) - 1.0
            if 'contrast_ui' in new_settings["camera"]:
                # Convert 0-100 to 0.0 to 4.0
                cam_set['contrast'] = float(new_settings["camera"]['contrast_ui']) / 25.0
            if 'saturation_ui' in new_settings["camera"]:
                # Convert 0-100 to 0.0 to 4.0
                cam_set['saturation'] = float(new_settings["camera"]['saturation_ui']) / 25.0
            # Add exposure_ui to exposure mapping if needed

        # Update FPS dependent values for storage
        if "storage" in self.settings and self.settings["storage"]["fps"] > 0:
            self.settings["storage"]["frame_interval"] = 1.0 / self.settings["storage"]["fps"]
        elif "storage" in self.settings: # If fps became 0 or invalid
             self.settings["storage"]["frame_interval"] = 1.0 # Default to 1 to avoid division by zero

        # Ensure camera FPS is sufficient for all output modules
        max_output_fps = 0
        
        # Stream FPS
        if self.settings["stream"]["fps"] > 0:
            max_output_fps = max(max_output_fps, self.settings["stream"]["fps"])
        
        # Storage FPS
        if self.settings["storage"]["fps"] > 0:
            max_output_fps = max(max_output_fps, self.settings["storage"]["fps"])
            
        # Timelapse effective FPS
        timelapse_interval = self.settings["timelapse"]["interval"]
        if timelapse_interval > 0:
            timelapse_fps = 1.0 / timelapse_interval
            max_output_fps = max(max_output_fps, timelapse_fps)

        if max_output_fps > 0 and self.settings["camera"]["fps"] < max_output_fps:
            print(f"Adjusting camera FPS from {self.settings['camera']['fps']} to {max_output_fps} to meet output module demand.")
            self.settings["camera"]["fps"] = max_output_fps
        elif self.settings["camera"]["fps"] <= 0 and max_output_fps > 0: # If camera FPS was invalid, set it to max_output_fps
            print(f"Setting camera FPS to {max_output_fps} (was invalid) to meet output module demand.")
            self.settings["camera"]["fps"] = max_output_fps
        elif self.settings["camera"]["fps"] <= 0: # If all FPS are 0 or invalid, default camera FPS
             print(f"Warning: Camera FPS is invalid ({self.settings['camera']['fps']}) and no valid output FPS. Setting camera FPS to 1.")
             self.settings["camera"]["fps"] = 1

        # We could add more validation or callbacks here if needed
        return True 