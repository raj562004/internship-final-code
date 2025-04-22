import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import "./Login.css";

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!username || !password) {
      setError("Please enter both username and password");
      setLoading(false);
      return;
    }

    try {
      if (isRegistering) {
        await register(username, password);
        // After registration, automatically log in
        await login(username, password);
      } else {
        await login(username, password);
      }

      // Redirect to main app
      navigate("/");
    } catch (err) {
      setError(err.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>Drowsiness Detection System</h1>
          <p className="login-subtitle">
            {isRegistering ? "Create a new account" : "Sign in to your account"}
          </p>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <div className="input-with-icon">
              <i className="icon user-icon">👤</i>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-with-icon">
              <i className="icon password-icon">🔒</i>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>
          </div>

          <button type="submit" className="login-button" disabled={loading}>
            {loading
              ? "Processing..."
              : isRegistering
              ? "Create Account"
              : "Sign In"}
          </button>
        </form>

        <div className="login-footer">
          <button
            className="switch-mode-button"
            onClick={() => setIsRegistering(!isRegistering)}
          >
            {isRegistering
              ? "Already have an account? Sign In"
              : "Need an account? Register"}
          </button>
        </div>

        <div className="login-decoration">
          <div className="eye-icon">👁️</div>
          <div className="login-system-name">Drowsiness Detection System</div>
        </div>
      </div>
    </div>
  );
};

export default Login;
