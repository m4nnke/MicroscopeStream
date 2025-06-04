from flask import Flask, render_template, Response, request, jsonify, send_file, send_from_directory
import os
import cv2
import io
import time

from camera import Camera, DEFAULT_IDLE_CAMERA_FPS
from stream_manager import StreamManager
from storage_manager import StorageManager
from timelapse_manager import TimelapseManager
from config_manager import ConfigManager, PROCESSING_STRATEGIES # Import global PROCESSING_STRATEGIES

app = Flask(__name__)

# --- Global Configuration ---
# DEFAULT_IDLE_CAMERA_FPS = 1/20  # Moved to camera.py
# --- End Global Configuration ---

# Initialize Configuration Manager
config_manager = ConfigManager()

# Initialize camera and modules
camera = Camera() # Camera will be configured by apply_module_configurations
stream_manager = StreamManager(name="stream") # Names are important for config mapping
storage_manager = StorageManager(name="storage", output_dir=config_manager.get_storage_settings().get("output_dir", "recordings"))
timelapse_manager = TimelapseManager(name="timelapse", output_dir=config_manager.get_timelapse_settings().get("output_dir", "timelapses"))

# Register modules with camera
camera.add_output_module(stream_manager)
camera.add_output_module(storage_manager)
camera.add_output_module(timelapse_manager)

# List of all output modules that can influence camera FPS
output_modules_for_fps = [stream_manager, storage_manager, timelapse_manager]

def update_camera_fps_based_on_outputs():
    """Calculates the max required FPS from all active modules and updates the camera."""
    max_required_fps = 0.0
    active_module_found = False
    for module in output_modules_for_fps:
        if module.is_running:
            required_fps = module.get_required_camera_fps()
            if required_fps > 0:
                max_required_fps = max(max_required_fps, required_fps)
                active_module_found = True
    
    # If no active module requires a specific FPS, default to the defined IDLE FPS.
    # The camera.update_capture_fps method itself handles 0 or negative by defaulting to 1.0, 
    # but we provide our specific idle FPS here.
    target_fps = max_required_fps if active_module_found and max_required_fps > 0 else DEFAULT_IDLE_CAMERA_FPS
    
    print(f"Updating camera FPS based on outputs. Max required: {max_required_fps}, Target FPS for camera: {target_fps}")
    camera.update_capture_fps(target_fps)

def apply_module_configurations():
    """Applies configurations from ConfigManager to all modules."""
    # Configure Camera
    cam_config = config_manager.get_camera_settings()
    camera.update_settings(
        # fps=cam_config['fps'], # FPS is now dynamic
        resolution=cam_config['resolution'],
        brightness_ui=cam_config['brightness_ui'], # Pass UI values, camera.update_settings handles conversion
        contrast_ui=cam_config['contrast_ui'],
        saturation_ui=cam_config['saturation_ui']
        # exposure_ui will be handled if/when implemented in camera.py and config_manager
    )

    # Configure Stream Manager
    stream_config = config_manager.get_stream_settings()
    stream_manager.set_fps(stream_config['fps'])
    stream_manager.jpeg_quality = stream_config['jpeg_quality']
    stream_manager.set_processing_strategy(config_manager.get_processing_strategy("stream"))

    # Configure Storage Manager
    storage_config = config_manager.get_storage_settings()
    storage_manager.set_fps(storage_config['fps']) # This also sets frame_interval
    storage_manager.output_dir = storage_config['output_dir']
    storage_manager.set_processing_strategy(config_manager.get_processing_strategy("storage"))

    # Configure Timelapse Manager
    timelapse_config = config_manager.get_timelapse_settings()
    # For timelapse, the 'interval' directly determines its internal FPS for frame capture timing
    timelapse_manager.set_frametime(float(timelapse_config['interval'])) 
    timelapse_manager.duration = timelapse_config['duration']
    timelapse_manager.min_frames = timelapse_config['min_frames']
    timelapse_manager.output_dir = timelapse_config['output_dir']
    timelapse_manager.set_processing_strategy(config_manager.get_processing_strategy("timelapse"))

    # After all modules are configured, update camera FPS
    update_camera_fps_based_on_outputs()

# Apply initial configurations at startup
apply_module_configurations()

STILLS_DIR = "stills" # Define the directory for storing stills

@app.route('/')
def index():
    """Render the main page with current settings and status."""
    # Supported resolutions can be static or derived if made dynamic in future
    supported_resolutions = [ (640, 480), (800, 600), (1280, 720), (1920, 1080)]
    
    # Get all settings from ConfigManager
    current_settings = config_manager.get_settings()
    current_settings['camera']['supported_resolutions'] = supported_resolutions # Add to camera settings for UI

    # Get current status from modules
    current_status = {
        'camera_running': camera.is_active,
        'stream_active': stream_manager.is_running,
        'storage_active': storage_manager.is_running,
        'storage_current_file': storage_manager.current_file,
        'timelapse_active': timelapse_manager.is_running,
        'timelapse_current_frames': len(timelapse_manager.frames) if timelapse_manager else 0,
        # Add more status fields as needed, e.g., from timelapse_manager.get_status()
    }
    
    page_data = {
        "settings": current_settings,
        "status": current_status
    }
    return render_template('index.html', page_data=page_data)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Unified endpoint to get or update all settings."""
    if request.method == 'POST':
        new_settings = request.json
        if new_settings:
            config_manager.update_settings(new_settings)
            apply_module_configurations() # Re-apply to all modules
            return jsonify({"success": True, "message": "Settings updated.", "settings": config_manager.get_settings()})
        return jsonify({"success": False, "message": "No settings provided."}), 400
    else: # GET
        return jsonify(config_manager.get_settings())

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get the current status of the camera and all modules."""
    status = {
        'camera_running': camera.is_active,
        'stream_active': stream_manager.is_running,
        'storage_active': storage_manager.is_running,
        'storage_current_file': storage_manager.current_file,
        'timelapse_active': timelapse_manager.is_running,
        'timelapse_info': timelapse_manager.get_status() if timelapse_manager else {}, # from get_status method
        # Consider adding more specific status like errors or progress here
    }
    return jsonify(status)

