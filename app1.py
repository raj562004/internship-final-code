import eventlet
eventlet.monkey_patch()  # Allows WebSockets to work smoothly

from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
import threading
import time

# Import our modules
import db
import detection
import routes
import socket_handlers

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable WebSockets

# Initialize database
db.init_db()

# Setup initial session
current_session_id = db.create_session()
app.config['CURRENT_SESSION_ID'] = current_session_id

# Register API routes
routes.register_routes(app)

# Register Socket.IO event handlers
socket_handlers.register_socket_handlers(socketio, app)

# Background task to clean up stale sessions
def cleanup_stale_sessions():
    """Background task to close any open sessions that are too old (> 30 minutes)"""
    while True:
        try:
            print("🧹 Checking for stale sessions...")
            open_sessions = db.get_open_sessions()
            
            if open_sessions:
                for session_id in open_sessions:
                    # Check if session is too old
                    session_info = db.get_session_info(session_id)
                    if session_info and 'start_time' in session_info:
                        # Close sessions that have been open for more than 30 minutes
                        session_age = db.get_session_age(session_id)
                        if session_age > 30 * 60:  # 30 minutes in seconds
                            print(f"Closing stale session {session_id[:8]} (age: {session_age/60:.1f} minutes)")
                            db.end_session(session_id)
                
                # Clear current session if it's stale
                current_session_id = app.config.get('CURRENT_SESSION_ID', '')
                if current_session_id and current_session_id in open_sessions:
                    # If the current session was closed, clear it from app config
                    app.config['CURRENT_SESSION_ID'] = ''
            
            # Sleep for 5 minutes before checking again
            time.sleep(5 * 60)
        except Exception as e:
            print(f"❌ Error in cleanup task: {e}")
            time.sleep(60)  # Sleep for 1 minute if there's an error

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_stale_sessions, daemon=True)
cleanup_thread.start()

# Cleanup session when app exits
@app.teardown_appcontext
def update_session_end_time(exception=None):
    try:
        current_session_id = app.config.get('CURRENT_SESSION_ID', '')
        db.end_session(current_session_id)
        print(f"✅ Updated session end time for: {current_session_id}")
    except Exception as e:
        print(f"⚠️ Error updating session end time: {e}")

if __name__ == '__main__':
    print("🚀 Flask WebSocket Server Running on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)