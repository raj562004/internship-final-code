import React, { useState, useEffect } from "react";

const DbStatus = () => {
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkDatabase = async () => {
      setIsLoading(true);
      try {
        const response = await fetch("/api/db-status");

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();
        setStatus(data);
      } catch (err) {
        setError(err.message);
        console.error("Error checking database status:", err);
      } finally {
        setIsLoading(false);
      }
    };

    checkDatabase();
  }, []);

  if (isLoading) {
    return (
      <div className="db-status-loading">Checking database connection...</div>
    );
  }

  if (error) {
    return (
      <div className="db-status-error">
        <h3>Error connecting to database</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="db-status">
      <h3>Database Status</h3>

      <div className="status-item">
        <span className="label">Connection:</span>
        <span className="value">{status?.status || "Unknown"}</span>
      </div>

      <div className="status-item">
        <span className="label">Database File:</span>
        <span className="value">{status?.database_file || "Unknown"}</span>
      </div>

      <div className="status-item">
        <span className="label">Current Session:</span>
        <span className="value">{status?.current_session || "Unknown"}</span>
      </div>

      <h4>Tables</h4>

      <div className="table-status">
        <div className="status-item">
          <span className="label">Events Table:</span>
          <span className="value">
            {status?.tables?.drowsiness_events?.exists ? "Exists" : "Missing"}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Events Count:</span>
          <span className="value">
            {status?.tables?.drowsiness_events?.count || 0}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Sessions Table:</span>
          <span className="value">
            {status?.tables?.sessions?.exists ? "Exists" : "Missing"}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Sessions Count:</span>
          <span className="value">{status?.tables?.sessions?.count || 0}</span>
        </div>
      </div>
    </div>
  );
};

export default DbStatus;
