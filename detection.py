import cv2
import dlib
import numpy as np
from scipy.spatial import distance
import pygame
import time
import base64
from PIL import Image
import io
import tensorflow as tf
import os

# Initialize Tensorflow model for eye state detection
try:
    # Print current directory for debugging
    print(f"Current directory: {os.getcwd()}")
    print(f"Looking for model file: {os.path.exists('eye_state_model.h5')}")
    
    # Load model with explicit path to ensure it's found
    model_path = os.path.join(os.getcwd(), "eye_state_model.h5")
    print(f"Loading model from: {model_path}")
    
    # Load with error verbosity
    eye_model = tf.keras.models.load_model(model_path, compile=False)
    
    # Print model summary to verify it loaded correctly
    eye_model.summary()
    
    print("🧠 Eye state model loaded successfully!")
    use_eye_model = True
except Exception as e:
    print(f"⚠️ Error loading eye state model: {e}")
    print("⚠️ Falling back to traditional EAR method")
    use_eye_model = False

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

# Constants
EAR_THRESHOLD = 0.25  # If EAR < 0.25, eyes are considered closed
CLOSED_FRAMES = 3    # Number of consecutive frames before triggering alert
EYE_IMG_SIZE = (24, 24)  # Size for eye model input

# Global variables
frame_count = 0       # Counter for closed-eye frames
alert_active = False  # Track if alert is playing
alert_start_time = 0  # Track when alert started
drowsiness_start_time = 0  # Track when drowsiness started for duration calculation

# Function to compute EAR (Eye Aspect Ratio)
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# Function to extract and preprocess eye image for the model
def extract_eye_region(frame, eye_landmarks):
    try:
        # Get bounding box of eye
        x_min = int(min(point[0] for point in eye_landmarks))
        x_max = int(max(point[0] for point in eye_landmarks))
        y_min = int(min(point[1] for point in eye_landmarks))
        y_max = int(max(point[1] for point in eye_landmarks))
        
        # Add margin
        margin = 5
        x_min, x_max = max(0, x_min - margin), min(frame.shape[1], x_max + margin)
        y_min, y_max = max(0, y_min - margin), min(frame.shape[0], y_max + margin)
        
        # Safety check
        if x_min >= x_max or y_min >= y_max:
            print("⚠️ Invalid eye region dimensions")
            return None
            
        # Extract eye region
        eye_region = frame[y_min:y_max, x_min:x_max]
        
        # Check if eye region is valid
        if eye_region.size == 0 or eye_region.shape[0] == 0 or eye_region.shape[1] == 0:
            print("⚠️ Empty eye region")
            return None
            
        # Resize to expected model input size
        eye_region = cv2.resize(eye_region, EYE_IMG_SIZE)
        
        # Keep as RGB (3 channels) as the model expects it
        # Just normalize the values to 0-1 range
        eye_region = eye_region.astype(np.float32) / 255.0
        
        # Add batch dimension
        eye_region = np.expand_dims(eye_region, axis=0)
        
        # Debug output
        print(f"Processed eye region shape: {eye_region.shape}")
        
        return eye_region
    except Exception as e:
        print(f"⚠️ Error extracting eye region: {e}")
        return None

def predict_eye_state(frame, left_eye_landmarks, right_eye_landmarks):
    """
    Use eye state model to predict if eyes are open or closed
    Returns True if eyes are closed, False if open
    """
    if not use_eye_model:
        # Fall back to EAR method if model isn't available
        left_ear = eye_aspect_ratio(left_eye_landmarks)
        right_ear = eye_aspect_ratio(right_eye_landmarks)
        ear = (left_ear + right_ear) / 2.0
        print(f"👁 Using EAR method: {ear:.2f} (threshold: {EAR_THRESHOLD})")
        return ear < EAR_THRESHOLD, ear
    
    try:
        # Extract eye regions
        left_eye_img = extract_eye_region(frame, left_eye_landmarks)
        right_eye_img = extract_eye_region(frame, right_eye_landmarks)
        
        # If either eye region is invalid, fall back to EAR
        if left_eye_img is None or right_eye_img is None:
            print("⚠️ Invalid eye regions, falling back to EAR")
            left_ear = eye_aspect_ratio(left_eye_landmarks)
            right_ear = eye_aspect_ratio(right_eye_landmarks)
            ear = (left_ear + right_ear) / 2.0
            print(f"👁 Fallback EAR: {ear:.2f}")
            return ear < EAR_THRESHOLD, ear
        
        # Debug input shape
        print(f"Model input shape: {left_eye_img.shape}")
        
        # Predict eye state (0=closed, 1=open)
        # Use model.predict with less verbosity
        try:
            # Less verbose prediction
            left_pred = eye_model.predict(left_eye_img, verbose=0)
            right_pred = eye_model.predict(right_eye_img, verbose=0)
        except Exception as model_err:
            print(f"⚠️ Error during model prediction: {model_err}")
            # Try one more time with different approach
            try:
                # Try calling model directly
                left_pred = eye_model(left_eye_img, training=False).numpy()
                right_pred = eye_model(right_eye_img, training=False).numpy()
            except Exception as call_err:
                print(f"⚠️ Direct model call also failed: {call_err}")
                # Fall back to EAR
                left_ear = eye_aspect_ratio(left_eye_landmarks)
                right_ear = eye_aspect_ratio(right_eye_landmarks)
                ear = (left_ear + right_ear) / 2.0
                return ear < EAR_THRESHOLD, ear
        
        # Debug raw predictions
        print(f"Predictions - Left: {left_pred.flatten()[0]:.3f}, Right: {right_pred.flatten()[0]:.3f}")
        
        # Extract prediction value based on model output shape
        left_val = left_pred.flatten()[0]
        right_val = right_pred.flatten()[0]
            
        # Average confidence (closer to 0 means more closed)
        avg_conf = (left_val + right_val) / 2.0
        
        # Calculate EAR anyway for logging
        left_ear = eye_aspect_ratio(left_eye_landmarks)
        right_ear = eye_aspect_ratio(right_eye_landmarks)
        ear = (left_ear + right_ear) / 2.0
        
        print(f"👁 Model confidence: {avg_conf:.2f}, EAR: {ear:.2f}")
        
        # Eyes closed if confidence < 0.5
        return avg_conf < 0.5, ear
    except Exception as e:
        print(f"⚠️ Error in model prediction: {e}")
        # Fall back to EAR method
        left_ear = eye_aspect_ratio(left_eye_landmarks)
        right_ear = eye_aspect_ratio(right_eye_landmarks)
        ear = (left_ear + right_ear) / 2.0
        return ear < EAR_THRESHOLD, ear

