// Authentication utility functions

// Login function
export const login = async (username, password) => {
  const response = await fetch("/api/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || "Login failed");
  }

  const data = await response.json();
  localStorage.setItem("user", JSON.stringify(data.user));
  localStorage.setItem("username", data.user.username);

  // Reset logs data after successful login
  try {
    console.log("Resetting logs data after login...");
    const resetResponse = await fetch("/api/logs/reset", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: data.user.username,
      },
    });

    if (resetResponse.ok) {
      const resetData = await resetResponse.json();
      console.log("Logs reset successfully:", resetData);
    } else {
      console.error("Failed to reset logs:", await resetResponse.text());
    }
  } catch (error) {
    console.error("Error resetting logs:", error);
  }

  return data.user;
};

// Register function
export const register = async (username, password) => {
  const response = await fetch("/api/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || "Registration failed");
  }

  const data = await response.json();
  return data;
};

// Logout function
export const logout = () => {
  localStorage.removeItem("user");
  localStorage.removeItem("username");
};

// Check if user is authenticated
export const isAuthenticated = () => {
  return localStorage.getItem("user") !== null;
};

// Get current user
export const getCurrentUser = () => {
  const userString = localStorage.getItem("user");
  if (!userString) return null;

  try {
    return JSON.parse(userString);
  } catch (e) {
    logout();
    return null;
  }
};

// Get auth header
export const getAuthHeader = () => {
  const user = getCurrentUser();
  if (!user) return {};

  return {
    Authorization: user.username,
  };
};

// Add auth header to API requests
export const withAuth = (fetch) => {
  return async (url, options = {}) => {
    const authOptions = {
      ...options,
      headers: {
        ...options.headers,
        ...getAuthHeader(),
      },
    };

    return fetch(url, authOptions);
  };
};
