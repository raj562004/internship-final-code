import React, { createContext, useState, useEffect, useContext } from "react";
import {
  login as authLogin,
  register as authRegister,
  logout as authLogout,
  getCurrentUser,
} from "../utils/auth";

// Create the context
const AuthContext = createContext();

// Create a hook to use the auth context
export const useAuth = () => {
  return useContext(AuthContext);
};

// Create the provider component
export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing user on initial load
  useEffect(() => {
    const user = getCurrentUser();
    setCurrentUser(user);
    setLoading(false);
  }, []);

  // Login function
  const login = async (username, password) => {
    try {
      const user = await authLogin(username, password);
      setCurrentUser(user);
      return user;
    } catch (error) {
      throw error;
    }
  };

  // Register function
  const register = async (username, password) => {
    try {
      const result = await authRegister(username, password);
      // We don't set current user here because registration doesn't log in the user
      return result;
    } catch (error) {
      throw error;
    }
  };

  // Logout function
  const logout = () => {
    authLogout();
    setCurrentUser(null);
  };

  // Context value
  const value = {
    currentUser,
    login,
    register,
    logout,
    isAuthenticated: !!currentUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
