import base64
import cv2
import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pygame

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Load the trained model
model = tf.keras.models.load_model("drowsiness_model2.h5")

# Initialize pygame for playing alert sound
pygame.mixer.init()
ALERT_SOUND = "alert.mp3"  # Ensure this file is in the same directory

def play_alert():
    pygame.mixer.music.load(ALERT_SOUND)
    pygame.mixer.music.play()

# Function to process the image and predict drowsiness
def predict_drowsiness(image_data):
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Preprocess the image (resize to 224x224 for the model)
        img = cv2.resize(img, (224, 224))  # Change to match model input size
        img = img / 255.0  # Normalize
        img = np.expand_dims(img, axis=0)  # Add batch dimension

        # Predict drowsiness
        prediction = model.predict(img)

        # Interpret result based on your logic
        if prediction[0][0] > 0.5:
            result = "Not Drowsy 😃"
        else:
            result = "Drowsy 😴"
            play_alert()  # Play alert only if drowsy

        return result
    except Exception as e:
        return str(e)

# WebSocket route to receive images and send predictions
@socketio.on("frame")
def handle_frame(data):
    result = predict_drowsiness(data["image"])
    emit("prediction", {"result": result})

# Start Flask server
if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
