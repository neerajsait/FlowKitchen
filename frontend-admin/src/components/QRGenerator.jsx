import React, { useState } from "react";
import { api } from "../utils/api";
import { QrCode, Printer, RefreshCw, CheckCircle } from "../ui/Icon";

export default function QRGenerator({ outlets, menuItems }) {
  const [form, setForm] = useState({ order_id: "", type: "B2B2C", item: "", qty: "", outlet_id: "", destination: "", batch_number: "", expiry_date: "" });
  const [qrResult, setQrResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    let updated = { ...form, [name]: value };
    if (name === "outlet_id") {
      const outlet = outlets.find(o => String(o.id) === value);
      updated.destination = outlet ? outlet.name : "";
    }
    setForm(updated);
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError(""); setQrResult(null);
    if (!form.item || !form.qty || !form.outlet_id) { setError("Item, quantity and outlet are required."); return; }
    setLoading(true);
    try {
      const payload = {
        order_id: form.order_id || null,
        type: form.type,
        item: form.item,
        qty: parseInt(form.qty),
        outlet_id: parseInt(form.outlet_id),
        destination: form.destination,
        batch_number: form.batch_number || null,
        expiry_date: form.expiry_date || null
      };
      const result = await api.adminGenerateQR(payload);
      setQrResult(result);
    } catch (err) { setError(err.message || "Failed to generate QR code"); }
    finally { setLoading(false); }
  };

  const handlePrint = () => {
    if (!qrResult?.qr_image) return;
    const p = qrResult.payload;
    const w = window.open("", "_blank");
    w.document.write(`<html><head><title>Dispatch Label</title><style>
      body{font-family:Arial,sans-serif;padding:32px;text-align:center;background:#fff}
      .box{border:2px solid #000;padding:24px;display:inline-block;border-radius:8px;max-width:300px}
      h2{font-size:18px;margin:0 0 12px}p{font-size:13px;margin:4px 0;color:#444}
      img{display:block;margin:16px auto;width:220px;height:220px}
      .note{font-size:11px;color:#999;margin-top:12px}
    </style></head><body onload="window.print()"><div class="box">
      <h2> Dispatch Label</h2>
      <p><strong>Item:</strong> ${p.item}</p>
      <p><strong>Qty:</strong> ${p.qty} units</p>
      <p><strong>Destination:</strong> ${p.destination || "—"}</p>
      ${p.order_id ? `<p><strong>Order:</strong> #${p.order_id}</p>` : ""}
      ${p.batch_number ? `<p><strong>Batch:</strong> ${p.batch_number}</p>` : ""}
      ${p.expiry_date ? `<p><strong>Expiry:</strong> ${p.expiry_date}</p>` : ""}
      <p><strong>Type:</strong> ${p.type}</p>
      <img referrerPolicy="no-referrer" src="${qrResult.qr_image}" alt="QR"/>
      <p class="note">Scan on arrival to update stock</p>
    </div></body></html>`);
    w.document.close();
  };

  return (
    <div className="grid-responsive-2col" style={{ gap: "1.5rem", alignItems: "start" }}>
      <div className="panel" style={{ padding: "1.5rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "700", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <QrCode size={18} /> Generate Dispatch QR
        </h3>
        {error && <div style={{ background: "var(--alert-bg)", color: "var(--alert-color)", padding: "0.6rem 0.9rem", borderRadius: "var(--radius-sm)", fontSize: "0.82rem", fontWeight: "600", marginBottom: "1rem", border: "1px solid rgba(239,68,68,0.2)" }}>{error}</div>}
        <form onSubmit={handleGenerate}>
          <div className="form-group">
            <label className="form-label">Destination Outlet *</label>
            <select className="form-input" name="outlet_id" value={form.outlet_id} onChange={handleChange} required>
              <option value="">-- Select Outlet --</option>
              {outlets.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Food Item *</label>
            <select className="form-input" name="item" value={form.item} onChange={handleChange} required>
              <option value="">-- Select Item --</option>
              {menuItems.filter(m => m.business_type === "snack_supply" || m.business_type === "both").map(m => (
                <option key={m.id} value={m.name}>{m.name}</option>
              ))}
            </select>
          </div>
          <div className="grid-responsive-2col" style={{ gap: "0.75rem" }}>
            <div className="form-group">
              <label className="form-label">Quantity *</label>
              <input type="number" min="1" name="qty" className="form-input" placeholder="e.g. 50" value={form.qty} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label className="form-label">Order ID (optional)</label>
              <input type="text" name="order_id" className="form-input" placeholder="e.g. 1024" value={form.order_id} onChange={handleChange} />
            </div>
          </div>
          <div className="grid-responsive-2col" style={{ gap: "0.75rem" }}>
            <div className="form-group">
              <label className="form-label">Batch Number (optional)</label>
              <input type="text" name="batch_number" className="form-input" placeholder="e.g. BATCH-01" value={form.batch_number} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label className="form-label">Expiry Date (optional)</label>
              <input type="date" name="expiry_date" className="form-input" value={form.expiry_date} onChange={handleChange} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Transfer Type</label>
            <select className="form-input" name="type" value={form.type} onChange={handleChange}>
              <option value="B2B2C">B2B2C Snack Supply</option>
              <option value="Restock">Restock</option>
            </select>
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: "100%", marginTop: "0.5rem" }} disabled={loading}>
            {loading ? <RefreshCw size={14} /> : <QrCode size={14} />} {loading ? " Generating..." : " Generate QR Code"}
          </button>
        </form>
      </div>

      <div className="panel" style={{ padding: "1.5rem", minHeight: "320px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        {!qrResult ? (
          <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            <QrCode size={48} style={{ opacity: 0.2, marginBottom: "0.75rem", display: "block", margin: "0 auto 0.75rem" }} />
            <p>Fill the form and click<br /><strong>Generate QR Code</strong></p>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: "0.75rem" }}>
              <CheckCircle size={16} style={{ color: "var(--success-color)", verticalAlign: "middle" }} />
              <span style={{ fontSize: "0.82rem", color: "var(--success-color)", fontWeight: "600", marginLeft: "0.4rem" }}>QR Ready!</span>
            </div>
            {qrResult.qr_image ? (
              <img referrerPolicy="no-referrer" src={qrResult.qr_image} alt="Dispatch QR Code" style={{ width: "200px", height: "200px", border: "1px solid var(--border-light)", borderRadius: "8px", marginBottom: "1rem" }} />
            ) : (
              <div style={{ width: "200px", height: "200px", background: "var(--bg-secondary)", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>No image returned</div>
            )}
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "1rem", textAlign: "left", width: "100%", lineHeight: "1.6" }}>
              <div><strong>Item:</strong> {qrResult.payload.item}</div>
              <div><strong>Qty:</strong> {qrResult.payload.qty} units</div>
              <div><strong>Outlet:</strong> {qrResult.payload.destination}</div>
              {qrResult.payload.order_id && <div><strong>Order:</strong> #{qrResult.payload.order_id}</div>}
              {qrResult.payload.batch_number && <div><strong>Batch:</strong> {qrResult.payload.batch_number}</div>}
              {qrResult.payload.expiry_date && <div><strong>Expiry:</strong> {qrResult.payload.expiry_date}</div>}
            </div>
            <button className="btn btn-primary" style={{ width: "100%" }} onClick={handlePrint} disabled={!qrResult.qr_image}>
              <Printer size={14} /> Print Label
            </button>
          </>
        )}
      </div>
    </div>
  );
}
