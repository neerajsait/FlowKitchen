import React from "react";
import { AlertTriangle, RefreshCw, Home } from "../ui/Icon";

/**
 * ErrorBoundary — catches render errors in child trees and shows a fallback UI.
 *
 * Usage:
 *   <ErrorBoundary>          — wraps the whole app
 *   <ErrorBoundary fallbackLabel="Admin Panel">  — wraps a specific view with a custom label
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, showDetails: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    // Log to console — swap for a real error reporting service (Sentry, etc.) in production
    console.error("[ErrorBoundary] Uncaught error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, showDetails: false });
    window.location.reload();
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, showDetails: false });
    window.location.href = "/";
  };

  toggleDetails = () => {
    this.setState(s => ({ showDetails: !s.showDetails }));
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    const isDev = import.meta.env.DEV;
    const label = this.props.fallbackLabel || "Page";

    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "var(--bg-base)",
        flexDirection: "column", gap: "1.5rem", padding: "2rem", textAlign: "center"
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: "50%",
          background: "rgba(239,68,68,0.1)", display: "flex",
          alignItems: "center", justifyContent: "center", color: "#ef4444"
        }}>
          <AlertTriangle size={32} />
        </div>

        <div style={{ fontSize: "5rem", fontWeight: "900", color: "var(--brand)", lineHeight: 1 }}>
          500
        </div>

        <h1 style={{ color: "var(--text-primary)", fontSize: "1.75rem", fontFamily: "var(--font-heading)", margin: 0 }}>
          {label} Crashed Unexpectedly
        </h1>

        <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", maxWidth: "480px", lineHeight: 1.65, margin: 0 }}>
          Something went wrong while rendering this section. Please try reloading. If the issue
          persists, contact support.
        </p>

        <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem", flexWrap: "wrap", justifyContent: "center" }}>
          <button onClick={this.handleReload} className="btn btn-primary"
            style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <RefreshCw size={16} /> Reload Page
          </button>
          <button onClick={this.handleGoHome} className="btn btn-secondary"
            style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Home size={16} /> Go to Dashboard
          </button>
        </div>

        {/* Developer details — only shown in dev mode or when toggled */}
        {isDev && this.state.error && (
          <div style={{ marginTop: "1rem", width: "100%", maxWidth: "700px" }}>
            <button onClick={this.toggleDetails} style={{
              background: "none", border: "1px solid var(--border-light)", color: "var(--text-muted)",
              padding: "0.35rem 0.8rem", borderRadius: "6px", cursor: "pointer", fontSize: "0.78rem"
            }}>
              {this.state.showDetails ? "Hide" : "Show"} Error Details
            </button>
            {this.state.showDetails && (
              <pre style={{
                background: "var(--bg-elevated)", border: "1px solid var(--border-light)",
                borderRadius: "8px", padding: "1rem", marginTop: "0.75rem",
                fontSize: "0.75rem", color: "var(--error, #ef4444)", textAlign: "left",
                overflowX: "auto", maxHeight: "300px", lineHeight: 1.5
              }}>
                <strong>{this.state.error?.toString()}</strong>
                {"\n\n"}
                {this.state.errorInfo?.componentStack}
              </pre>
            )}
          </div>
        )}
      </div>
    );
  }
}
