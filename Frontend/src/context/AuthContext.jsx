import { useMemo, useState } from "react";
import { AuthContext } from "./useAuth";

// Decode the JWT payload client-side.
// JWTs use base64url (- and _ instead of + and /), which atob() can't read directly.
// Returns null for a missing, malformed, or expired token.
function decodeToken(token) {
  if (!token) return null;
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64));
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return { username: payload.sub, role: payload.role };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));

  // Derived synchronously — available on the very first render,
  // so route guards don't redirect before the user is known (e.g. on page refresh).
  const user = useMemo(() => decodeToken(token), [token]);

  const login = (newToken) => {
    localStorage.setItem("token", newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

