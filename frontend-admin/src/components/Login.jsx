import React, { useState } from "react";
import { api } from "../utils/api";
import {
  Lock, Mail, UserPlus, LogIn, Eye, EyeOff, ShoppingBag,
  Store, BarChart3, Package, Shield, Zap, Star
} from "../ui/Icon";

const FEATURES = [
  { icon: ShoppingBag, label: "B2C Online Shop", desc: "Full e-commerce ordering for home foods" },
  { icon: Store, label: "POS Terminal", desc: "Cashier system for snack supply outlets" },
  { icon: BarChart3, label: "Analytics Dashboard", desc: "Revenue, stock & order insights" },
  { icon: Package, label: "QR Stock System", desc: "Scan-to-stock dispatch workflow" },
];

const STATS = [
  { value: "35+", label: "Products" },
  { value: "3", label: "Outlets" },
  { value: "∞", label: "Orders" },
];

export default function Login({ onLoginSuccess }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  
  const [loginMode, setLoginMode] = useState("admin"); // "admin" | "staff"
  const [staffCode, setStaffCode] = useState("");
  const [pin, setPin] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Forgot password flow state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotStep, setForgotStep] = useState(1);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotToken, setForgotToken] = useState("");
  const [forgotNewPassword, setForgotNewPassword] = useState("");
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotError, setForgotError] = useState("");
  const [forgotMessage, setForgotMessage] = useState("");


  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setMessage(""); setLoading(true);
    try {
      if (isRegistering) {
        await api.register(email, password, "customer", firstName, lastName, phone);
        setMessage("Account created! Please sign in.");
        setIsRegistering(false);
        setPassword("");
      } else {
        const payload = loginMode === "staff" ? { staff_code: staffCode, pin } : { email, password };
        const data = await api.login(payload);
        onLoginSuccess(data.user);
      }
    } catch (err) {
      setError(err.message || "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (qEmail, qPass) => {
    setError(""); setMessage(""); setLoading(true);
    try {
      const data = await api.login({ email: qEmail, password: qPass });
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || "Quick login failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    setForgotError(""); setForgotMessage(""); setForgotLoading(true);
    try {
      const data = await api.forgotPassword(forgotEmail);
      setForgotMessage(data.message || "Token sent! Please check your email or server log.");
      setForgotStep(2);
    } catch (err) {
      setForgotError(err.message || "Failed to send reset token.");
    } finally {
      setForgotLoading(false);
    }
  };

  const handleResetSubmit = async (e) => {
    e.preventDefault();
    setForgotError(""); setForgotMessage(""); setForgotLoading(true);
    try {
      await api.resetPassword(forgotEmail, forgotToken, forgotNewPassword);
      setMessage("Password successfully reset! Please sign in with your new credentials.");
      setShowForgotModal(false);
      setPassword("");
    } catch (err) {
      setForgotError(err.message || "Failed to reset password.");
    } finally {
      setForgotLoading(false);
    }
  };


  return (
    <div className="login-shell">

      {/* ── Left Hero Panel ── */}
      <div className="login-hero">
        <div className="login-hero-content animate-fade-in">
          {/* Logo */}
          <div className="login-hero-logo">S</div>

          <h1>
            FoodPilot<span>Kitchen</span>
          </h1>
          <p>
            One platform for home cooking and the full snack supply chain.
          </p>

          {/* Stats row */}
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
            gap: "0.75rem", marginBottom: "2.5rem"
          }}>
            {STATS.map(s => (
              <div key={s.label} style={{
                background: "var(--brand-glow)",
                border: "1px solid var(--brand-glow)",
                borderRadius: "var(--r-lg)", padding: "0.875rem",
                textAlign: "center"
              }}>
                <div style={{
                  fontFamily: "var(--font-heading)", fontSize: "1.5rem",
                  fontWeight: 900, color: "var(--brand)", lineHeight: 1
                }}>{s.value}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.2rem", fontWeight: 600 }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>

          {/* Features */}
          <div className="login-features">
            {FEATURES.map(f => (
              <div key={f.label} className="login-feature-item">
                <div className="login-feature-icon">
                  <f.icon size={16} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.875rem" }}>{f.label}</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "0.78rem" }}>{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right Form Panel ── */}
      <div className="login-form-panel">
        <div className="login-form-wrap animate-fade-in">

          <div className="login-form-title">
            {isRegistering ? "Create Account" : "Welcome back"}
          </div>
          <div className="login-form-sub">
            {isRegistering
              ? "Register as a customer to start ordering"
              : "Sign in to access your workspace"}
          </div>

          {error && (
            <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
              <Zap size={15} style={{ flexShrink: 0 }} /> {error}
            </div>
          )}
          {message && (
            <div className="alert alert-success" style={{ marginBottom: "1rem" }}>
              <Star size={15} style={{ flexShrink: 0 }} /> {message}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            
            {!isRegistering && (
              <div style={{ display: "flex", gap: "10px", marginTop: "1rem" }}>
                <button
                  type="button"
                  onClick={() => setLoginMode("admin")}
                  style={{
                    flex: 1, padding: "0.5rem", borderRadius: "var(--r-md)",
                    border: loginMode === "admin" ? "2px solid var(--brand)" : "1px solid var(--border)",
                    background: loginMode === "admin" ? "var(--brand-glow)" : "transparent",
                    color: loginMode === "admin" ? "var(--brand)" : "var(--text-secondary)",
                    cursor: "pointer", fontWeight: 600
                  }}
                >
                  Admin / Owner
                </button>
                <button
                  type="button"
                  onClick={() => setLoginMode("staff")}
                  style={{
                    flex: 1, padding: "0.5rem", borderRadius: "var(--r-md)",
                    border: loginMode === "staff" ? "2px solid var(--brand)" : "1px solid var(--border)",
                    background: loginMode === "staff" ? "var(--brand-glow)" : "transparent",
                    color: loginMode === "staff" ? "var(--brand)" : "var(--text-secondary)",
                    cursor: "pointer", fontWeight: 600
                  }}
                >
                  Staff / Kitchen
                </button>
              </div>
            )}

            {isRegistering || loginMode === "admin" ? (
              <>
                {/* Email */}
                <div className="form-group" style={{ margin: 0, marginTop: isRegistering ? 0 : "1rem" }}>
                  <label className="form-label">Email or Username</label>
                  <div className="input-icon-wrap">
                    <Mail size={15} className="input-icon" />
                    <input
                      type="text"
                      required
                      className="form-input"
                      placeholder="admin or email@example.com"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="form-group" style={{ margin: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label className="form-label">Password</label>
                    {!isRegistering && (
                      <button
                        type="button"
                        onClick={() => {
                          setShowForgotModal(true);
                          setForgotStep(1);
                          setForgotEmail(email);
                          setForgotToken("");
                          setForgotNewPassword("");
                          setForgotError("");
                          setForgotMessage("");
                        }}
                        style={{
                          background: "none", border: "none", color: "var(--brand)",
                          cursor: "pointer", fontSize: "0.78rem", fontWeight: 600,
                          padding: 0, textDecoration: "underline", fontFamily: "var(--font-body)"
                        }}
                      >
                        Forgot Password?
                      </button>
                    )}
                  </div>
                  <div className="input-icon-wrap" style={{ position: "relative" }}>

                    <Lock size={15} className="input-icon" />
                    <input
                      type={showPass ? "text" : "password"}
                      required
                      className="form-input"
                      placeholder="••••••••"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      style={{ paddingRight: "2.8rem" }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass(!showPass)}
                      style={{
                        position: "absolute", right: "0.9rem", top: "50%",
                        transform: "translateY(-50%)", background: "none",
                        border: "none", color: "var(--text-muted)", cursor: "pointer",
                        display: "flex"
                      }}
                    >
                      {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                {/* Staff Code */}
                <div className="form-group" style={{ margin: 0, marginTop: "1rem" }}>
                  <label className="form-label">4-Digit Staff ID</label>
                  <div className="input-icon-wrap">
                    <UserPlus size={15} className="input-icon" />
                    <input
                      type="text"
                      required
                      maxLength="4"
                      className="form-input"
                      placeholder="e.g. 1234"
                      value={staffCode}
                      onChange={e => setStaffCode(e.target.value)}
                    />
                  </div>
                </div>

                {/* PIN */}
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">4-Digit PIN</label>
                  <div className="input-icon-wrap" style={{ position: "relative" }}>
                    <Lock size={15} className="input-icon" />
                    <input
                      type={showPass ? "text" : "password"}
                      required
                      maxLength="4"
                      className="form-input"
                      placeholder="••••"
                      value={pin}
                      onChange={e => setPin(e.target.value)}
                      style={{ paddingRight: "2.8rem" }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass(!showPass)}
                      style={{
                        position: "absolute", right: "0.9rem", top: "50%",
                        transform: "translateY(-50%)", background: "none",
                        border: "none", color: "var(--text-muted)", cursor: "pointer",
                        display: "flex"
                      }}
                    >
                      {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* Registration extra fields */}
            {isRegistering && (
              <div className="animate-fade-in" style={{
                borderTop: "1px solid var(--border-subtle)", paddingTop: "1rem",
                display: "flex", flexDirection: "column", gap: "0.75rem"
              }}>
                <div className="grid-responsive-2col" style={{ gap: "0.75rem" }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">First Name</label>
                    <input type="text" required className="form-input" placeholder="Priya" value={firstName} onChange={e => setFirstName(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Last Name</label>
                    <input type="text" required className="form-input" placeholder="Sharma" value={lastName} onChange={e => setLastName(e.target.value)} />
                  </div>
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Phone Number</label>
                  <input type="tel" required maxLength={10} className="form-input" placeholder="9876543210" pattern="\d{10}" value={phone} onChange={e => { const val = e.target.value.replace(/\D/g, ''); if (val.length <= 10) setPhone(val); }} />
                </div>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ marginTop: "0.5rem", padding: "0.875rem" }}>
              {loading
                ? <><div style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> Processing…</>
                : isRegistering
                  ? <><UserPlus size={16} /> Create Account</>
                  : <><LogIn size={16} /> Sign In</>
              }
            </button>
          </form>

          {/* Toggle mode */}
          <div style={{ textAlign: "center", marginTop: "1rem" }}>
            <button
              onClick={() => { setIsRegistering(!isRegistering); setError(""); setMessage(""); }}
              style={{
                background: "none", border: "none", color: "var(--text-secondary)",
                cursor: "pointer", fontWeight: 600, fontSize: "0.82rem",
                textDecoration: "underline", fontFamily: "var(--font-body)"
              }}
            >
              {isRegistering ? "← Back to Sign In" : "New customer? Create account"}
            </button>
          </div>
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="modal-overlay" style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 1000
        }}>
          <div className="modal-content animate-fade-in" style={{
            background: "rgba(18, 22, 28, 0.95)", border: "1px solid rgba(249, 115, 22, 0.2)",
            boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)", borderRadius: "var(--r-lg)",
            padding: "2rem", width: "100%", maxWidth: "420px", position: "relative"
          }}>
            <h3 style={{ fontFamily: "var(--font-heading)", color: "var(--text-primary)", fontSize: "1.25rem", marginBottom: "0.5rem", fontWeight: 700, display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <Lock size={18} className="text-brand" />
              {forgotStep === 1 ? "Forgot Password" : "Reset Password"}
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginBottom: "1.25rem", lineHeight: 1.4 }}>
              {forgotStep === 1
                ? "Enter your account email to request a secure password reset token."
                : "Enter the reset token sent to your email (or logged to console) along with your new password."}
            </p>

            {forgotError && (
              <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
                <Zap size={15} style={{ flexShrink: 0 }} /> {forgotError}
              </div>
            )}
            {forgotMessage && (
              <div className="alert alert-success" style={{ marginBottom: "1rem" }}>
                <Star size={15} style={{ flexShrink: 0 }} /> {forgotMessage}
              </div>
            )}

            {forgotStep === 1 ? (
              <form onSubmit={handleForgotSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    required
                    className="form-input"
                    placeholder="email@example.com"
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                  />
                </div>
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="btn btn-secondary"
                    style={{ flex: 1, padding: "0.75rem" }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={forgotLoading}
                    className="btn btn-primary"
                    style={{ flex: 1, padding: "0.75rem" }}
                  >
                    {forgotLoading ? "Sending..." : "Send Token"}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleResetSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    required
                    className="form-input"
                    value={forgotEmail}
                    disabled
                  />
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Reset Token</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Enter received token"
                    value={forgotToken}
                    onChange={e => setForgotToken(e.target.value)}
                  />
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">New Password</label>
                  <input
                    type="password"
                    required
                    className="form-input"
                    placeholder="••••••••"
                    value={forgotNewPassword}
                    onChange={e => setForgotNewPassword(e.target.value)}
                  />
                </div>
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setForgotStep(1)}
                    className="btn btn-secondary"
                    style={{ flex: 1, padding: "0.75rem" }}
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={forgotLoading}
                    className="btn btn-primary"
                    style={{ flex: 1, padding: "0.75rem" }}
                  >
                    {forgotLoading ? "Resetting..." : "Reset Password"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

