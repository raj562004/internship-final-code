import sqlite3
import datetime
from datetime import datetime, timedelta
import uuid
import os

# Database setup - use absolute path that works in ephemeral environments
DATABASE_DIR = os.environ.get('DATABASE_DIR', os.path.dirname(os.path.abspath(__file__)))
DATABASE_FILE = os.path.join(DATABASE_DIR, "drowsiness_logs.db")

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

def create_session():
    """Create a new session and return its ID"""
    session_id = str(uuid.uuid4())
    try:
        # Format current timestamp in ISO format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sessions (id, start_time) VALUES (?, ?)", (session_id, current_time))
        conn.commit()
        conn.close()
        print(f"📝 Started new session: {session_id} at {current_time}")
        return session_id
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None

def end_session(session_id):
    """End a session by updating its end time"""
    try:
        if not session_id:
            print("⚠️ No session ID provided to end_session")
            return False
            
        # Check if session exists first
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", (session_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            print(f"⚠️ Cannot end session, ID not found: {session_id[:8]}")
            conn.close()
            return False
            
        # Check if session already ended
        cursor.execute("SELECT end_time FROM sessions WHERE id = ?", (session_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            print(f"ℹ️ Session already ended: {session_id[:8]} at {result[0]}")
            conn.close()
            return True
            
        # Format current timestamp in ISO format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update with explicit timestamp
        cursor.execute("UPDATE sessions SET end_time = ? WHERE id = ?", (current_time, session_id))
        conn.commit()
        
        # Verify update
        cursor.execute("SELECT end_time FROM sessions WHERE id = ?", (session_id,))
        end_time = cursor.fetchone()
        
        # Get the session duration for logging
        if end_time and end_time[0]:
            cursor.execute("""
                SELECT 
                    start_time,
                    (julianday(?) - julianday(start_time)) * 86400 as duration
                FROM sessions 
                WHERE id = ?
            """, (current_time, session_id))
            
            session_info = cursor.fetchone()
            if session_info:
                start_time, duration = session_info
                print(f"✅ Ended session: {session_id[:8]} - Started: {start_time}, Ended: {current_time}, Duration: {duration:.2f}s")
        
        conn.close()
        
        return True
    except Exception as e:
        print(f"❌ Error updating session: {e}")
        import traceback
        traceback.print_exc()
        return False

def log_drowsiness_event(ear_value, duration_seconds, session_id):
    """Log drowsiness event to database"""
    try:
        # Print debugging info
        print(f"🔍 Logging drowsiness event: EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s")
        
        # Format current timestamp in ISO format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Connect to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Log the event with explicit timestamp
        cursor.execute(
            "INSERT INTO drowsiness_events (timestamp, ear_value, duration_seconds, session_id) VALUES (?, ?, ?, ?)",
            (current_time, ear_value, duration_seconds, session_id)
        )
        
        # Update session stats
        cursor.execute(
            "UPDATE sessions SET total_events = total_events + 1, total_duration_seconds = total_duration_seconds + ? WHERE id = ?", 
            (duration_seconds, session_id)
        )
        
        # Commit and close
        conn.commit()
        conn.close()
        
        # Verify the event was logged
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drowsiness_events WHERE session_id = ?", (session_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✅ Logged drowsiness event: EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s (Total events: {count})")
        
        # Also log to text file as backup
        with open("drowsiness_log.txt", "a") as f:
            f.write(f"Drowsiness detected at {current_time} - EAR={ear_value:.2f}, Duration={duration_seconds:.2f}s\n")
            
    except Exception as e:
        print(f"❌ Error logging to database: {e}")
        # Log error to file
        with open("database_error.log", "a") as f:
            f.write(f"{datetime.now()}: Error logging event - {str(e)}\n")

def get_events(days=7, start_date=None, end_date=None):
    """Get drowsiness events based on filters"""
    try:
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
        
        return events
    except Exception as e:
        print(f"❌ Error fetching events: {e}")
        return []

def get_session_info(session_id):
    """Get detailed information about a single session"""
    try:
        if not session_id:
            return None
            
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get session data with duration calculation
        cursor.execute("""
            SELECT 
                s.id,
                datetime(s.start_time) as start_time,
                datetime(s.end_time) as end_time,
                s.total_events,
                s.total_duration_seconds,
                CASE
                    WHEN s.end_time IS NULL THEN 0
                    ELSE (julianday(s.end_time) - julianday(s.start_time)) * 86400
                END as duration,
                (SELECT COUNT(*) FROM drowsiness_events WHERE session_id = s.id) as event_count
            FROM sessions s
            WHERE s.id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        session = dict(row) if row else None
        
        conn.close()
        
        if session:
            print(f"📊 Session {session_id[:8]}: Duration = {session.get('duration', 0):.2f}s, Events = {session.get('event_count', 0)}")
        
        return session
    except Exception as e:
        print(f"❌ Error fetching session info: {e}")
        return None

def get_sessions():
    """Get all sessions with event counts and accurate durations"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ensure we get proper ISO format dates and accurate duration calculation
        cursor.execute("""
            SELECT 
                s.id,
                datetime(s.start_time) as start_time,
                datetime(s.end_time) as end_time,
                s.total_events,
                s.total_duration_seconds,
                CASE
                    WHEN s.end_time IS NULL THEN 0
                    ELSE (julianday(s.end_time) - julianday(s.start_time)) * 86400
                END as duration,
                (SELECT COUNT(*) FROM drowsiness_events WHERE session_id = s.id) as event_count
            FROM sessions s 
            ORDER BY s.start_time DESC
        """)
        
        sessions = [dict(row) for row in cursor.fetchall()]
        
        # Debug session data
        print(f"📊 Retrieved {len(sessions)} sessions")
        total_duration = 0
        for session in sessions[:3]:  # Print first 3 sessions for debugging
            start = session.get('start_time', 'None')
            end = session.get('end_time', 'None')
            duration = session.get('duration', 0)
            total_duration += duration
            print(f"  Session {session['id'][:8]}: {start} to {end} - Duration: {duration:.2f}s")
        
        print(f"  Total duration of all sessions: {total_duration:.2f}s")
        
        conn.close()
        
        return sessions
    except Exception as e:
        print(f"❌ Error fetching sessions: {e}")
        return []

def get_stats():
    """Get overall and today's stats"""
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
        
        # Get today's stats - use date() function for proper comparison
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT 
                COUNT(*) as today_events,
                SUM(duration_seconds) as today_duration
            FROM drowsiness_events
            WHERE date(timestamp) = ?
        """, (today,))
        
        today_stats = cursor.fetchone()
        
        # Get today's session durations - more accurate camera runtime
        cursor.execute("""
            SELECT 
                SUM(CASE
                    WHEN end_time IS NULL THEN 
                        (julianday('now') - julianday(start_time)) * 86400
                    ELSE 
                        (julianday(end_time) - julianday(start_time)) * 86400
                END) as total_session_time
            FROM sessions
            WHERE date(start_time) = ?
        """, (today,))
        
        session_stats = cursor.fetchone()
        total_session_time = session_stats[0] if session_stats and session_stats[0] is not None else 0
        
        conn.close()
        
        # Clean None values
        total_duration = overall[1] if overall[1] is not None else 0
        avg_duration = overall[2] if overall[2] is not None else 0
        today_duration = today_stats[1] if today_stats[1] is not None else 0
        
        # Debug print for today's stats
        print(f"📊 Today's stats: Events={today_stats[0]}, Duration={today_duration}, Session Time={total_session_time:.2f}s")
        
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
                "duration": today_duration,
                "session_time": total_session_time
            }
        }
        
        return stats
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return None

def add_event(ear_value, duration, session_id):
    """Add a drowsiness event manually"""
    try:
        # Format current timestamp in ISO format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Insert event with current session ID and timestamp
        cursor.execute(
            "INSERT INTO drowsiness_events (timestamp, ear_value, duration_seconds, session_id) VALUES (?, ?, ?, ?)",
            (current_time, ear_value, duration, session_id)
        )
        
        # Update session stats
        cursor.execute(
            "UPDATE sessions SET total_events = total_events + 1, total_duration_seconds = total_duration_seconds + ? WHERE id = ?",
            (duration, session_id)
        )
        
        conn.commit()
        
        # Get the newly created event
        event_id = cursor.lastrowid
        
        conn.close()
        
        return event_id
    except Exception as e:
        print(f"❌ Error adding event: {e}")
        return None

def get_db_status():
    """Get database status information"""
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
        
        return {
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
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def get_open_sessions():
    """Get all session IDs for sessions that don't have an end_time set"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Find sessions without end_time
        cursor.execute("""
            SELECT id FROM sessions 
            WHERE end_time IS NULL OR end_time = ''
        """)
        
        sessions = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # Debug info
        if sessions:
            print(f"📊 Found {len(sessions)} open sessions that need to be closed")
            for session_id in sessions[:5]:  # Show first 5
                print(f"  Open session: {session_id[:8]}")
        
        return sessions
    except Exception as e:
        print(f"❌ Error fetching open sessions: {e}")
        return []

def get_session_age(session_id):
    """Get the age of a session in seconds"""
    try:
        if not session_id:
            print("⚠️ No session ID provided")
            return 0
            
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # First check if the session exists
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", (session_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            print(f"⚠️ Session not found in database: {session_id[:8]}")
            conn.close()
            return 0
        
        # Get the start time of the session
        cursor.execute("SELECT start_time, end_time FROM sessions WHERE id = ?", (session_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"⚠️ Session not found: {session_id[:8]}")
            return 0
            
        start_time_str, end_time_str = result
        
        if not start_time_str:
            print(f"⚠️ Session has no start time: {session_id[:8]}")
            return 0
            
        # Parse the timestamps
        try:
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            print(f"📊 Parsed start time: {start_time}")
        except ValueError:
            # Try alternative format if needed
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
                print(f"📊 Parsed start time (alt format): {start_time}")
            except ValueError:
                print(f"⚠️ Unable to parse start time: {start_time_str}")
                return 0
        
        # If end_time is None, calculate age based on current time
        if not end_time_str:
            # For active sessions, use current time
            current_time = datetime.now()
            age_seconds = (current_time - start_time).total_seconds()
            
            if age_seconds < 0:
                print(f"⚠️ Negative session age: {age_seconds}s - Session might have clock issues")
                # Use a safe minimum value
                age_seconds = 0
            
            print(f"📊 Active session {session_id[:8]}: Start={start_time}, Now={current_time}, Duration={age_seconds:.2f}s (still running)")
        else:
            # For completed sessions, use end_time
            try:
                end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                print(f"📊 Parsed end time: {end_time}")
            except ValueError:
                # Try alternative format if needed
                try:
                    end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%S")
                    print(f"📊 Parsed end time (alt format): {end_time}")
                except ValueError:
                    print(f"⚠️ Unable to parse end time: {end_time_str}")
                    # Fallback to current time
                    end_time = datetime.now()
                    print(f"📊 Using current time as end time: {end_time}")
            
            age_seconds = (end_time - start_time).total_seconds()
            
            if age_seconds < 0:
                print(f"⚠️ Negative session age: {age_seconds}s - Clock issues detected")
                # Use a safe minimum value
                age_seconds = 0
                
            print(f"📊 Completed session {session_id[:8]}: Start={start_time}, End={end_time}, Duration={age_seconds:.2f}s")
        
        return age_seconds
            
    except Exception as e:
        print(f"❌ Error calculating session age: {e}")
        import traceback
        traceback.print_exc()
        return 0

def reset_daily_logs():
    """Reset logs data for the current day - called upon login"""
    try:
        # Get today's date for filtering
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # End any active sessions
        cursor.execute("""
            UPDATE sessions 
            SET end_time = datetime('now')
            WHERE end_time IS NULL OR end_time = ''
        """)
        
        # Delete today's drowsiness events
        cursor.execute("""
            DELETE FROM drowsiness_events
            WHERE date(timestamp) = ?
        """, (today,))
        
        # Delete today's sessions
        cursor.execute("""
            DELETE FROM sessions
            WHERE date(start_time) = ?
        """, (today,))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Reset logs data for {today}")
        return True
    except Exception as e:
        print(f"❌ Error resetting logs: {e}")
        return False 