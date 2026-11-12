import { createContext, useContext } from "react";

// Kept separate from AuthContext.jsx so that file only exports a component
// (needed for React Fast Refresh / hot reload to work).
export const AuthContext = createContext(null);

// Custom hook — any component can call useAuth() to get token/user/login/logout
export function useAuth() {
  return useContext(AuthContext);
}
