# MicroscopeStream: Web-Based Camera Control and Capture

MicroscopeStream is a Python Flask web application designed to control a Picamera2-compatible camera (commonly used with Raspberry Pi) for microscopy or general-purpose imaging. It provides a web interface to view a live stream, adjust camera settings, record videos, capture timelapses, and take high-resolution still images.

## Overview

The application offers a user-friendly web UI accessible from any browser on the same network. It allows for real-time monitoring and control, making it suitable for various imaging projects, especially those involving remote or automated capture. Key functionalities include live streaming, on-demand video recording, configurable timelapse photography, and high-resolution still image capture.

## Features

*   **Live Video Stream:** View a real-time MJPEG stream from the camera.
*   **Camera Control:**
    *   Start/Stop camera.
    *   Adjust resolution, brightness, contrast, and saturation.
    *   Dynamic FPS adjustment based on active modules (stream, recording, timelapse).
*   **Video Recording:**
    *   Start/Stop video recording on demand.
    *   Recordings saved as MP4 files in the `recordings/` directory.
    *   Configurable recording FPS.
*   **Timelapse Capture:**
    *   Configure interval between frames, total duration, and minimum frames for video generation.
    *   Timelapses saved as MP4 files in the `timelapses/` directory.
*   **High-Resolution Stills:**
    *   Capture still images at the camera's maximum sensor resolution.
    *   Stills saved as JPG files in the `stills/` directory.
*   **Image Processing (Basic):**
    *   Apply simple image processing strategies (e.g., grayscale, edge detection, contrast enhancement) to the stream, recordings, or timelapses. (Configurable per module)
*   **Web Interface:**
    *   Responsive UI with live feed display.
    *   Controls for camera, stream, recording, and timelapse.
    *   Settings panel for fine-tuning parameters.
    *   File browser to list and download captured recordings, timelapses, and stills.
*   **Configuration Management:**
    *   Settings are managed via internal defaults, which could be extended to use a `config.json` file for persistent custom configurations.

## Hardware & Software Requirements

*   **Hardware:**
    *   A Raspberry Pi (or compatible single-board computer) is recommended.
    *   A Picamera2-compatible camera module.
*   **Software:**
    *   Python 3.7+
    *   `libcamera` library (usually pre-installed on recent Raspberry Pi OS).
    *   The Python dependencies listed in `requirements.txt`.

## Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd MicroscopeStream
    ```

2.  **Install Dependencies:**
    It's recommended to use a Python virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Run the Application:**
    ```bash
    python app.py
    ```
    The application will start, and by default, it should be accessible at `http://<your_raspberry_pi_ip>:5000` from a web browser on the same network.

## Using the Application

Once the application is running, open your web browser and navigate to the IP address of the device running the application, followed by port 5000 (e.g., `http://192.168.1.100:5000`).

The web interface is divided into three main columns:

*   **Live Feed & Master Controls (Left):**
    *   Displays the live video feed from the camera.
    *   Buttons to start/stop the camera, live stream, video recording, and timelapse capture.
    *   Button to capture a high-resolution still image.
    *   Status indicators for each module.

*   **Settings (Middle):**
    *   Allows adjustment of various parameters for the camera (resolution, brightness, contrast, saturation), stream (FPS, JPEG quality), recording (FPS), and timelapse (interval, duration, min frames).
    *   Selection of image processing modes for stream, recording, and timelapse.
    *   Button to apply changed settings.

*   **Files (Right):**
    *   Lists captured recordings, timelapses, and stills.
    *   Refresh buttons to update the lists.
    *   Files are clickable links to download them directly.

## Configuration

The application uses default settings defined in `config_manager.py`. While not currently implemented to load from/save to an external `config.json` file, the `ConfigManager` class is structured to potentially support this in the future for persistent user configurations.

Default output directories:
*   Recordings: `recordings/`
*   Timelapses: `timelapses/`
*   Stills: `stills/`

These directories are automatically created if they don't exist. They are also included in the `.gitignore` file to prevent accidental versioning of media files.

## Project Structure

*   `app.py`: Main Flask application, defines routes and orchestrates modules.
*   `camera.py`: Handles camera initialization, configuration, and frame capture using Picamera2.
*   `config_manager.py`: Manages application settings for camera and output modules.
*   `output_module.py`: Base class for modules that process or save camera frames.
*   `stream_manager.py`: Manages the MJPEG live stream.
*   `storage_manager.py`: Manages video recording.
*   `timelapse_manager.py`: Manages timelapse capture and video generation.
*   `strategies/`: Contains image processing strategy classes.
*   `templates/index.html`: The main HTML file for the web interface.
*   `requirements.txt`: Lists Python dependencies.
*   `.gitignore`: Specifies intentionally untracked files for Git.
*   `README.md`: This file.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit pull requests. If you encounter any issues or have feature suggestions, please open an issue on GitHub.

## License

(No license specified in the project. Consider adding one, e.g., MIT, Apache 2.0, GPL.)
