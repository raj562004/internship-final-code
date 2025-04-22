import eventlet
eventlet.monkey_patch()  # Allows WebSockets to work smoothly

from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
from flask_cors import CORS
import cv2
import dlib
import numpy as np
from scipy.spatial import distance
import pygame
import base64
import io
import time  # For tracking sound duration
from PIL import Image
import sqlite3
import os
import datetime
from datetime import datetime, timedelta
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import io
import uuid
import csv
import hashlib
import secrets
from functools import wraps

app = Flask(__name__)
# Enable CORS for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable WebSockets

# Initialize Pygame sound alert
pygame.mixer.init()
try:
    pygame.mixer.music.load("alert.mp3")  # Ensure "alert.mp3" is in the working directory
    print("🔊 Sound Loaded Successfully!")
except pygame.error as e:
    print(f"⚠️ Error loading sound: {e}")

# Load Dlib's face detector and landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# Eye landmarks
LEFT_EYE = list(range(42, 48))
RIGHT_EYE = list(range(36, 42))

# Database setup
DATABASE_FILE = "drowsiness_logs.db"

def init_db():
    """Initialize database tables if they don't exist"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Create tables for drowsiness events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS drowsiness_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ear_value REAL,
            duration_seconds REAL,
            session_id TEXT
        )
        ''')
        
        # Create table for sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            total_events INTEGER DEFAULT 0,
            total_duration_seconds REAL DEFAULT 0
        )
        ''')
        
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

# Initialize database on startup
init_db()

# Create or get current session ID
current_session_id = str(uuid.uuid4())
try:
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (id) VALUES (?)", (current_session_id,))
    conn.commit()
    conn.close()
    print(f"📝 Started new session: {current_session_id}")
except Exception as e:
    print(f"❌ Error creating session: {e}")

# Function to compute EAR (Eye Aspect Ratio)
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# Constants
EAR_THRESHOLD = 0.25  # If EAR < 0.25, eyes are considered closed
CLOSED_FRAMES = 3    # Number of consecutive frames before triggering alert
frame_count = 0       # Counter for closed-eye frames
alert_active = False  # Track if alert is playing
alert_start_time = 0  # Track when alert started
drowsiness_start_time = 0  # Track when drowsiness started for duration calculation

def log_drowsiness_event(ear_value, duration_seconds):
    """Log drowsiness event to database"""
    try:
        # Print debugging info
        print(f"🔍 Logging drowsiness event: EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s")
        
        # Connect to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Log the event
        cursor.execute(
            "INSERT INTO drowsiness_events (ear_value, duration_seconds, session_id) VALUES (?, ?, ?)",
            (ear_value, duration_seconds, current_session_id)
        )
        
        # Update session stats
        cursor.execute(
            "UPDATE sessions SET total_events = total_events + 1, total_duration_seconds = total_duration_seconds + ? WHERE id = ?", 
            (duration_seconds, current_session_id)
        )
        
        # Commit and close
        conn.commit()
        conn.close()
        
        # Verify the event was logged
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drowsiness_events WHERE session_id = ?", (current_session_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✅ Logged drowsiness event: EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s (Total events: {count})")
        
        # Also log to text file as backup
        with open("drowsiness_log.txt", "a") as f:
            f.write(f"Drowsiness detected at {datetime.now()} - EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s\n")
            
    except Exception as e:
        print(f"❌ Error logging to database: {e}")
        # Log error to file
        with open("database_error.log", "a") as f:
            f.write(f"{datetime.now()}: Error logging event - {str(e)}\n")

@socketio.on('send_frame')
def handle_frame(data):
    global frame_count, alert_active, alert_start_time, drowsiness_start_time

    if not data:
        return

    # Convert Base64 image to OpenCV format
    try:
        img_data = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_data))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    except Exception as e:
        print(f"⚠️ Error processing image: {e}")
        return

    # Detect faces
    faces = detector(gray)
    print(f"🧐 Faces detected: {len(faces)}")

    if len(faces) == 0:
        frame_count = 0  # Reset count when no face detected
        return

    for face in faces:
        landmarks = predictor(gray, face)
        landmarks = np.array([(p.x, p.y) for p in landmarks.parts()])

        left_eye = landmarks[LEFT_EYE]
        right_eye = landmarks[RIGHT_EYE]

        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        ear = (left_ear + right_ear) / 2.0  # Average EAR

        print(f"👁 EAR: {ear:.2f}")

        if ear < EAR_THRESHOLD:
            frame_count += 1
            print(f"⏳ Drowsy frame count: {frame_count}/{CLOSED_FRAMES}")

            if frame_count >= CLOSED_FRAMES:
                if not alert_active:
                    drowsiness_start_time = time.time()  # Record start time of drowsiness
                    alert_active = True
                    alert_start_time = time.time()  # Store time when alert starts
                    print("🚨 Drowsiness Detected! Playing Alert Sound...")
                    
                    try:
                        pygame.mixer.music.stop()  # Stop previous sound before playing again
                        pygame.mixer.music.play(-1)  # -1 means loop indefinitely
                    except Exception as e:
                        print(f"⚠️ Error playing sound: {e}")

        else:
            # If drowsiness ends, log the event and stop the alert
            if alert_active:
                duration = time.time() - drowsiness_start_time
                log_drowsiness_event(ear, duration)
                alert_active = False
                pygame.mixer.music.stop()
                print("✅ Eyes opened, stopping alert.")
                
            frame_count = 0  # Reset counter

    socketio.emit('detection_result', {"drowsy": alert_active})  # Send status to frontend

# Add API endpoint to start/end camera session
@socketio.on('camera_status')
def camera_status(data):
    global current_session_id, alert_active
    
    try:
        status = data.get('status')
        
        if status == 'started':
            # Create a new session when camera starts
            current_session_id = str(uuid.uuid4())
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sessions (id) VALUES (?)", (current_session_id,))
            conn.commit()
            conn.close()
            print(f"📝 Started new session: {current_session_id}")
            
        elif status == 'stopped':
            # End the session when camera stops
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET end_time = CURRENT_TIMESTAMP WHERE id = ?", (current_session_id,))
            conn.commit()
            conn.close()
            print(f"✅ Ended session: {current_session_id}")
            
            # Stop alert sound if it's playing
            if alert_active:
                alert_active = False
                pygame.mixer.music.stop()
                print("🔇 Stopping alert sound - camera closed")
            
    except Exception as e:
        print(f"❌ Error updating session: {e}")

@app.route('/')
@app.route('/logs')
def serve_react_app():
    return render_template('index.html')

# Route to verify database connectivity - no auth required
@app.route('/api/db-status')
def db_status():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drowsiness_events'")
        event_table_exists = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        session_table_exists = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_table_exists = cursor.fetchone() is not None
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM drowsiness_events")
        event_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        users_count = 0
        if users_table_exists:
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "status": "connected",
            "database_file": DATABASE_FILE,
            "tables": {
                "drowsiness_events": {
                    "exists": event_table_exists,
                    "count": event_count
                },
                "sessions": {
                    "exists": session_table_exists,
                    "count": session_count
                },
                "users": {
                    "exists": users_table_exists,
                    "count": users_count
                }
            },
            "current_session": current_session_id
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Add middleware to check for authentication
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'message': 'Authentication required'}), 401
            
        # In a production environment, you should use JWT tokens or sessions
        # For simplicity, we'll use basic authentication here
        try:
            username = auth_header
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return jsonify({'message': 'Invalid authentication'}), 401
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'message': f'Authentication error: {str(e)}'}), 500
    
    return decorated

# Route to serve API for export to CSV
@app.route('/api/export-csv')
@require_auth
def export_csv():
    try:
        days = request.args.get('days', default=7, type=int)
        start_date = request.args.get('start_date', default=None)
        end_date = request.args.get('end_date', default=None)
        
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM drowsiness_events WHERE 1=1"
        params = []
        
        if start_date and end_date:
            query += " AND timestamp BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        else:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += " AND timestamp >= ?"
            params.append(date_limit)
            
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not events:
            return jsonify({"error": "No data found"}), 404
            
        # Create CSV content
        output = io.StringIO()
        headers = ["ID", "Timestamp", "EAR Value", "Duration (s)", "Session ID"]
        csv_writer = csv.writer(output)
        csv_writer.writerow(headers)
        
        for event in events:
            csv_writer.writerow([
                event['id'],
                event['timestamp'],
                event['ear_value'],
                event['duration_seconds'],
                event['session_id']
            ])
            
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=drowsiness_logs_{datetime.now().strftime('%Y-%m-%d')}.csv"}
        )
        
        return response
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add authentication routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    # Generate a random salt
    salt = secrets.token_hex(16)
    
    # Hash the password with the salt
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'message': 'Username already exists'}), 409
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username, password_hash, salt)
        )
        
        conn.commit()
        
        # Get the newly created user
        cursor.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data:
            return jsonify({'message': 'User registration failed'}), 500
        
        # Create user object to return
        user = {
            'id': user_data[0],
            'username': user_data[1],
            'created_at': user_data[2]
        }
        
        return jsonify({'message': 'User registered successfully', 'user': user}), 201
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user data
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'message': 'Invalid username or password'}), 401
        
        # Verify password
        password_hash = hashlib.sha256((password + user['salt']).encode()).hexdigest()
        
        if password_hash != user['password_hash']:
            conn.close()
            return jsonify({'message': 'Invalid username or password'}), 401
        
        # Create user object to return
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'created_at': user['created_at']
        }
        
        conn.close()
        return jsonify({'message': 'Login successful', 'user': user_data})
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'message': f'Login failed: {str(e)}'}), 500

# Protect these routes with authentication
@app.route('/api/events', methods=['GET'])
@require_auth
def get_events():
    try:
        # Parse query parameters
        days = request.args.get('days', default=7, type=int)
        start_date = request.args.get('start_date', default=None)
        end_date = request.args.get('end_date', default=None)
        
        print(f"📋 Fetching events with parameters: days={days}, start_date={start_date}, end_date={end_date}")
        
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        # Print all events in database for debugging
        cursor.execute("SELECT COUNT(*) FROM drowsiness_events")
        total_count = cursor.fetchone()[0]
        print(f"📊 Total events in database: {total_count}")
        
        # Construct the query based on filters
        query = "SELECT * FROM drowsiness_events WHERE 1=1"
        params = []
        
        if start_date and end_date:
            query += " AND timestamp BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        else:
            # Default to last N days
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += " AND timestamp >= ?"
            params.append(date_limit)
            
        query += " ORDER BY timestamp DESC"
        
        print(f"🔍 Query: {query} with params {params}")
        
        cursor.execute(query, params)
        events = [dict(row) for row in cursor.fetchall()]
        
        print(f"🔢 Events found: {len(events)}")
        
        conn.close()
        return jsonify({"events": events})
    
    except Exception as e:
        print(f"❌ Error fetching events: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/events/add', methods=['POST'])
@require_auth
def add_event():
    try:
        data = request.get_json()
        ear_value = data.get('ear_value')
        duration = data.get('duration_seconds')
        
        # Validate inputs
        if not ear_value or not duration:
            return jsonify({"error": "Missing required fields"}), 400
            
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Insert event with current session ID
        cursor.execute(
            "INSERT INTO drowsiness_events (ear_value, duration_seconds, session_id) VALUES (?, ?, ?)",
            (ear_value, duration, current_session_id)
        )
        
        # Update session stats
        cursor.execute(
            "UPDATE sessions SET total_events = total_events + 1, total_duration_seconds = total_duration_seconds + ? WHERE id = ?",
            (duration, current_session_id)
        )
        
        conn.commit()
        
        # Get the newly created event
        event_id = cursor.lastrowid
        cursor.execute("SELECT * FROM drowsiness_events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        conn.close()
        
        return jsonify({"message": "Event added successfully", "event_id": event_id})
    except Exception as e:
        print(f"❌ Error adding event: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
@require_auth
def get_sessions():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, COUNT(e.id) as event_count
            FROM sessions s 
            LEFT JOIN drowsiness_events e ON s.id = e.session_id
            GROUP BY s.id
            ORDER BY s.start_time DESC
        """)
        
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({"sessions": sessions})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_stats():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get overall stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_events,
                SUM(duration_seconds) as total_duration,
                AVG(duration_seconds) as avg_duration,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event
            FROM drowsiness_events
        """)
        
        overall = cursor.fetchone()
        
        # Get today's stats
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT 
                COUNT(*) as today_events,
                SUM(duration_seconds) as today_duration
            FROM drowsiness_events
            WHERE date(timestamp) = ?
        """, (today,))
        
        today_stats = cursor.fetchone()
        
        conn.close()
        
        # Clean None values
        total_duration = overall[1] if overall[1] is not None else 0
        avg_duration = overall[2] if overall[2] is not None else 0
        today_duration = today_stats[1] if today_stats[1] is not None else 0
        
        stats = {
            "overall": {
                "total_events": overall[0],
                "total_duration": total_duration,
                "avg_duration": avg_duration,
                "first_event": overall[3],
                "last_event": overall[4]
            },
            "today": {
                "events": today_stats[0],
                "duration": today_duration
            }
        }
        
        return jsonify(stats)
    
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

# Cleanup session when app exits
@app.teardown_appcontext
def update_session_end_time(exception=None):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET end_time = CURRENT_TIMESTAMP WHERE id = ?", (current_session_id,))
        conn.commit()
        conn.close()
        print(f"✅ Updated session end time for: {current_session_id}")
    except Exception as e:
        print(f"⚠️ Error updating session end time: {e}")

# Add a sample protected route
@app.route('/api/protected', methods=['GET'])
@require_auth
def protected():
    return jsonify({'message': 'This is a protected route'})

if __name__ == '__main__':
    print("🚀 Flask WebSocket Server Running on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
