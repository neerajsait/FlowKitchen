import React from "react";
import { AlertTriangle, RefreshCw, Home } from "../ui/Icon";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo });
    console.error("[ErrorBoundary] Uncaught error:", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("user");
    window.location.href = "/";
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0d1117", padding: "2rem" }}>
        <div style={{ background: "rgba(18,22,28,0.95)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "1.5rem", padding: "3rem 2.5rem", maxWidth: 520, width: "100%", textAlign: "center" }}>
          <div style={{ width: 72, height: 72, background: "rgba(239,68,68,0.1)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.5rem", color: "#ef4444" }}>
            <AlertTriangle size={36} />
          </div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "#f0f6fc", margin: "0 0 0.5rem" }}>Something went wrong</h1>
          <p style={{ color: "#8b949e", fontSize: "0.95rem", lineHeight: 1.6, margin: "0 0 0.5rem" }}>This is an internal server error, not something you did wrong.</p>
          {this.state.error && (
            <div style={{ background: "#161b22", color: "#f87171", padding: "1rem", borderRadius: "0.5rem", textAlign: "left", fontSize: "0.8rem", overflowX: "auto", margin: "1rem 0" }}>
              <strong>Error:</strong> {this.state.error.toString()}
              {this.state.errorInfo?.componentStack && (
                <pre style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#9ca3af", whiteSpace: "pre-wrap" }}>
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </div>
          )}
          <p style={{ color: "#6e7681", fontSize: "0.85rem", lineHeight: 1.6, margin: "0 0 2rem" }}>If this persists, please contact support. You can try refreshing the page or going back to home.</p>
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
            <button onClick={this.handleReload} style={{ padding: "0.75rem 1.5rem", background: "#f97316", color: "#fff", border: "none", borderRadius: "0.75rem", cursor: "pointer" }}><RefreshCw size={16} /> Reload Page</button>
            <button onClick={this.handleGoHome} style={{ padding: "0.75rem 1.5rem", background: "transparent", color: "#8b949e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "0.75rem", cursor: "pointer" }}><Home size={16} /> Go to Login</button>
          </div>
        </div>
      </div>
    );
  }
}
