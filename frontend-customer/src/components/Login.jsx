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

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");

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
        await api.register(email, password, "customer", firstName, lastName, phone, address);
        setMessage("Account created! Please sign in.");
        setIsRegistering(false);
        setPassword("");
      } else {
        const data = await api.login({ email, password });
        onLoginSuccess(data.user);
      }
    } catch (err) {
      setError(err.message || "An error occurred. Please try again.");
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
    <div className="split-layout">
      
      {/* ── Login Panel ── */}
      <div 
        className={`split-panel left-panel ${!isRegistering ? "active" : "inactive"}`}
        onClick={() => { if (isRegistering) setIsRegistering(false); }}
      >
        <div className="split-bg" style={{ backgroundImage: "url('https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=1600&q=80')" }}></div>
        <div className="split-overlay-text" style={{ writingMode: "horizontal-tb", transform: "none", textAlign: "center" }}>
          <div style={{ fontSize: "1rem", color: "var(--green)", marginBottom: "0.5rem", letterSpacing: "1px" }}> FlowKitchen</div>
          <div style={{ fontSize: "1.5rem" }}>SIGN IN</div>
        </div>
        
        <div className="split-content">
          <div className="glass-form">
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
              <div style={{ width: 40, height: 40, background: "var(--green)", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.25rem" }}></div>
              <div>
                <div style={{ fontWeight: 800, fontSize: "1.1rem", lineHeight: 1 }}>FlowKitchen</div>
                <div style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: "1px" }}>FlowKitchen</div>
              </div>
            </div>

            <h2 className="glass-title">Welcome Back</h2>
            <p className="glass-sub">Sign in to access your workspace.</p>

            {error && !isRegistering && (
              <div className="alert alert-error" style={{ marginBottom: "1rem", background: "rgba(239, 68, 68, 0.2)", border: "1px solid rgba(239, 68, 68, 0.4)", color: "#fff" }}>
                <Zap size={15} style={{ flexShrink: 0 }} /> {error}
              </div>
            )}
            {message && !isRegistering && (
              <div className="alert alert-success" style={{ marginBottom: "1rem", background: "rgba(34, 197, 94, 0.2)", border: "1px solid rgba(34, 197, 94, 0.4)", color: "#fff" }}>
                <Star size={15} style={{ flexShrink: 0 }} /> {message}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: "1.5rem" }}>
                <label className="glass-label">Email or Username</label>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <input 
                    type="text" 
                    required 
                    className="glass-input" 
                    placeholder="admin or email@example.com" 
                    value={email} 
                    onChange={e => setEmail(e.target.value)} 
                  />
                  <Mail size={18} className="glass-icon" />
                </div>
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                  <label className="glass-label" style={{ marginBottom: 0 }}>Password</label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotModal(true);
                      setForgotStep(1); setForgotEmail(email); setForgotToken(""); setForgotNewPassword(""); setForgotError(""); setForgotMessage("");
                    }}
                    className="glass-link"
                  >
                    Forgot Password?
                  </button>
                </div>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <input 
                    type={showPass ? "text" : "password"} 
                    required 
                    className="glass-input" 
                    placeholder="••••••••" 
                    value={password} 
                    onChange={e => setPassword(e.target.value)} 
                  />
                  <Lock size={18} className="glass-icon" />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    style={{
                      position: "absolute", right: "1rem", top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", color: "rgba(255,255,255,0.5)", cursor: "pointer", display: "flex"
                    }}
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button type="submit" className="glass-btn" disabled={loading}>
                {loading ? "Signing in..." : <>Sign In <LogIn size={18} /></>}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* ── Register Panel ── */}
      <div 
        className={`split-panel right-panel ${isRegistering ? "active" : "inactive"}`}
        onClick={() => { if (!isRegistering) setIsRegistering(true); }}
      >
        <div className="split-bg" style={{ backgroundImage: "url('https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&q=80')" }}></div>
        <div className="split-overlay-text" style={{ writingMode: "horizontal-tb", transform: "none", textAlign: "center" }}>
          <div style={{ fontSize: "1rem", color: "var(--green)", marginBottom: "0.5rem", letterSpacing: "1px" }}> FlowKitchen</div>
          <div style={{ fontSize: "1.5rem" }}>REGISTER</div>
        </div>

        <div className="split-content">
          <div className="glass-form" style={{ padding: "2rem 2.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
              <div style={{ width: 40, height: 40, background: "var(--green)", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.25rem" }}></div>
              <div>
                <div style={{ fontWeight: 800, fontSize: "1.1rem", lineHeight: 1 }}>FlowKitchen</div>
                <div style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: "1px" }}>FlowKitchen</div>
              </div>
            </div>
            
            <h2 className="glass-title">Create Account</h2>
            <p className="glass-sub">Join FlowKitchen today.</p>

            {error && isRegistering && (
              <div className="alert alert-error" style={{ marginBottom: "1rem", background: "rgba(239, 68, 68, 0.2)", border: "1px solid rgba(239, 68, 68, 0.4)", color: "#fff" }}>
                <Zap size={15} style={{ flexShrink: 0 }} /> {error}
              </div>
            )}
            {message && isRegistering && (
              <div className="alert alert-success" style={{ marginBottom: "1rem", background: "rgba(34, 197, 94, 0.2)", border: "1px solid rgba(34, 197, 94, 0.4)", color: "#fff" }}>
                <Star size={15} style={{ flexShrink: 0 }} /> {message}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
                <div>
                  <label className="glass-label">First Name</label>
                  <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                    <input type="text" required className="glass-input" style={{ paddingLeft: "1rem" }} placeholder="John" value={firstName} onChange={e => setFirstName(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="glass-label">Last Name</label>
                  <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                    <input type="text" required className="glass-input" style={{ paddingLeft: "1rem" }} placeholder="Doe" value={lastName} onChange={e => setLastName(e.target.value)} />
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label className="glass-label">Email</label>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <input type="email" required className="glass-input" placeholder="john@example.com" value={email} onChange={e => setEmail(e.target.value)} />
                  <Mail size={18} className="glass-icon" />
                </div>
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label className="glass-label">Phone Number</label>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <input type="tel" required className="glass-input" placeholder="10-digit mobile number" value={phone} onChange={e => setPhone(e.target.value)} />
                </div>
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label className="glass-label">Delivery Address</label>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <textarea required className="glass-input" placeholder="Enter your full address" rows={2} value={address} onChange={e => setAddress(e.target.value)} style={{ paddingLeft: "1rem", paddingTop: "0.75rem", resize: "none" }} />
                </div>
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label className="glass-label">Password</label>
                <div className="glass-input-wrap" style={{ marginBottom: 0 }}>
                  <input type={showPass ? "text" : "password"} required className="glass-input" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} />
                  <Lock size={18} className="glass-icon" />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    style={{
                      position: "absolute", right: "1rem", top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", color: "rgba(255,255,255,0.5)", cursor: "pointer", display: "flex"
                    }}
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button type="submit" className="glass-btn" disabled={loading} style={{ marginTop: "0.5rem" }}>
                {loading ? "Creating account..." : <>Create Account <UserPlus size={18} /></>}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="modal-overlay" style={{ backdropFilter: "blur(8px)" }} onClick={() => setShowForgotModal(false)}>
          <div className="modal-content animate-fade-in" onClick={e => e.stopPropagation()} style={{ background: "rgba(20,20,20,0.85)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", backdropFilter: "blur(16px)" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: "0.5rem" }}>Reset Password</h2>
            
            {forgotError && <div className="alert alert-error" style={{ marginBottom: "1rem" }}>{forgotError}</div>}
            {forgotMessage && <div className="alert alert-success" style={{ marginBottom: "1rem" }}>{forgotMessage}</div>}

            {forgotStep === 1 && (
              <form onSubmit={handleForgotSubmit}>
                <p style={{ fontSize: "0.875rem", color: "rgba(255,255,255,0.6)", marginBottom: "1rem" }}>Enter your email to receive a reset token.</p>
                <div>
                  <label className="glass-label">Email Address</label>
                  <div className="glass-input-wrap" style={{ marginBottom: "1.5rem" }}>
                    <input type="email" required className="glass-input" value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} />
                    <Mail size={18} className="glass-icon" />
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
                  <button type="button" className="glass-link" onClick={() => setShowForgotModal(false)}>Cancel</button>
                  <button type="submit" className="glass-btn" style={{ width: "auto", padding: "0.75rem 1.5rem", marginTop: 0 }} disabled={forgotLoading}>
                    {forgotLoading ? "Sending..." : "Send Token"}
                  </button>
                </div>
              </form>
            )}

            {forgotStep === 2 && (
              <form onSubmit={handleResetSubmit}>
                <p style={{ fontSize: "0.875rem", color: "rgba(255,255,255,0.6)", marginBottom: "1rem" }}>Enter the token sent to your email and your new password.</p>
                
                <div>
                  <label className="glass-label">Reset Token</label>
                  <div className="glass-input-wrap">
                    <input type="text" required className="glass-input" style={{ paddingLeft: "1rem" }} value={forgotToken} onChange={e => setForgotToken(e.target.value)} />
                  </div>
                </div>

                <div>
                  <label className="glass-label">New Password</label>
                  <div className="glass-input-wrap">
                    <input type="password" required className="glass-input" style={{ paddingLeft: "1rem" }} value={forgotNewPassword} onChange={e => setForgotNewPassword(e.target.value)} />
                  </div>
                </div>

                <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                  <button type="button" className="glass-link" onClick={() => setShowForgotModal(false)}>Cancel</button>
                  <button type="submit" className="glass-btn" style={{ width: "auto", padding: "0.75rem 1.5rem", marginTop: 0 }} disabled={forgotLoading}>
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
