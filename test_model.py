import tensorflow as tf
import numpy as np
import os
import cv2

print(f"TensorFlow version: {tf.__version__}")
print(f"Current directory: {os.getcwd()}")
print(f"Model file exists: {os.path.exists('eye_state_model.h5')}")

# Try to load the model
try:
    model_path = os.path.join(os.getcwd(), "eye_state_model.h5")
    print(f"Loading model from: {model_path}")
    
    # Try different loading methods
    print("Method 1: Standard loading")
    try:
        model = tf.keras.models.load_model(model_path)
        print("Standard loading succeeded")
        print(f"Model summary:")
        model.summary()
    except Exception as e:
        print(f"Standard loading failed: {e}")
    
    print("\nMethod 2: Loading without compilation")
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        print("Loading without compilation succeeded")
        print(f"Model summary:")
        model.summary()
    except Exception as e:
        print(f"Loading without compilation failed: {e}")
    
    # Create a dummy RGB input (3 channels)
    dummy_input = np.random.random((1, 24, 24, 3))
    print(f"\nTrying prediction with dummy RGB input shape: {dummy_input.shape}")
    
    prediction = model.predict(dummy_input, verbose=1)
    print(f"Prediction result type: {type(prediction)}")
    print(f"Prediction shape: {prediction.shape if hasattr(prediction, 'shape') else 'N/A'}")
    print(f"Prediction: {prediction}")
    
    # Let's try with an actual eye image if we can find one
    try:
        # Create a blank RGB image
        blank_eye = np.ones((24, 24, 3), dtype=np.float32) * 0.5
        blank_eye_batch = np.expand_dims(blank_eye, axis=0)
        
        print(f"\nTrying prediction with blank eye image shape: {blank_eye_batch.shape}")
        pred = model.predict(blank_eye_batch, verbose=1)
        print(f"Blank eye prediction: {pred}")
        
        # Interpret the prediction (assuming binary classification: 0=closed, 1=open)
        is_open = pred[0][0] > 0.5 if pred.shape == (1, 1) else pred[0] > 0.5
        print(f"Eye is {'open' if is_open else 'closed'}")
    except Exception as e:
        print(f"Error with blank image test: {e}")
    
except Exception as e:
    print(f"Error in model testing: {e}") 