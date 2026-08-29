import React, { useState, useEffect } from "react";
import { api } from "../utils/api";
import { CheckCircle, XCircle, Loader2 } from "../ui/Icon";

export default function VerifyEmail() {
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("Verifying your email...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("Invalid or missing verification token.");
      return;
    }

    api.verifyEmail(token)
      .then(res => {
        setStatus("success");
        setMessage(res.message || "Email verified successfully!");
      })
      .catch(err => {
        setStatus("error");
        setMessage(err.message || "Verification failed.");
      });
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-base)", padding: "2rem" }}>
      <div className="panel" style={{ padding: "3rem", textAlign: "center", maxWidth: "400px", width: "100%" }}>
        {status === "loading" && (
          <div style={{ color: "var(--brand)" }}>
            <Loader2 size={48} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.25rem", color: "var(--text-primary)" }}>{message}</h2>
          </div>
        )}
        {status === "success" && (
          <div style={{ color: "var(--success)" }}>
            <CheckCircle size={48} style={{ margin: "0 auto 1rem" }} />
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.25rem", marginBottom: "1rem" }}>Success!</h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>{message}</p>
            <a href="/" className="btn btn-primary" style={{ display: "inline-block", textDecoration: "none" }}>Go to Login</a>
          </div>
        )}
        {status === "error" && (
          <div style={{ color: "var(--error)" }}>
            <XCircle size={48} style={{ margin: "0 auto 1rem" }} />
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.25rem", marginBottom: "1rem" }}>Verification Failed</h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>{message}</p>
            <a href="/" className="btn btn-secondary" style={{ display: "inline-block", textDecoration: "none" }}>Go to Login</a>
          </div>
        )}
      </div>
    </div>
  );
}
