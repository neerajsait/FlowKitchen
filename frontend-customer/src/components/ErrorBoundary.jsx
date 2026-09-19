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
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "var(--bg-base)", flexDirection: "column", gap: "1.5rem", padding: "2rem", textAlign: "center"
      }}>
        <div style={{ fontSize: "6rem", fontWeight: "900", color: "var(--brand)", lineHeight: 1, textShadow: "0 10px 30px rgba(249, 115, 22, 0.2)" }}>
          500
        </div>
        <h1 style={{ color: "var(--text-primary)", fontSize: "2rem", fontFamily: "var(--font-heading)", margin: 0 }}>
          Internal App Error
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "1rem", maxWidth: "450px", lineHeight: 1.6, margin: 0 }}>
          Oops! Something went wrong while rendering this page. Our engineers have been notified. Please try reloading the page or returning home.
        </p>
        <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
          <button onClick={this.handleReload} className="btn btn-primary" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <RefreshCw size={16} /> Reload Page
          </button>
          <button onClick={this.handleGoHome} className="btn btn-secondary" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Home size={16} /> Go Home
          </button>
        </div>
      </div>
    );
  }
}
