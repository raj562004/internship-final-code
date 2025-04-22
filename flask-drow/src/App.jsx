import React, { useState, useEffect, useRef } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";
import io from "socket.io-client";
import "./App.css";
import Logs from "./components/Logs";
import Login from "./components/Login";
import { useAuth } from "./contexts/AuthContext";
import { getAuthHeader } from "./utils/auth";
import {
  startCameraSession,
  stopCameraSession,
  stopSession,
} from "./utils/sessionUtils";

const socket = io("http://localhost:5000", { transports: ["websocket"] });

// Create protected route component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  return children;
};

// Add logout functionality
const LogoutButton = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <button
      className="control-btn logout"
      onClick={handleLogout}
      style={{
        backgroundColor: "#e63946",
        color: "white",
        border: "none",
        padding: "0.6rem 1.2rem",
        borderRadius: "4px",
        cursor: "pointer",
        marginTop: "1rem",
      }}
    >
      Logout
    </button>
  );
};

const DrowsinessDetection = () => {
  const videoRef = useRef(null);
  const [drowsy, setDrowsy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [sessionActive, setSessionActive] = useState(false);
  const [useEyeModel, setUseEyeModel] = useState(true);
  const [modelConfidence, setModelConfidence] = useState(null);

  useEffect(() => {
    socket.on("detection_result", (data) => {
      setDrowsy(data.drowsy);
      // Check if confidence data is available in the response
      if (data.confidence !== undefined) {
        setModelConfidence(data.confidence);
      }
    });

    // Listen for session status updates
    socket.on("session_started", (data) => {
      console.log("Session started confirmation:", data);
      setSessionActive(true);
    });

    socket.on("session_ended", (data) => {
      console.log("Session ended confirmation:", data);
      setSessionActive(false);
    });

    // Cleanup on component unmount - ensure session is ended
    return () => {
      socket.off("detection_result");
      socket.off("session_started");
      socket.off("session_ended");

      // If streaming is still active when component unmounts, stop the session
      if (streaming || sessionActive) {
        console.log("Component unmounting - ensuring session is ended");
        stopSession().then(() => console.log("Session ended on unmount"));
      }
    };
  }, [streaming, sessionActive]);

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      videoRef.current.srcObject = stream;
      setStreaming(true);

      // Start a new session using our utility
      const started = startCameraSession(socket);
      if (!started) {
        console.warn(
          "Socket method failed, may need HTTP fallback for session start"
        );
      }
      console.log("Camera started - session tracking began");
    } catch (error) {
      console.error("Error accessing camera:", error);
    }
  };

  const stopWebcam = async () => {
    // Stop the video tracks
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
    }
    setStreaming(false);

    // End the session using our utility with fallbacks
    try {
      // Try the socket method first with HTTP fallback
      const success = await stopCameraSession(socket);

      if (!success) {
        // Last resort: try the direct HTTP endpoint
        await stopSession();
      }

      console.log("Camera stopped - session ended successfully");
    } catch (error) {
      console.error("Failed to end session properly:", error);
    }
  };

  // Toggle between eye state model and traditional EAR method
  const toggleDetectionModel = async () => {
    try {
      const response = await fetch("/api/detection/toggle-model", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeader(),
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Error toggling model:", response.status, errorText);
        return;
      }

      const result = await response.json();
      console.log("Model toggled:", result);
      setUseEyeModel(result.use_eye_model);
    } catch (error) {
      console.error("Error toggling detection model:", error);
    }
  };

  // Window unload handler to ensure session is properly closed
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (streaming || sessionActive) {
        // Synchronous version for beforeunload
        fetch("/api/session/end", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeader(),
          },
          keepalive: true, // Ensure request completes even if page is unloading
        });
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [streaming, sessionActive]);

  const sendFrame = () => {
    if (!videoRef.current || !streaming) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = 320;
    canvas.height = 240;
    ctx.drawImage(videoRef.current, 0, 0, 320, 240);

    const frameData = canvas.toDataURL("image/jpeg", 0.6);
    const base64Data = frameData.split(",")[1];
    socket.emit("send_frame", base64Data);
  };

  useEffect(() => {
    const interval = setInterval(() => {
      sendFrame();
    }, 500);

    return () => clearInterval(interval);
  }, [streaming]);

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="logo">
          <h1>Drowsiness Detection</h1>
        </div>
        <div className="status-card">
          <div className="status-header">
            <h2>Status</h2>
            <div className={`status-indicator ${drowsy ? "drowsy" : "awake"}`}>
              {drowsy ? "Drowsy" : "Awake"}
            </div>
          </div>
          <div className="status-details">
            <div className="status-item">
              <span className="label">Eye State:</span>
              <span className={`value ${drowsy ? "drowsy" : "awake"}`}>
                {drowsy ? "Closed" : "Open"}
              </span>
            </div>
            <div className="status-item">
              <span className="label">Alert Status:</span>
              <span className={`value ${drowsy ? "drowsy" : "awake"}`}>
                {drowsy ? "Active" : "Inactive"}
              </span>
            </div>
            <div className="status-item">
              <span className="label">Session:</span>
              <span
                className={`value ${sessionActive ? "active" : "inactive"}`}
              >
                {sessionActive ? "Active" : "Inactive"}
              </span>
            </div>
            <div className="status-item">
              <span className="label">Detection:</span>
              <span className={`value ${useEyeModel ? "model" : "ear"}`}>
                {useEyeModel ? "AI Model" : "Traditional"}
              </span>
            </div>
            {modelConfidence !== null && (
              <div className="status-item">
                <span className="label">Confidence:</span>
                <span className="value confidence">
                  {Math.round(modelConfidence * 100)}%
                </span>
                <div className="confidence-meter">
                  <div
                    className="confidence-bar"
                    style={{
                      width: `${Math.round(modelConfidence * 100)}%`,
                      backgroundColor: drowsy ? "#e63946" : "#2a9d8f",
                    }}
                  ></div>
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="controls">
          <button
            className={`control-btn ${streaming ? "active" : ""}`}
            onClick={startWebcam}
            disabled={streaming}
          >
            Start Camera
          </button>
          <button
            className="control-btn stop"
            onClick={stopWebcam}
            disabled={!streaming}
          >
            Stop Camera
          </button>
          <button
            className="control-btn toggle-model"
            onClick={toggleDetectionModel}
            title="Switch between AI model and traditional detection"
          >
            {useEyeModel ? "Use Traditional" : "Use AI Model"}
          </button>
          <a href="/logs" className="control-btn view-logs">
            View Logs & Reports
          </a>
          <LogoutButton />
        </div>
      </div>

      <div className="main-content">
        <div className="video-container">
          <video ref={videoRef} autoPlay></video>
          <div className="overlay">
            <div className="overlay-content">
              <h3>Live Feed</h3>
              <p>Real-time drowsiness detection</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const App = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DrowsinessDetection />
            </ProtectedRoute>
          }
        />
        <Route
          path="/logs"
          element={
            <ProtectedRoute>
              <Logs />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
};

export default App;
