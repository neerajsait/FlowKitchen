import React, { useState, useEffect, Suspense, lazy } from "react";
import { api } from "./utils/api";
import Login from "./components/Login";
import ErrorBoundary from "./components/ErrorBoundary";
import VerifyEmail from "./components/VerifyEmail";

// Lazy load views for code splitting
const CustomerView = lazy(() => import("./components/CustomerView"));
import {
  LogOut, Zap, 
  ChevronRight, Lock
} from "./ui/Icon";



export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [dbMode, setDbMode] = useState("Checking...");
  const [loading, setLoading] = useState(true);

  // Force password change state
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [forceChangeLoading, setForceChangeLoading] = useState(false);
  const [forceChangeError, setForceChangeError] = useState("");
  const [showLogin, setShowLogin] = useState(false);


  const checkSession = async () => {
    try {
      const mode = await api.getMode();
      setDbMode(mode);
      
      // Silent refresh: restore the access token into memory via the
      // HttpOnly refresh cookie (token is never persisted client-side).
      const restored = await api.ensureSession();
      if (restored) {
        const user = await api.getMe();
        if (user) {
          setCurrentUser(user);
        } else {
          api.logout();
          setCurrentUser(null);
        }
      }
    } catch (err) {
      console.error("Session init failed:", err);
      api.logout();
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { checkSession(); }, []);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    api.getMode().then(setDbMode);
  };

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
  };

  // Idle timeout (1 hour)
  useEffect(() => {
    let timeoutId;
    const resetTimer = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        if (currentUser) {
          handleLogout();
        }
      }, 3600000); // 1 hour
    };

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    events.forEach(event => document.addEventListener(event, resetTimer));
    resetTimer();

    return () => {
      clearTimeout(timeoutId);
      events.forEach(event => document.removeEventListener(event, resetTimer));
    };
  }, [currentUser]);

  const handleForcePasswordChangeSubmit = async (e) => {
    e.preventDefault();
    setForceChangeError("");
    if (newPassword.length < 8 || !/[a-zA-Z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setForceChangeError("Password must be at least 8 characters and contain both letters and numbers.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setForceChangeError("Passwords do not match.");
      return;
    }
    setForceChangeLoading(true);
    try {
      await api.changePassword(newPassword);
      const updatedUser = { ...currentUser, is_first_login: false };
      setCurrentUser(updatedUser);
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setForceChangeError(err.message || "Failed to update password.");
    } finally {
      setForceChangeLoading(false);
    }
  };


  if (loading) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "var(--bg-base)", flexDirection: "column", gap: "1rem"
      }}>
        <div style={{
          width: 56, height: 56,
          background: "var(--brand)",
          borderRadius: "var(--r-xl)", display: "flex", alignItems: "center",
          justifyContent: "center", fontSize: "1.75rem",
          boxShadow: "0 2px 12px rgba(0, 0, 0, 0.08)", animation: "pulse-glow 2s ease-in-out infinite"
        }}></div>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Starting Suggula\'s Kitchen…
        </p>
      </div>
    );
  }

  if (window.location.pathname === "/verify-email") {
    return <VerifyEmail />;
  }

  // If user specifically requested login, or we need authentication to proceed (optional later)
  if (showLogin && !currentUser) {
    return <Login onLoginSuccess={(user) => { setShowLogin(false); handleLoginSuccess(user); }} />;
  }

  // Render the correct view (allow guests)
  const renderView = () => {
    return (
      <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh', color: 'var(--brand)' }}>Loading View...</div>}>
        {(!currentUser || currentUser.role === 'customer') && (
          <CustomerView 
            onLogout={handleLogout} 
            onLoginRequest={() => setShowLogin(true)} 
            dbMode={dbMode} 
            currentUser={currentUser} 
          />
        )}
        {currentUser && currentUser.role !== 'customer' && (
          <div style={{ padding: "3rem", textAlign: "center" }}>
            <div className="empty-state">
              <div className="empty-state-icon">
                <ChevronRight size={28} />
              </div>
              <h3>Staff Portal</h3>
              <p>Your account role ({currentUser.role}) does not belong here. Please log into the Admin/Staff Portal.</p>
              <button className="btn btn-secondary" onClick={handleLogout} style={{ marginTop: "1rem" }}>
                <LogOut size={15} /> Sign Out
              </button>
            </div>
          </div>
        )}
      </Suspense>
    );
  };

  return (
    <ErrorBoundary>
      <div>
        {renderView()}
      </div>

      {currentUser && currentUser.is_first_login && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(13, 17, 23, 0.98)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 9999, backdropFilter: "blur(12px)"
        }}>
          <div style={{
            background: "rgba(18, 22, 28, 0.95)", border: "1px solid var(--brand)",
            boxShadow: "0 0 50px rgba(249, 115, 22, 0.15)", borderRadius: "var(--r-xl)",
            padding: "2.5rem", width: "100%", maxWidth: "440px", textAlign: "center"
          }}>
            <div style={{
              width: 56, height: 56, background: "rgba(249, 115, 22, 0.1)",
              borderRadius: "50%", display: "flex", alignItems: "center",
              justifyContent: "center", margin: "0 auto 1.25rem", color: "var(--brand)"
            }}>
              <Lock size={24} />
            </div>
            <h2 style={{ fontFamily: "var(--font-heading)", color: "var(--text-primary)", fontSize: "1.5rem", fontWeight: 800, marginBottom: "0.5rem" }}>
              Secure Your Account
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem", lineHeight: 1.4 }}>
              This is your first login with a default temporary password. For security reasons, you must set a new password before continuing.
            </p>

            {forceChangeError && (
              <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
                <Zap size={15} style={{ flexShrink: 0 }} /> {forceChangeError}
              </div>
            )}

            <form onSubmit={handleForcePasswordChangeSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem", textAlign: "left" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">New Password</label>
                <input
                  type="password"
                  required
                  className="form-input"
                  placeholder="Min 8 chars, letters & numbers"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Confirm New Password</label>
                <input
                  type="password"
                  required
                  className="form-input"
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={forceChangeLoading}
                className="btn btn-primary"
                style={{ width: "100%", padding: "0.875rem", marginTop: "0.5rem" }}
              >
                {forceChangeLoading ? "Updating Password..." : "Update Password & Continue"}
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="btn btn-secondary"
                style={{ width: "100%", padding: "0.875rem", marginTop: "0.25rem" }}
              >
                Sign Out
              </button>
            </form>
          </div>
        </div>
      )}
    </ErrorBoundary>
  );
}
