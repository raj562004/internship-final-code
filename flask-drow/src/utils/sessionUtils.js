import { getAuthHeader } from "./auth";

/**
 * Explicitly end the current camera session
 * Call this when stopping the camera/stream
 */
export const stopSession = async () => {
  try {
    console.log("Ending camera session via API...");
    const response = await fetch("/api/session/end", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Error ending session:", response.status, errorText);
      return null;
    }

    const result = await response.json();
    console.log("Session ended successfully:", result);
    return result;
  } catch (err) {
    console.error("Error ending session:", err);
    return null;
  }
};

/**
 * Notify the server that the camera has started
 * This uses WebSockets, but provides a fallback HTTP method
 */
export const startCameraSession = (socket) => {
  try {
    // Primary method: use WebSockets
    if (socket && socket.connected) {
      console.log("Starting camera session via WebSocket...");
      socket.emit("camera_status", { status: "started" });
      return true;
    }

    // Fallback: Could implement HTTP method if needed
    console.warn("No socket connection available for camera start");
    return false;
  } catch (err) {
    console.error("Error starting camera session:", err);
    return false;
  }
};

/**
 * Notify the server that the camera has stopped
 * This uses WebSockets with an HTTP fallback
 */
export const stopCameraSession = async (socket) => {
  try {
    // Try WebSocket first
    if (socket && socket.connected) {
      console.log("Stopping camera session via WebSocket...");
      socket.emit("camera_status", { status: "stopped" });
    } else {
      console.warn("No socket connection, falling back to HTTP API");
      // Fallback to HTTP API
      return await stopSession();
    }
    return true;
  } catch (err) {
    console.error("Error stopping camera session:", err);

    // Try HTTP fallback if WebSocket fails
    try {
      return await stopSession();
    } catch (innerErr) {
      console.error("HTTP fallback also failed:", innerErr);
      return false;
    }
  }
};
