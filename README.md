# Drowsiness Detection System

This application monitors a user's face for signs of drowsiness and alerts when drowsiness is detected. It tracks drowsiness events and provides analytics.

## Project Structure

The project has been reorganized into a modular structure for better maintainability:

- `app1.py` - Main entry point for the application
- `db.py` - Database operations and data access
- `detection.py` - Drowsiness detection logic
- `auth.py` - Authentication logic
- `routes.py` - API routes
- `socket_handlers.py` - WebSocket event handlers

## Requirements

- Python 3.6+
- Flask and Flask extensions (SocketIO, CORS)
- OpenCV
- dlib
- PyGame
- SQLite3
- Additional dependencies in `requirements.txt`

## Setup

1. Make sure you have all dependencies installed:

   ```
   pip install -r requirements.txt
   ```

2. Ensure you have the face landmark predictor file:

   - `shape_predictor_68_face_landmarks.dat`

3. Ensure you have the sound alert file:
   - `alert.mp3`

## Running the Application

Start the application by running:

```
python app1.py
```

The server will start on port 5000. You can access the web interface at `http://localhost:5000`.

then open new terminal -> cd flask-drow   
then npm install
then npm run dev 


## Features

- Real-time drowsiness detection using eye aspect ratio (EAR)
- Audio alerts when drowsiness is detected
- Event logging to SQLite database
- REST API for data retrieval and analysis
- User authentication
- Session tracking
- Analytics dashboard

## API Endpoints

- `/` - Web interface
- `/api/db-status` - Database status
- `/api/events` - Get drowsiness events
- `/api/sessions` - Get sessions
- `/api/stats` - Get statistics
- `/api/export-csv` - Export data to CSV
- `/api/register` - Register new user
- `/api/login` - User login

## WebSocket Events

- `send_frame` - Send camera frame for processing
- `camera_status` - Update camera status (start/stop)
- `detection_result` - Receive drowsiness detection result
