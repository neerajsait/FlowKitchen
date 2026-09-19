import React from "react";
import { Home } from "../ui/Icon";

export default function NotFound404() {
  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--bg-base)",
      flexDirection: "column",
      gap: "1.5rem",
      padding: "2rem",
      textAlign: "center"
    }}>
      <div style={{
        fontSize: "6rem",
        fontWeight: "900",
        color: "var(--brand)",
        lineHeight: 1,
        textShadow: "0 10px 30px rgba(249, 115, 22, 0.2)"
      }}>
        404
      </div>
      <h1 style={{
        color: "var(--text-primary)",
        fontSize: "2rem",
        fontFamily: "var(--font-heading)",
        margin: 0
      }}>
        Page Not Found
      </h1>
      <p style={{
        color: "var(--text-secondary)",
        fontSize: "1rem",
        maxWidth: "400px",
        lineHeight: 1.6,
        margin: 0
      }}>
        The requested URL was not found on this server. It might have been moved or doesn't exist.
      </p>
      
      <button 
        onClick={() => { window.location.href = "/"; }}
        className="btn btn-primary"
        style={{ marginTop: "1rem", padding: "0.875rem 2rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}
      >
        <Home size={18} />
        Back to Dashboard
      </button>
    </div>
  );
}
