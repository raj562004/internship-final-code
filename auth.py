import hashlib
import secrets
import sqlite3
from functools import wraps
from flask import request, jsonify

# Database file
DATABASE_FILE = "drowsiness_logs.db"

def require_auth(f):
    """Middleware to check for authentication"""
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

def register_user(username, password):
    """Register a new user"""
    try:
        # Generate a random salt
        salt = secrets.token_hex(16)
        
        # Hash the password with the salt
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return None, "Username already exists"
        
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
            return None, "User registration failed"
        
        # Create user object to return
        user = {
            'id': user_data[0],
            'username': user_data[1],
            'created_at': user_data[2]
        }
        
        return user, None
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return None, f"Registration failed: {str(e)}"

def login_user(username, password):
    """Authenticate a user"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user data
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return None, "Invalid username or password"
        
        # Verify password
        password_hash = hashlib.sha256((password + user['salt']).encode()).hexdigest()
        
        if password_hash != user['password_hash']:
            conn.close()
            return None, "Invalid username or password"
        
        # Create user object to return
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'created_at': user['created_at']
        }
        
        conn.close()
        return user_data, None
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None, f"Login failed: {str(e)}" 