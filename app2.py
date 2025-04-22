import cv2
import dlib
import numpy as np
from scipy.spatial import distance
import pyttsx3
import datetime
import threading
import random
 # To detect OS

# Detect OS and set TTS engine accordingly

engine = pyttsx3.init('sapi5')  # Use eSpeak on Linux
 # Use SAPI5 on Windows

# Load Dlib's face detector and 68-landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# Eye landmarks (left and right)
LEFT_EYE = list(range(42, 48))
RIGHT_EYE = list(range(36, 42))

# Function to compute Eye Aspect Ratio (EAR)
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# Drowsiness detection threshold
EAR_THRESHOLD = 0.25
CLOSED_FRAMES = 20
frame_count = 0
alert_active = False

# List of random wake-up messages
wake_up_messages = [
    # "Wake up! Stay focused!",
    # "Hey! Don't sleep while driving!",
    # "Alert! Wake up now!",
    # "Open your eyes! Stay safe!",
    # "Drowsiness detected! Foce road!"
    
]

# Open log file
log_file = open("drowsiness_log.txt", "a")

# Function to play random alert in a separate thread
def speak_alert():
    global alert_active
    if not alert_active:
        alert_active = True
        message = random.choice(wake_up_messages)
        print(f"Speaking: {message}")  # Debugging log
        engine.say(message)
        engine.runAndWait()
        alert_active = False

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector(gray)

    for face in faces:
        landmarks = predictor(gray, face)
        landmarks = np.array([(p.x, p.y) for p in landmarks.parts()])

        left_eye = landmarks[LEFT_EYE]
        right_eye = landmarks[RIGHT_EYE]

        left_EAR = eye_aspect_ratio(left_eye)
        right_EAR = eye_aspect_ratio(right_eye)
        avg_EAR = (left_EAR + right_EAR) / 2.0

        for (x, y) in np.vstack((left_eye, right_eye)):
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)

        if avg_EAR < EAR_THRESHOLD:
            frame_count += 1
            if frame_count >= CLOSED_FRAMES:
                cv2.putText(frame, "DROWSINESS ALERT!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
                print("DROWSINESS ALERT! Wake up!")
                log_file.write(f"Drowsiness detected at {datetime.datetime.now()}\n")
                log_file.flush()
                # Run alert in a separate thread
                threading.Thread(target=speak_alert).start()
        else:
            frame_count = 0

    cv2.imshow("Drowsiness Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

log_file.close()
cap.release()
cv2.destroyAllWindows()