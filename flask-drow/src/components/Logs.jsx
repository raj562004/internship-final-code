import React, { useState, useEffect, useRef } from "react";
import { format } from "date-fns";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "./Logs.css";
import DbStatus from "./DbStatus";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { getAuthHeader } from "../utils/auth";
import io from "socket.io-client";

// Create logout button component
const LogoutButton = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <button className="logout-button" onClick={handleLogout}>
      Logout
    </button>
  );
};

const Logs = () => {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({
    overall: { total_events: 0, total_duration: 0, avg_duration: 0 },
    today: { events: 0, duration: 0 },
  });
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState([null, null]);
  const [startDate, endDate] = dateRange;
  const [showDbStatus, setShowDbStatus] = useState(false);
  const [activeFilter, setActiveFilter] = useState(1);
  const [activeSessionRuntime, setActiveSessionRuntime] = useState(0);
  const [sessionActive, setSessionActive] = useState(false);
  const runtimeTimerRef = useRef(null);
  const lastServerRuntimeRef = useRef(0);
  const lastUpdateTimeRef = useRef(Date.now());

  // Define display constants at component level
  const DISPLAY_ALERT_DURATION = 1; // 1 second per alert for display in UI

  // Format duration to readable format
  const formatDuration = (seconds) => {
    if (!seconds || isNaN(seconds)) return "0s";
    if (seconds < 60) return `${Math.round(seconds)}s`;

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);

    if (minutes < 60) {
      return `${minutes}m ${remainingSeconds}s`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`;
  };

  // Local timer to increment session runtime smoothly
  const startRuntimeTimer = () => {
    // Clear any existing timer
    if (runtimeTimerRef.current) {
      clearInterval(runtimeTimerRef.current);
    }

    console.log(
      "Starting runtime timer with initial value:",
      lastServerRuntimeRef.current
    );

    // Start a new timer that updates every 100ms
    runtimeTimerRef.current = setInterval(() => {
      if (sessionActive) {
        // Calculate elapsed time since last server update
        const now = Date.now();
        const elapsed = (now - lastUpdateTimeRef.current) / 1000;

        // Only update if elapsed time makes sense (protection against clock skew)
        if (elapsed >= 0) {
          const newRuntime = lastServerRuntimeRef.current + elapsed;
          setActiveSessionRuntime(newRuntime);

          // Debug log every 5 seconds
          if (
            Math.floor(newRuntime) % 5 === 0 &&
            Math.floor(newRuntime - elapsed) % 5 !== 0
          ) {
            console.log(
              `Runtime timer update: ${newRuntime.toFixed(
                1
              )}s (elapsed: ${elapsed.toFixed(1)}s)`
            );
          }
        }
      }
    }, 100); // Update very frequently for smooth counter
  };

  // Update runtime from server
  const updateRuntimeFromServer = (serverRuntime) => {
    // Only update if we got a valid runtime
    if (
      typeof serverRuntime === "number" &&
      !isNaN(serverRuntime) &&
      serverRuntime >= 0
    ) {
      console.log(
        `Updating runtime from server: ${serverRuntime.toFixed(
          1
        )}s (previous: ${lastServerRuntimeRef.current.toFixed(1)}s)`
      );

      // Store the server runtime and update time
      lastServerRuntimeRef.current = serverRuntime;
      lastUpdateTimeRef.current = Date.now();
      setActiveSessionRuntime(serverRuntime);
    } else {
      console.warn(`Received invalid runtime from server: ${serverRuntime}`);
    }
  };

  // Get total camera runtime from sessions or stats
  const getTotalCameraRuntime = () => {
    // If we have an active session runtime, use that
    if (sessionActive && activeSessionRuntime > 0) {
      return activeSessionRuntime;
    }

    // Otherwise use pre-calculated session_time from stats
    if (stats?.today?.session_time !== undefined) {
      const sessionTime = parseFloat(stats.today.session_time);
      if (!isNaN(sessionTime)) {
        console.log(
          `Using pre-calculated session time from stats: ${sessionTime.toFixed(
            2
          )}s`
        );
        return sessionTime;
      }
    }

    // Fallback to calculating from sessions if stats doesn't have it
    console.log("Calculating runtime from sessions directly");
    return calculateRuntimeFromSessions();
  };

  // Calculate alert count - one alert = one complete cycle (start to end)
  const getAlertCount = () => {
    const count = stats?.today?.events || 0;
    console.log(`Alert count from stats: ${count}`);
    return count;
  };

  // Calculate safe drive time (total time minus drowsy time)
  const getSafeDriveTime = () => {
    const totalTime = getTotalCameraRuntime();
    const drowsyTime = stats?.today?.duration || 0;

    console.log(
      `Safe drive calculation: Total=${totalTime}s - Drowsy=${drowsyTime}s`
    );

    return Math.max(0, totalTime - drowsyTime);
  };

  // Fetch logs data
  const fetchLogs = async (days = 1, start = null, end = null) => {
    setIsLoading(true);
    try {
      let url = `/api/events?days=${days}`;

      if (start && end) {
        const formattedStart = format(start, "yyyy-MM-dd");
        const formattedEnd = format(end, "yyyy-MM-dd");
        url = `/api/events?start_date=${formattedStart}&end_date=${formattedEnd}`;
      }

      console.log("Fetching logs from:", url);
      const response = await fetch(url, {
        headers: getAuthHeader(),
      });

      if (!response.ok) {
        const text = await response.text();
        console.error("API Error:", response.status, text.substring(0, 200));
        throw new Error(`HTTP error ${response.status}`);
      }

      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        const text = await response.text();
        console.error(
          "Invalid response format:",
          contentType,
          text.substring(0, 200)
        );
        throw new Error("Received non-JSON response");
      }

      const data = await response.json();
      console.log("Received log data:", data);

      if (data.events) {
        setLogs(data.events);
      }

      // Also fetch sessions to get camera runtime
      fetchSessions();
    } catch (error) {
      console.error("Error fetching logs:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch session data to get accurate camera runtime
  const fetchSessions = async () => {
    try {
      const response = await fetch("/api/sessions", {
        headers: getAuthHeader(),
      });

      if (!response.ok) throw new Error(`HTTP error ${response.status}`);

      const data = await response.json();
      console.log("Received sessions data:", data);

      if (data.sessions) {
        setSessions(data.sessions);
      }
    } catch (error) {
      console.error("Error fetching sessions:", error);
    }
  };

  // Fetch statistics
  const fetchStats = async () => {
    try {
      console.log("Fetching stats from /api/stats");
      const response = await fetch("/api/stats", {
        headers: getAuthHeader(),
      });

      if (!response.ok) {
        const text = await response.text();
        console.error("API Error:", response.status, text.substring(0, 200));
        throw new Error(`HTTP error ${response.status}`);
      }

      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        const text = await response.text();
        console.error(
          "Invalid response format:",
          contentType,
          text.substring(0, 200)
        );
        throw new Error("Received non-JSON response");
      }

      const data = await response.json();
      console.log("Received stats data:", data);

      // Verify today's data exists
      if (data.today) {
        console.log(
          "Today's events:",
          data.today.events,
          "Duration:",
          data.today.duration
        );
      } else {
        console.warn("Today's data is missing in stats response");
      }

      setStats(data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
  };

  // Handle date filter
  const handleDateFilter = (days) => {
    setDateRange([null, null]); // Reset date picker
    fetchLogs(days);
    // Also refresh stats when filter changes
    fetchStats();
    setActiveFilter(days);
  };

  // Fetch active session runtime
  const fetchActiveSessionRuntime = async () => {
    const runtime = await getActiveSessionRuntime();
    setActiveSessionRuntime(runtime);
    return runtime;
  };

  // Ensure stats are loaded before calculating derived values
  useEffect(() => {
    // First load data
    fetchLogs(1);
    fetchStats();
    fetchSessions();
    fetchActiveSessionRuntime();
    setActiveFilter(1); // Set default active filter to "Today"

    // Start the smooth runtime timer
    startRuntimeTimer();

    // Set up periodic refresh every 2 seconds for active runtime
    const runtimeInterval = setInterval(() => {
      fetchActiveSessionRuntime();
    }, 2000); // More frequent updates for runtime

    // Set up periodic refresh every 10 seconds for stats and logs
    const dataInterval = setInterval(() => {
      console.log("Refreshing stats and logs data...");
      fetchLogs(activeFilter); // Use the active filter period
      fetchStats();
      fetchSessions();
    }, 10000); // Less frequent for full data refresh

    return () => {
      clearInterval(runtimeInterval);
      clearInterval(dataInterval);

      // Clear runtime timer on unmount
      if (runtimeTimerRef.current) {
        clearInterval(runtimeTimerRef.current);
      }
    };
  }, []);

  // Listen for socket events for real-time updates
  useEffect(() => {
    // Setup socket listener for stats updates
    const socket = io();

    socket.on("connect", () => {
      console.log("Socket connected");
    });

    socket.on("disconnect", () => {
      console.log("Socket disconnected");
    });

    socket.on("stats_updated", (newStats) => {
      console.log("Received stats update from server:", newStats);
      setStats(newStats);
      fetchActiveSessionRuntime();
    });

    socket.on("session_ended", (sessionData) => {
      console.log("Session ended:", sessionData);
      // Refresh data when a session ends
      fetchStats();
      fetchSessions();
      setSessionActive(false);
      lastServerRuntimeRef.current = 0;
      setActiveSessionRuntime(0); // Clear active session runtime
    });

    socket.on("session_started", (sessionData) => {
      console.log("Session started, refreshing stats:", sessionData);
      // Refresh data when a new session starts
      fetchStats();
      fetchSessions();
      setSessionActive(true);
      fetchActiveSessionRuntime(); // Get the new active session runtime
    });

    return () => {
      socket.off("stats_updated");
      socket.off("session_ended");
      socket.off("session_started");
      socket.disconnect();
    };
  }, []);

  // Set up refresh timers for runtime and data
  useEffect(() => {
    console.log("Setting up refresh timers");

    // Start the smooth runtime timer
    startRuntimeTimer();

    // Set up periodic refresh every 2 seconds for active runtime
    const runtimeInterval = setInterval(() => {
      if (sessionActive) {
        console.log("Refreshing active runtime data...");
        fetchActiveSessionRuntime();
      }
    }, 5000); // Less frequent server checks (5 seconds)

    // Set up periodic refresh every 10 seconds for stats and logs
    const dataInterval = setInterval(() => {
      console.log("Refreshing stats and logs data...");
      fetchLogs(activeFilter); // Use the active filter period
      fetchStats();
      fetchSessions();
    }, 15000); // Less frequent for full data refresh (15 seconds)

    return () => {
      console.log("Cleaning up timers");
      clearInterval(runtimeInterval);
      clearInterval(dataInterval);

      // Clear runtime timer on unmount
      if (runtimeTimerRef.current) {
        clearInterval(runtimeTimerRef.current);
      }
    };
  }, []);

  // Get active session runtime directly from the backend
  const getActiveSessionRuntime = async () => {
    try {
      const response = await fetch("/api/session/runtime", {
        headers: getAuthHeader(),
      });

      if (!response.ok) throw new Error(`HTTP error ${response.status}`);

      const data = await response.json();
      console.log("Received session runtime data:", data);

      if (data.active && typeof data.runtime === "number") {
        // Set session as active
        setSessionActive(true);

        // Update the runtime from server (this updates our reference values)
        updateRuntimeFromServer(data.runtime);

        // If we have today's stats in the response, update them
        if (data.today_stats) {
          setStats((prevStats) => ({
            ...prevStats,
            today: {
              ...prevStats.today,
              ...data.today_stats,
            },
          }));
        }

        return data.runtime;
      } else {
        console.log("No active session found or invalid runtime");
        setSessionActive(false);
        lastServerRuntimeRef.current = 0;

        // Even if no active session, update stats if available
        if (data.today_stats) {
          setStats((prevStats) => ({
            ...prevStats,
            today: {
              ...prevStats.today,
              ...data.today_stats,
            },
          }));
        }

        return 0;
      }
    } catch (error) {
      console.error("Error fetching active session runtime:", error);
      return 0;
    }
  };

  // Calculate all derived values after data is loaded
  const calculateDerivedValues = () => {
    // First check if we have the necessary data
    if (!stats || !sessions) {
      console.log("Data not yet loaded, deferring calculations");
      return {
        totalDriveTime: 0,
        drowsyTime: 0,
        safeDriveTime: 0,
        alertCount: 0,
        safePercentage: 100,
      };
    }

    // IMPROVED: Consistent way to get totalDriveTime prioritizing active runtime
    let totalDriveTime = 0;

    // If we have an active session runtime from server, use that first
    if (sessionActive && activeSessionRuntime > 0) {
      console.log(`Using active session runtime: ${activeSessionRuntime}s`);
      totalDriveTime = activeSessionRuntime;
    }
    // Next try to use the stats summary that's calculated on the server
    else if (
      stats?.today?.session_time !== undefined &&
      stats.today.session_time > 0
    ) {
      totalDriveTime = parseFloat(stats.today.session_time);
      console.log(
        `Using session_time from stats: ${totalDriveTime.toFixed(2)}s`
      );
    }
    // Last fallback - only if needed
    else {
      totalDriveTime = calculateRuntimeFromSessions();
      console.log(
        `Calculated runtime from sessions: ${totalDriveTime.toFixed(2)}s`
      );
    }

    // Get alert count from stats
    const alertCount = stats?.today?.events || 0;

    // Use fixed 50ms (0.05s) duration for each alert for calculation purposes
    const fixedAlertDuration = 0.05; // 50ms per alert for calculation
    const drowsyTime = alertCount * fixedAlertDuration;

    console.log(
      `Using fixed alert duration: ${fixedAlertDuration}s per alert for calculation`
    );
    console.log(`Displaying as: ${DISPLAY_ALERT_DURATION}s per alert in UI`);
    console.log(
      `Total alerts: ${alertCount}, Total drowsy time: ${drowsyTime.toFixed(
        2
      )}s`
    );

    // Calculate safe time and percentage
    const safeDriveTime = Math.max(0, totalDriveTime - drowsyTime);
    const safePercentage =
      totalDriveTime > 0
        ? Math.round((safeDriveTime / totalDriveTime) * 100)
        : 100;

    console.log(
      `Stats Summary - Total Drive: ${formatDuration(
        totalDriveTime
      )}, Drowsy: ${formatDuration(drowsyTime)}, Safe: ${formatDuration(
        safeDriveTime
      )}, Percentage: ${safePercentage}%`
    );

    return {
      totalDriveTime,
      drowsyTime,
      safeDriveTime,
      alertCount,
      safePercentage,
    };
  };

  // Helper function to calculate runtime from sessions
  const calculateRuntimeFromSessions = () => {
    if (!sessions || sessions.length === 0) {
      console.log("No sessions available for runtime calculation");
      return 0;
    }

    // Get today's date in YYYY-MM-DD format for accurate comparison
    const today = new Date().toISOString().split("T")[0];
    console.log("Today's date for comparison:", today);
    const now = new Date();

    // Sum up duration of all sessions for today using the pre-calculated duration
    const totalRuntime = sessions.reduce((total, session) => {
      // Only count sessions from today
      const startTime = new Date(session.start_time);
      const sessionDate = startTime.toISOString().split("T")[0];

      if (sessionDate === today) {
        let sessionDuration = 0;

        // For active sessions with no end time, calculate duration up to now
        if (!session.end_time) {
          console.log(
            `Active session ${session.id.substring(
              0,
              8
            )}: calculating live duration`
          );
          sessionDuration = (now - startTime) / 1000; // Convert ms to seconds
        }
        // For completed sessions, use the pre-calculated duration
        else if (session.duration !== undefined) {
          sessionDuration = parseFloat(session.duration);
        }

        if (!isNaN(sessionDuration)) {
          // Debug session information
          console.log(
            `Session ${session.id.substring(
              0,
              8
            )}: Date=${sessionDate}, Duration=${sessionDuration.toFixed(
              2
            )}s, End time=${session.end_time || "active"}`
          );
          return total + sessionDuration;
        }
      }
      return total;
    }, 0);

    console.log(
      `Total calculated runtime from sessions: ${Math.round(totalRuntime)}s`
    );
    return totalRuntime;
  };

  // Now calculate all derived values in one go
  const {
    totalDriveTime,
    drowsyTime,
    safeDriveTime,
    alertCount,
    safePercentage,
  } = calculateDerivedValues();

  return (
    <div className="simple-logs-container">
      <div className="logs-header">
        <h1>Drowsiness Detection Report</h1>
        <div>
          <button
            className="db-status-button"
            onClick={() => setShowDbStatus(!showDbStatus)}
          >
            {showDbStatus ? "Hide Technical Info" : "Show Technical Info"}
          </button>
          <a href="/" className="back-button">
            Back to Detection
          </a>
          <LogoutButton />
        </div>
      </div>

      {showDbStatus && (
        <div className="db-status-container">
          <DbStatus />
        </div>
      )}

      {/* Simple Date Filter */}
      <div className="simple-filter">
        <h3>View Logs For:</h3>
        <div className="date-buttons">
          <button
            className={`date-btn ${activeFilter === 1 ? "active" : ""}`}
            onClick={() => handleDateFilter(1)}
          >
            Today
          </button>
          <button
            className={`date-btn ${activeFilter === 7 ? "active" : ""}`}
            onClick={() => handleDateFilter(7)}
          >
            Last 7 Days
          </button>
          <button
            className={`date-btn ${activeFilter === 30 ? "active" : ""}`}
            onClick={() => handleDateFilter(30)}
          >
            Last 30 Days
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="simple-stats">
        <div className="stat-card">
          <div className="stat-icon">🕒</div>
          <div className="stat-content">
            <h3>Camera Runtime</h3>
            <p className="stat-value">{formatDuration(totalDriveTime)}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <h3>Alert-Free Time</h3>
            <p className="stat-value">{formatDuration(safeDriveTime)}</p>
            <div className="safety-meter">
              <div
                className="safety-progress"
                style={{ width: `${safePercentage}%` }}
              ></div>
            </div>
            <p className="safety-percentage">{safePercentage}% Alert-Free</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⚠️</div>
          <div className="stat-content">
            <h3>Alert Count</h3>
            <p className="stat-value">{alertCount}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⏱️</div>
          <div className="stat-content">
            <h3>Avg. Alert Duration</h3>
            <p className="stat-value">
              {formatDuration(DISPLAY_ALERT_DURATION)}
            </p>
          </div>
        </div>
      </div>

      {/* Simple Summary */}
      <div className="summary-section">
        <h2>Driving Summary</h2>
        <div className="summary-content">
          <p>
            Your camera has been active for{" "}
            <strong>{formatDuration(totalDriveTime)}</strong>
            {totalDriveTime > 0 && drowsyTime > 0 ? (
              <>
                , with <strong>{formatDuration(safeDriveTime)}</strong> of
                alert-free time and{" "}
                <strong>{formatDuration(drowsyTime)}</strong> of estimated
                drowsiness detected.
              </>
            ) : totalDriveTime > 0 ? (
              <>, with no drowsiness detected.</>
            ) : (
              <>. No camera activity recorded today.</>
            )}
          </p>

          {alertCount > 0 ? (
            <p>
              The drowsiness alert was triggered{" "}
              <strong>
                {alertCount} {alertCount === 1 ? "time" : "times"}
              </strong>
              , with an average alert duration of{" "}
              <strong>{formatDuration(DISPLAY_ALERT_DURATION)}</strong> per
              alert.
            </p>
          ) : totalDriveTime > 0 ? (
            <p>No drowsiness alerts were triggered during this period.</p>
          ) : null}

          {totalDriveTime > 0 && (
            <p className="recommendation">
              {safePercentage > 95
                ? "Great job staying alert! Keep up the good work."
                : safePercentage > 80
                ? "You've experienced some drowsiness. Consider taking breaks more frequently."
                : "You've experienced significant drowsiness. Please find a safe place to rest when possible."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Logs;
