from flask import Flask, render_template, Response, request, jsonify
from camera import Camera
from stream_manager import StreamManager
from storage_manager import StorageManager
from timelapse_manager import TimelapseManager
from strategies.base_strategy import NoOpStrategy
from strategies.image_strategies import (
    EdgeDetectionStrategy,
    GrayscaleStrategy,
    ThresholdStrategy,
    ContrastEnhancementStrategy
)
#from strategies.ocr_strategy import OCRStrategy

app = Flask(__name__)

# Initialize camera and modules
camera = Camera()
stream_manager = StreamManager()
storage_manager = StorageManager()
timelapse_manager = TimelapseManager()

# Register modules with camera
camera.add_output_module(stream_manager)
camera.add_output_module(storage_manager)
camera.add_output_module(timelapse_manager)

# Create strategy instances
PROCESSING_STRATEGIES = {
    'none': NoOpStrategy(),
    'edges': EdgeDetectionStrategy(),
    'grayscale': GrayscaleStrategy(),
    'threshold': ThresholdStrategy(),
    'contrast': ContrastEnhancementStrategy(),
 #   'ocr': OCRStrategy()
}

@app.route('/')
def index():
    """Render the main page."""
    camera_info = {
        'status': {
            'camera_running': camera.is_active,
            'stream_active': stream_manager.is_running,
            'capture_active': storage_manager.is_running,
            'timelapse_active': timelapse_manager.is_running
        },
        'current_settings': {
            **camera.get_settings(),
            'processing_mode': 'none',  # For future image processing modes
            'available_modes': ['none'],  # For future image processing modes
            'stream': {
                'jpeg_quality': stream_manager.jpeg_quality,
                'fps': stream_manager.fps
            },
            'storage': {
                'output_dir': storage_manager.output_dir,
                'fps': storage_manager.fps,
                'interval': storage_manager.frame_interval,
                'current_file': storage_manager.current_file
            },
            'timelapse': timelapse_manager.get_status()
        },
        'supported_resolutions': [
            (640, 480),
            (800, 600),
            (1280, 720),
            (1920, 1080)
        ]
    }
    return render_template('index.html', camera_info=camera_info)

@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    if not stream_manager.is_running:
        return '', 204
    return Response(
        stream_manager.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/camera/control', methods=['POST'])
def camera_control():
    """Handle camera control actions."""
    action = request.json.get('action')
    success = False
    message = ''
    print(action)
    
    if action == 'start_camera':
        success = camera.start()
        message = 'Camera started' if success else 'Failed to start camera'
    elif action == 'stop_camera':
        success = camera.stop()
        message = 'Camera stopped' if success else 'Failed to stop camera'
    elif action == 'start_stream':
        success = stream_manager.start()
        message = 'Stream started' if success else 'Failed to start stream'
    elif action == 'stop_stream':
        success = stream_manager.stop()
        message = 'Stream stopped' if success else 'Failed to stop stream'
    elif action == 'start_capture':
        success = storage_manager.start()
        message = 'Recording started' if success else 'Failed to start recording'
    elif action == 'stop_capture':
        success = storage_manager.stop()
        message = 'Recording stopped' if success else 'Failed to stop recording'
    elif action == 'start_timelapse':
        success = timelapse_manager.start()
        message = 'Timelapse started' if success else 'Failed to start timelapse'
    elif action == 'stop_timelapse':
        success = timelapse_manager.stop()
        message = 'Timelapse stopped' if success else 'Failed to stop timelapse'
        
    return jsonify({'success': success, 'message': message})

@app.route('/camera/status')
def camera_status():
    """Get camera and modules status."""
    return jsonify({
        'camera_running': camera.is_active,
        'stream_active': stream_manager.is_running,
        'capture_active': storage_manager.is_running,
        'timelapse_active': timelapse_manager.is_running
    })

@app.route('/camera_settings', methods=['POST'])
def update_camera_settings():
    """Update camera settings."""
    settings = request.json
    success = camera.update_settings(**settings)
    
    return jsonify({
        'success': success,
        'settings': {
            'status': {
                'camera_running': camera.is_active,
                'stream_active': stream_manager.is_running,
                'capture_active': storage_manager.is_running,
                'timelapse_active': timelapse_manager.is_running
            }
        }
    })

@app.route('/stream/settings', methods=['GET', 'POST'])
def update_stream_settings():
    """Update stream settings."""
    try:
        data = request.get_json()
        
        if 'fps' in data:
            stream_manager.set_fps(int(data['fps']))
            
        if 'jpeg_quality' in data:
            stream_manager.jpeg_quality = int(data['jpeg_quality'])
            
        if 'processing_mode' in data:
            mode = data['processing_mode']
            if mode in PROCESSING_STRATEGIES:
                stream_manager.set_processing_strategy(PROCESSING_STRATEGIES[mode])
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/storage/settings', methods=['GET', 'POST'])
def storage_settings():
    """Get or update storage settings."""
    if request.method == 'POST':
        settings = request.json
        updated = False
        
        if 'output_dir' in settings:
            storage_manager.output_dir = settings['output_dir']
            updated = True
            
        if 'fps' in settings:
            fps = max(1, min(60, int(settings['fps'])))
            updated = storage_manager.set_fps(fps)

        if 'interval' in settings:
            frametime = max(0.01, float(settings['interval']))
            updated = storage_manager.set_frametime(frametime)
            
        return jsonify({
            'success': updated,
            'settings': {
                'output_dir': storage_manager.output_dir,
                'fps': storage_manager.fps,
                'current_file': storage_manager.current_file
            }
        })
    else:
        return jsonify({
            'output_dir': storage_manager.output_dir,
            'fps': storage_manager.fps,
            'current_file': storage_manager.current_file
        })

@app.route('/timelapse/settings', methods=['GET', 'POST'])
def timelapse_settings():
    """Get or update timelapse settings."""
    if request.method == 'POST':
        settings = request.json
        success = timelapse_manager.update_settings(**settings)
        return jsonify({'success': success})
    else:
        return jsonify(timelapse_manager.get_status())

@app.route('/recordings')
def list_recordings():
    """List all recorded videos."""
    import os
    recordings = []
    if os.path.exists(storage_manager.output_dir):
        recordings = [f for f in os.listdir(storage_manager.output_dir) 
                     if f.endswith('.mp4')]
    return jsonify({'recordings': recordings})

@app.route('/timelapses')
def list_timelapses():
    """List all timelapse videos."""
    import os
    timelapses = []
    if os.path.exists(timelapse_manager.output_dir):
        timelapses = [f for f in os.listdir(timelapse_manager.output_dir) 
                     if f.endswith('.mp4')]
    return jsonify({'timelapses': timelapses})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 