def process_frame(data, log_drowsiness_callback):
    """
    Process a frame to detect drowsiness
    
    Args:
        data: Base64 encoded image data
        log_drowsiness_callback: Callback function to log drowsiness event
        
    Returns:
        dict: Status of drowsiness detection
    """
    global frame_count, alert_active, alert_start_time, drowsiness_start_time
    
    if not data:
        return {"drowsy": False}

    # Convert Base64 image to OpenCV format
    try:
        img_data = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_data))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    except Exception as e:
        print(f"⚠️ Error processing image: {e}")
        return {"drowsy": False}

    # Detect faces
    faces = detector(gray)
    print(f"🧐 Faces detected: {len(faces)}")

    if len(faces) == 0:
        frame_count = 0  # Reset count when no face detected
        return {"drowsy": False}

    # Store eye confidence for UI feedback
    confidence = 0.0
    
    for face in faces:
        landmarks = predictor(gray, face)
        landmarks = np.array([(p.x, p.y) for p in landmarks.parts()])

        left_eye = landmarks[LEFT_EYE]
        right_eye = landmarks[RIGHT_EYE]
        
        # Variable to track if eyes are closed
        eyes_closed = False
        ear = 0.0
        
        # If we're using the AI model
        if use_eye_model:
            # Extract eye regions for prediction
            left_eye_img = extract_eye_region(frame, left_eye)
            right_eye_img = extract_eye_region(frame, right_eye)
            
            if left_eye_img is not None and right_eye_img is not None:
                try:
                    # Get predictions (0-1 where 1 is open eyes)
                    left_pred = eye_model.predict(left_eye_img, verbose=0).flatten()[0]
                    right_pred = eye_model.predict(right_eye_img, verbose=0).flatten()[0]
                    
                    # Calculate ear for logging
                    left_ear = eye_aspect_ratio(left_eye)
                    right_ear = eye_aspect_ratio(right_eye)
                    ear = (left_ear + right_ear) / 2.0
                    
                    print(f"Predictions - Left: {left_pred:.3f}, Right: {right_pred:.3f}")
                    
                    # More sensitive detection: consider eyes closed if either eye prediction is below 0.7
                    eyes_closed = left_pred < 0.7 or right_pred < 0.7
                    
                    # Calculate confidence for UI display
                    if eyes_closed:
                        # Average of how closed both eyes are
                        confidence = 1.0 - ((left_pred + right_pred) / 2.0)
                    else:
                        # Average of how open both eyes are
                        confidence = (left_pred + right_pred) / 2.0
                        
                    print(f"👁 AI Model - Eyes {'closed' if eyes_closed else 'open'} (threshold: 0.7, confidence: {confidence:.2f})")
                    
                except Exception as e:
                    print(f"⚠️ Error in model prediction: {e}")
                    # Fall back to EAR
                    left_ear = eye_aspect_ratio(left_eye)
                    right_ear = eye_aspect_ratio(right_eye)
                    ear = (left_ear + right_ear) / 2.0
                    eyes_closed = ear < EAR_THRESHOLD
                    confidence = 0.5  # Neutral confidence on error
            else:
                # Fall back to EAR if eye regions couldn't be extracted
                left_ear = eye_aspect_ratio(left_eye)
                right_ear = eye_aspect_ratio(right_eye)
                ear = (left_ear + right_ear) / 2.0
                eyes_closed = ear < EAR_THRESHOLD
                confidence = 0.5  # Neutral confidence
        else:
            # Traditional EAR method
            left_ear = eye_aspect_ratio(left_eye)
            right_ear = eye_aspect_ratio(right_eye)
            ear = (left_ear + right_ear) / 2.0
            eyes_closed = ear < EAR_THRESHOLD
            
            # For EAR method, use normalized EAR as confidence
            if eyes_closed:
                # Low EAR means high confidence in closed state
                confidence = 1.0 - (ear / EAR_THRESHOLD)
            else:
                # High EAR means high confidence in open state
                confidence = min(1.0, ear / (EAR_THRESHOLD * 1.5))
                
            print(f"👁 EAR method: {ear:.2f} (threshold: {EAR_THRESHOLD})")

        if eyes_closed:
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
                log_drowsiness_callback(ear, duration)
                alert_active = False
                pygame.mixer.music.stop()
                print("✅ Eyes opened, stopping alert.")
                
            frame_count = 0  # Reset counter

    # Return drowsiness status and confidence
    return {
        "drowsy": alert_active,
        "confidence": round(confidence * 100) / 100,  # Round to 2 decimal places
        "using_model": use_eye_model
    }

def stop_alert():
    """Stop the alert sound if it's playing"""
    global alert_active
    if alert_active:
        alert_active = False
        pygame.mixer.music.stop()
        print("🔇 Stopping alert sound") 