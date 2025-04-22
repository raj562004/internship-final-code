import db
import detection

def register_socket_handlers(socketio, app):
    """Register all Socket.IO event handlers"""
    
    @socketio.on('send_frame')
    def handle_frame(data):
        """Handle incoming frame data for drowsiness detection"""
        
        def log_drowsiness(ear_value, duration_seconds):
            """Callback to log drowsiness events"""
            current_session_id = app.config.get('CURRENT_SESSION_ID', '')
            db.log_drowsiness_event(ear_value, duration_seconds, current_session_id)
        
        # Process the frame and detect drowsiness
        result = detection.process_frame(data, log_drowsiness)
        
        # Send the result back to the client
        socketio.emit('detection_result', result)
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connect event - ensure previous sessions are closed"""
        try:
            # End any dangling sessions
            dangling_sessions = db.get_open_sessions()
            for session_id in dangling_sessions:
                db.end_session(session_id)
                print(f"Ending dangling session on connect: {session_id}")
        except Exception as e:
            print(f"Error handling connect: {e}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnect event - ensure current session is closed"""
        try:
            current_session_id = app.config.get('CURRENT_SESSION_ID', '')
            if current_session_id:
                db.end_session(current_session_id)
                print(f"Ending session on disconnect: {current_session_id}")
                
            # Stop alert sound if it's playing
            detection.stop_alert()
        except Exception as e:
            print(f"Error handling disconnect: {e}")
    
    @socketio.on('camera_status')
    def camera_status(data):
        """Handle camera start/stop events"""
        try:
            status = data.get('status')
            
            if status == 'started':
                # First, end any active session to avoid overlapping sessions
                current_session_id = app.config.get('CURRENT_SESSION_ID', '')
                if current_session_id:
                    db.end_session(current_session_id)
                    print(f"Ending previous session before starting new one: {current_session_id}")
                
                # Also end any other open sessions
                dangling_sessions = db.get_open_sessions()
                for session_id in dangling_sessions:
                    if session_id != current_session_id:
                        db.end_session(session_id)
                        print(f"Closing dangling session: {session_id}")
                
                # Create new session with current timestamp
                new_session_id = db.create_session()
                app.config['CURRENT_SESSION_ID'] = new_session_id
                app.config['CAMERA_ACTIVE'] = True
                print(f"📝 Started new camera session: {new_session_id}")
                
                # Send acknowledgment to client with more details
                session_info = db.get_session_info(new_session_id)
                socketio.emit('session_started', {
                    'session_id': new_session_id,
                    'start_time': session_info.get('start_time') if session_info else None,
                    'message': 'Session started successfully'
                })
                
            elif status == 'stopped':
                # End the session when camera stops
                current_session_id = app.config.get('CURRENT_SESSION_ID', '')
                if current_session_id:
                    # Ensure end time is set
                    db.end_session(current_session_id)
                    print(f"✅ Ended camera session: {current_session_id}")
                    app.config['CAMERA_ACTIVE'] = False
                    
                    # Send session info to client
                    session_info = db.get_session_info(current_session_id)
                    
                    # Get total duration
                    duration = session_info.get('duration', 0) if session_info else 0
                    
                    # Send detailed session info including duration
                    socketio.emit('session_ended', {
                        'session_id': current_session_id,
                        'duration': duration,
                        'start_time': session_info.get('start_time') if session_info else None,
                        'end_time': session_info.get('end_time') if session_info else None,
                        'message': 'Session ended successfully'
                    })
                    
                    # Explicitly trigger a stats update
                    stats = db.get_stats()
                    socketio.emit('stats_updated', stats)
                else:
                    print("⚠️ No active session to end")
                    socketio.emit('session_ended', {
                        'error': 'No active session to end',
                        'session_id': None
                    })
                
                # Stop alert sound if it's playing
                detection.stop_alert()
                
        except Exception as e:
            print(f"❌ Error updating session: {e}")
            socketio.emit('session_error', {'error': str(e)}) 