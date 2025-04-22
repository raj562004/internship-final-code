from flask import jsonify, request, Response, render_template
import io
import csv
from datetime import datetime, timedelta

# Import from other modules
from auth import require_auth
import db

def register_routes(app):
    @app.route('/')
    @app.route('/logs')
    def serve_react_app():
        return render_template('index.html')

    # Route to verify database connectivity - no auth required
    @app.route('/api/db-status')
    def db_status():
        try:
            status = db.get_db_status()
            status["current_session"] = app.config.get('CURRENT_SESSION_ID', '')
            return jsonify(status)
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    # Route to serve API for export to CSV
    @app.route('/api/export-csv')
    @require_auth
    def export_csv():
        try:
            days = request.args.get('days', default=7, type=int)
            start_date = request.args.get('start_date', default=None)
            end_date = request.args.get('end_date', default=None)
            
            events = db.get_events(days, start_date, end_date)
            
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
        from auth import register_user
        
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Username and password are required'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        user, error = register_user(username, password)
        
        if error:
            return jsonify({'message': error}), 409 if "already exists" in error else 500
        
        return jsonify({'message': 'User registered successfully', 'user': user}), 201

    @app.route('/api/login', methods=['POST'])
    def login():
        from auth import login_user
        
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Username and password are required'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        user, error = login_user(username, password)
        
        if error:
            return jsonify({'message': error}), 401
        
        return jsonify({'message': 'Login successful', 'user': user})

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
            
            events = db.get_events(days, start_date, end_date)
            
            print(f"🔢 Events found: {len(events)}")
            
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
                
            current_session_id = app.config.get('CURRENT_SESSION_ID', '')
            event_id = db.add_event(ear_value, duration, current_session_id)
            
            if not event_id:
                return jsonify({"error": "Failed to add event"}), 500
            
            return jsonify({"message": "Event added successfully", "event_id": event_id})
        except Exception as e:
            print(f"❌ Error adding event: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/sessions', methods=['GET'])
    @require_auth
    def get_sessions():
        try:
            sessions = db.get_sessions()
            return jsonify({"sessions": sessions})
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/stats', methods=['GET'])
    @require_auth
    def get_stats():
        try:
            stats = db.get_stats()
            if stats is None:
                return jsonify({"error": "Failed to get stats"}), 500
            
            return jsonify(stats)
        
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return jsonify({"error": str(e)}), 500

    # Add a sample protected route
    @app.route('/api/protected', methods=['GET'])
    @require_auth
    def protected():
        return jsonify({'message': 'This is a protected route'})
        
    # Add endpoint to explicitly end the current session
    @app.route('/api/session/end', methods=['POST'])
    @require_auth
    def end_current_session():
        try:
            session_id = app.config.get('CURRENT_SESSION_ID', '')
            if not session_id:
                return jsonify({'error': 'No active session to end'}), 400
            
            db.end_session(session_id)
            app.config['CURRENT_SESSION_ID'] = ''  # Clear the session ID
            
            # Get stats to return updated info
            stats = db.get_stats()
            
            return jsonify({
                'message': 'Session ended successfully',
                'session_id': session_id,
                'stats': stats
            })
        except Exception as e:
            print(f"❌ Error ending session via API: {e}")
            return jsonify({'error': str(e)}), 500

    # Get current session runtime
    @app.route('/api/session/runtime', methods=['GET'])
    @require_auth
    def get_session_runtime():
        try:
            session_id = app.config.get('CURRENT_SESSION_ID', '')
            active = bool(session_id)
            
            print(f"📊 Runtime request - Active session: {active}, ID: {session_id[:8] if session_id else 'None'}")
            
            if not active:
                # No active session, return today's totals from stats
                stats = db.get_stats()
                today_stats = stats.get('today', {})
                
                print(f"📊 No active session - Today's session time: {today_stats.get('session_time', 0)}")
                
                return jsonify({
                    'active': False,
                    'runtime': 0,
                    'today_stats': today_stats,
                    'message': 'No active session'
                })
            
            # Get runtime for the active session
            runtime = db.get_session_age(session_id)
            print(f"📊 Active session runtime: {runtime:.2f}s")
            
            # Get today's totals including previous completed sessions
            stats = db.get_stats()
            today_stats = stats.get('today', {})
            
            # Always make sure session_time is a number
            if 'session_time' in today_stats and today_stats['session_time'] is not None:
                try:
                    session_time = float(today_stats['session_time'])
                except (ValueError, TypeError):
                    session_time = 0
            else:
                session_time = 0
                
            # For active sessions, session_time should include the current runtime
            # But we need to be careful not to double-count
            if runtime > session_time:
                today_stats['session_time'] = runtime
                print(f"📊 Updated session_time to match active runtime: {runtime:.2f}s")
            else:
                print(f"📊 Current session_time from stats: {session_time:.2f}s")
                
            # Force runtime to be a float to avoid JSON serialization issues
            runtime = float(runtime)
                
            return jsonify({
                'active': True,
                'session_id': session_id,
                'runtime': runtime,
                'today_stats': today_stats,
                'message': 'Active session found'
            })
        except Exception as e:
            print(f"❌ Error getting session runtime: {e}")
            return jsonify({'error': str(e)}), 500
            
    # Toggle between EAR and model-based detection
    @app.route('/api/detection/toggle-model', methods=['POST'])
    @require_auth
    def toggle_detection_model():
        try:
            import detection
            
            # Toggle the use_eye_model flag
            detection.use_eye_model = not detection.use_eye_model
            
            return jsonify({
                'use_eye_model': detection.use_eye_model,
                'message': f"Now using {'eye state model' if detection.use_eye_model else 'traditional EAR method'}"
            })
        except Exception as e:
            print(f"❌ Error toggling detection model: {e}")
            return jsonify({'error': str(e)}), 500
            
    # Reset logs data
    @app.route('/api/logs/reset', methods=['POST'])
    @require_auth
    def reset_logs_data():
        try:
            success = db.reset_daily_logs()
            
            if success:
                # Start a fresh session
                current_session_id = db.create_session()
                app.config['CURRENT_SESSION_ID'] = current_session_id
                
                return jsonify({
                    'success': True,
                    'message': 'Logs data reset successfully',
                    'new_session_id': current_session_id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to reset logs data'
                }), 500
                
        except Exception as e:
            print(f"❌ Error resetting logs: {e}")
            return jsonify({'error': str(e)}), 500 