@app.route('/api/control/<string:component>/<string:action>', methods=['POST'])
def api_control(component, action):
    """Control camera and output modules (start/stop)."""
    success = False
    message = f"Action '{action}' on component '{component}' not recognized."

    target_module = None
    if component == 'camera': target_module = camera
    elif component == 'stream': target_module = stream_manager
    elif component == 'storage': target_module = storage_manager
    elif component == 'timelapse': target_module = timelapse_manager
    else:
        return jsonify({'success': False, 'message': f'Unknown component: {component}'}), 404

    if action == 'start':
        if hasattr(target_module, 'start'):
            success = target_module.start()
            message = f'{component.capitalize()} started.' if success else f'Failed to start {component}.'
            if success:
                update_camera_fps_based_on_outputs() # Update FPS after starting a module
        else: message = f"Component {component} cannot be started."
    elif action == 'stop':
        if hasattr(target_module, 'stop'):
            success = target_module.stop()
            message = f'{component.capitalize()} stopped.' if success else f'Failed to stop {component}.'
            if success:
                update_camera_fps_based_on_outputs() # Update FPS after stopping a module
        else: message = f"Component {component} cannot be stopped."
    
    if not success and not message.startswith("Failed"): # if action not start/stop
        message = f"Action '{action}' not supported for {component}."

    return jsonify({'success': success, 'message': message})

@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    if not stream_manager.is_running:
        # Return a placeholder image or a 204 No Content if stream is off
        # For simplicity, returning 204. A user-friendly app might show a "Stream Off" image.
        return '', 204 
    return Response(
        stream_manager.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/recordings')
def list_recordings():
    """List all recorded videos."""
    recordings_dir = config_manager.get_storage_settings().get("output_dir", "recordings")
    recs = []
    if os.path.exists(recordings_dir):
        recs = sorted([f for f in os.listdir(recordings_dir) if f.endswith('.mp4')], reverse=True)
    return jsonify({'recordings': recs})

@app.route('/timelapses')
def list_timelapses():
    """List all timelapse videos."""
    timelapses_dir = config_manager.get_timelapse_settings().get("output_dir", "timelapses")
    lapses = []
    if os.path.exists(timelapses_dir):
        lapses = sorted([f for f in os.listdir(timelapses_dir) if f.endswith('.mp4')], reverse=True)
    return jsonify({'timelapses': lapses})

@app.route('/capture_high_res_still', methods=['POST'])
def capture_high_res_still():
    """Captures a still image at maximum resolution and saves it."""
    frame = camera.capture_still_at_max_resolution()
    if frame is not None:
        try:
            os.makedirs(STILLS_DIR, exist_ok=True)
            success, encoded_image_data = cv2.imencode('.jpg', frame)
            if not success:
                return jsonify({"success": False, "message": "Failed to encode image to JPEG."}), 500
            
            encoded_image_bytes = encoded_image_data.tobytes()
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"high_res_still_{timestamp}.jpg"
            filepath = os.path.join(STILLS_DIR, filename)

            try:
                with open(filepath, 'wb') as f:
                    f.write(encoded_image_bytes)
                print(f"High-resolution still saved to {filepath}")
                return jsonify({"success": True, "message": f"Still image saved as {filename}", "filename": filename})
            except Exception as e:
                print(f"Error saving high-resolution still to file: {e}")
                return jsonify({"success": False, "message": f"Error saving still image: {str(e)}"}), 500

        except Exception as e:
            print(f"Error processing high-res still: {e}")
            return jsonify({"success": False, "message": f"Error processing image: {str(e)}"}), 500
    else:
        return jsonify({"success": False, "message": "Failed to capture high-resolution still image."}), 500

@app.route('/api/stills_list')
def list_stills():
    """List all saved still images."""
    stills = []
    if os.path.exists(STILLS_DIR):
        try:
            # Sort by name, which includes timestamp, so newest first if using YYYYMMDD format
            stills = sorted([f for f in os.listdir(STILLS_DIR) if f.lower().endswith('.jpg')], reverse=True)
        except Exception as e:
            print(f"Error listing stills directory {STILLS_DIR}: {e}")
            return jsonify({'success': False, 'message': 'Error listing stills'}), 500
    return jsonify({'stills': stills, 'success': True})

# --- Download Routes ---
@app.route('/download/recording/<path:filename>')
def download_recording(filename):
    recordings_dir = config_manager.get_storage_settings().get("output_dir", "recordings")
    return send_from_directory(directory=recordings_dir, path=filename, as_attachment=True)

@app.route('/download/timelapse/<path:filename>')
def download_timelapse(filename):
    timelapses_dir = config_manager.get_timelapse_settings().get("output_dir", "timelapses")
    return send_from_directory(directory=timelapses_dir, path=filename, as_attachment=True)

@app.route('/download/still/<path:filename>')
def download_still(filename):
    return send_from_directory(directory=STILLS_DIR, path=filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 