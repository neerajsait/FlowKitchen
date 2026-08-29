import React, { useState, useCallback } from "react";
import { Scanner } from "@yudiel/react-qr-scanner";
import { api } from "../utils/api";
import { ScanLine, CheckCircle, XCircle, Package, X } from "../ui/Icon";

export default function QRScanner({ onStockUpdated }) {
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);   // { success, message, data }
  const [loading, setLoading] = useState(false);

  const handleScan = useCallback(async (detectedCodes) => {
    if (loading || !detectedCodes || detectedCodes.length === 0) return;
    const rawValue = detectedCodes[0]?.rawValue;
    if (!rawValue) return;

    setScanning(false);
    setLoading(true);
    setResult(null);

    try {
      // Validate it's a JSON QR before sending for dispatch
      // If it fails JSON parsing, assume it's a product code
      let isJson = false;
      try {
        JSON.parse(rawValue);
        isJson = true;
      } catch (err) {
        // Not a JSON, treat as product code
      }

      if (isJson) {
        const data = await api.posScanArrival(rawValue);
        setResult({ success: true, message: data.message, data });
        if (onStockUpdated) onStockUpdated(rawValue);
      } else {
        // Treat as product code
        setResult({ success: true, message: `Scanned code: ${rawValue}`, data: { code: rawValue } });
        if (onStockUpdated) onStockUpdated(rawValue);
      }
    } catch (err) {
      setResult({ success: false, message: err.message || "Scan failed", data: null });
    } finally {
      setLoading(false);
    }
  }, [loading, onStockUpdated]);

  const handleError = (error) => {
    console.error("QR Scanner error:", error);
    setResult({ success: false, message: "Camera error: " + (error?.message || "unknown"), data: null });
    setScanning(false);
  };

  return (
    <div className="panel" style={{ padding: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "0.5rem", margin: 0 }}>
          <ScanLine size={18} /> Scan Stock Arrival
        </h3>
        {scanning && (
          <button className="btn btn-secondary" style={{ padding: "0.3rem 0.7rem", fontSize: "0.78rem" }} onClick={() => setScanning(false)}>
            <X size={13} /> Stop
          </button>
        )}
      </div>

      <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "1.25rem", lineHeight: "1.5" }}>
        When a stock delivery arrives, click <strong>Start Scan</strong> and point your camera at the dispatch QR label. The stock will be automatically added to your outlet in the system.
      </p>

      {!scanning && !loading && (
        <button className="btn btn-primary" style={{ width: "100%", padding: "0.75rem", fontSize: "0.95rem", marginBottom: "1rem" }} onClick={() => { setScanning(true); setResult(null); }}>
          <ScanLine size={16} /> Start Scan
        </button>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)", fontSize: "0.88rem" }}>
          <div className="spin" style={{ display: "inline-block", marginBottom: "0.5rem" }}>⏳</div>
          <div>Updating stock in database...</div>
        </div>
      )}

      {scanning && (
        <div style={{ borderRadius: "12px", overflow: "hidden", border: "2px solid var(--accent-primary)", marginBottom: "1rem" }}>
          <Scanner
            onScan={handleScan}
            onError={handleError}
            constraints={{ facingMode: "environment" }}
            styles={{ container: { width: "100%", maxHeight: "280px" } }}
          />
          <div style={{ textAlign: "center", padding: "0.5rem", background: "var(--bg-secondary)", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Point camera at QR code on the delivery box
          </div>
        </div>
      )}

      {result && (
        <div style={{
          padding: "1rem",
          borderRadius: "var(--radius-sm)",
          border: `1px solid ${result.success ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)"}`,
          background: result.success ? "var(--success-bg)" : "var(--alert-bg)",
          marginTop: "0.5rem"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: result.data ? "0.75rem" : 0 }}>
            {result.success
              ? <CheckCircle size={16} style={{ color: "var(--success-color)" }} />
              : <XCircle size={16} style={{ color: "var(--alert-color)" }} />
            }
            <span style={{ fontSize: "0.85rem", fontWeight: "600", color: result.success ? "var(--success-color)" : "var(--alert-color)" }}>
              {result.message}
            </span>
          </div>

          {result.success && result.data && (
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: "1.7", borderTop: "1px solid rgba(16,185,129,0.15)", paddingTop: "0.6rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.25rem" }}>
                <Package size={13} />
                <strong>{result.data.item}</strong>
              </div>
              <div><strong>+{result.data.qty_added}</strong> units added</div>
              <div> New total stock: <strong>{result.data.new_stock}</strong> units</div>
            </div>
          )}

          {!loading && (
            <button className="btn btn-secondary" style={{ marginTop: "0.75rem", width: "100%", fontSize: "0.8rem" }} onClick={() => { setResult(null); setScanning(true); }}>
              <ScanLine size={13} /> Scan Another
            </button>
          )}
        </div>
      )}
    </div>
  );
}
