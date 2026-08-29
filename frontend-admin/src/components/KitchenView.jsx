import React, { useState, useEffect } from "react";
import { api } from "../utils/api";
import {
  ChefHat, Package, Clock, CheckCircle, Flame, ArrowRight,
  LogOut, RefreshCw, AlertTriangle, Plus, Grid, QrCode
} from "../ui/Icon";

const premiumStyles = `
  .kv-wrapper {
    display: flex;
    min-height: 100vh;
    background: var(--bg-canvas);
    font-family: var(--font-body);
    color: var(--text-primary);
    animation: fadeIn 0.3s ease-out;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  
  .kv-sidebar {
    width: 220px;
    background: var(--bg-card);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    padding: 1rem;
  }
  
  .kv-brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 2rem;
  }
  
  .kv-brand-icon {
    width: 36px;
    height: 36px;
    background: var(--brand);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
  }
  
  .kv-nav-btn {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 0.25rem;
  }
  
  .kv-nav-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }
  
  .kv-nav-btn.active {
    background: var(--brand-dim);
    color: var(--brand);
    border: 1px solid var(--border-brand);
  }
  
  .kv-main {
    flex: 1;
    padding: 0.5rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  
  .kv-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    background: var(--bg-card);
    padding: 0.5rem 1rem;
    border-radius: 8px;
    border: 1px solid var(--border-subtle);
  }
  
  .kv-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--text-primary);
    margin: 0;
  }
  
  .kv-btn {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: none;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  
  .kv-btn-primary {
    background: var(--brand);
    color: white;
  }
  .kv-btn-primary:hover { opacity: 0.9; }
  
  .kv-btn-success {
    background: var(--success);
    color: white;
  }
  .kv-btn-success:hover { opacity: 0.9; }

  .kv-btn-icon {
    width: 36px;
    height: 36px;
    border-radius: 6px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-card);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.2s;
  }
  .kv-btn-icon:hover { background: var(--bg-hover); color: var(--text-primary); }
  
  .kv-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.75rem;
  }
  
  .kv-card {
    background: var(--bg-card);
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid var(--border-default);
    animation: slideUp 0.3s ease-out forwards;
    display: flex;
    flex-direction: column;
  }
  
  @keyframes slideUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  
  .kv-badge {
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
  }
  
  .kv-badge-pending { background: var(--warning-bg); color: var(--warning); border: 1px solid var(--warning); }
  .kv-badge-processing { background: var(--info-bg); color: var(--info); border: 1px solid var(--info); }
  
  .kv-items-list {
    background: var(--bg-hover);
    border-radius: 6px;
    padding: 0.75rem;
    margin: 0.75rem 0;
    flex: 1;
  }
  
  .kv-item-row {
    display: flex;
    justify-content: space-between;
    padding: 0.4rem 0;
    border-bottom: 1px dashed var(--border-subtle);
    font-size: 0.9rem;
  }
  .kv-item-row:last-child { border-bottom: none; }
  
  .kv-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s ease-out;
  }
  
  .kv-modal {
    background: var(--bg-card);
    border-radius: 12px;
    padding: 1.5rem;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    animation: slideUp 0.3s ease-out;
  }

  .kv-input {
    width: 100%;
    padding: 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--border-default);
    background: var(--bg-input);
    font-size: 0.95rem;
    outline: none;
  }
  .kv-input:focus {
    border-color: var(--brand);
    box-shadow: 0 0 0 2px var(--brand-glow);
  }
  
  .spin-anim {
    animation: spin 1s linear infinite;
  }
  @keyframes spin { 100% { transform: rotate(360deg); } }
`;

export default function KitchenView({ onLogout, dbMode }) {
  const [activeTab, setActiveTab] = useState("orders");
  const [orders, setOrders] = useState([]);
  const [restockReqs, setRestockReqs] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const [showProduceModal, setShowProduceModal] = useState(false);
  const [batchForm, setBatchForm] = useState({ menu_item_id: "", quantity: 1, expiry_date: "" });
  const [producedQR, setProducedQR] = useState(null);
  const [viewOrderQR, setViewOrderQR] = useState(null);

  const alertMsg = (msg) => {
    setToast({ message: msg, type: msg.toLowerCase().includes("failed") ? "error" : "success" });
  };

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "orders") {
        const o = await api.getKitchenOrders();
        setOrders(o);
      } else {
        const r = await api.getStockRequests();
        setRestockReqs(r);
        const m = await api.getFoodsMenu();
        setMenuItems(m);
      }
    } catch (err) {
      alertMsg(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000); // 15s refresh for responsiveness
    return () => clearInterval(interval);
  }, [activeTab]);

  const updateOrderStatus = async (id, status) => {
    try {
      await api.updateKitchenOrderStatus(id, status);
      alertMsg(`Order marked as ${status}`);
      loadData();
    } catch (err) {
      alertMsg(err.message || "Failed to update status");
    }
  };

  const handleProduceBatch = async (e) => {
    e.preventDefault();
    try {
      const res = await api.produceBatch(batchForm.menu_item_id, batchForm.quantity, batchForm.expiry_date);
      setProducedQR(res.batch);
      alertMsg("Batch Produced!");
      loadData();
    } catch (err) {
      alertMsg(err.message || "Failed to produce batch");
    }
  };

  return (
    <>
      <style>{premiumStyles}</style>
      <div className="kv-wrapper">
        <aside className="kv-sidebar">
          <div className="kv-brand">
            <div className="kv-brand-icon"><ChefHat size={28} /></div>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 800, margin: 0, color: "#0f172a" }}>Kitchen Hub</h2>
              <p style={{ fontSize: "0.75rem", color: "#64748b", margin: 0, fontWeight: 600 }}>{dbMode.toUpperCase()} MODE</p>
            </div>
          </div>
          
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "1rem" }}>
              Operations
            </p>
            <button className={`kv-nav-btn ${activeTab === "orders" ? "active" : ""}`} onClick={() => setActiveTab("orders")}>
              <Flame size={20} /> Live Orders
            </button>
            <button className={`kv-nav-btn ${activeTab === "restock" ? "active" : ""}`} onClick={() => setActiveTab("restock")}>
              <Package size={20} /> Restock & Produce
            </button>
          </div>
          
          <button className="kv-nav-btn" onClick={onLogout} style={{ color: "#ef4444" }}>
            <LogOut size={20} /> Sign Out
          </button>
        </aside>

        <main className="kv-main">
          <header className="kv-header">
            <h1 className="kv-title">
              {activeTab === "orders" ? "Live Customer Orders" : "Restock Requests & Production"}
            </h1>
            <div style={{ display: "flex", gap: "1rem" }}>
              <button className="kv-btn-icon" onClick={loadData} disabled={loading} title="Refresh">
                <RefreshCw size={20} className={loading ? "spin-anim" : ""} />
              </button>
              {activeTab === "restock" && (
                <button className="kv-btn kv-btn-primary" onClick={() => {
                  setShowProduceModal(true);
                  setProducedQR(null);
                }}>
                  <Plus size={18} /> Produce Batch
                </button>
              )}
            </div>
          </header>

          {activeTab === "orders" && (
            <div className="kv-grid">
              {orders.length === 0 && !loading && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: "4rem 2rem", background: "rgba(255,255,255,0.5)", borderRadius: "20px" }}>
                  <CheckCircle size={64} color="#22c55e" style={{ marginBottom: "1rem" }} />
                  <h3 style={{ fontSize: "1.5rem", color: "#0f172a", marginBottom: "0.5rem" }}>Kitchen is Clear!</h3>
                  <p style={{ color: "#64748b" }}>There are no pending orders right now. Good job team.</p>
                </div>
              )}
              {orders.map(o => (
                <div key={o.id} className="kv-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <span style={{ fontSize: "1.25rem", fontWeight: 800, color: "#0f172a" }}>#{o.id}</span>
                    <span className={`kv-badge ${o.status === 'processing' ? 'kv-badge-processing' : 'kv-badge-pending'}`}>
                      {o.status}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#64748b", fontSize: "0.85rem", fontWeight: 600 }}>
                    <Clock size={14} /> {new Date(o.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </div>
                  
                  <div className="kv-items-list">
                    {o.items.map((i, idx) => (
                      <div key={idx} className="kv-item-row">
                        <span style={{ fontWeight: 600, color: "#334155" }}>{i.menu_item_name}</span>
                        <span style={{ fontWeight: 800, color: "#ea580c" }}>x{i.quantity}</span>
                      </div>
                    ))}
                  </div>
                  
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    {o.status === "pending" && (
                      <button className="kv-btn kv-btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={() => updateOrderStatus(o.id, "processing")}>
                        <Flame size={18} /> Start Cooking
                      </button>
                    )}
                    {o.status === "processing" && (
                      <button className="kv-btn kv-btn-success" style={{ width: "100%", justifyContent: "center" }} onClick={() => updateOrderStatus(o.id, "ready")}>
                        <CheckCircle size={18} /> Mark Ready
                      </button>
                    )}
                    {o.qr_code_base64 && (
                      <button className="kv-btn" style={{ width: "auto", justifyContent: "center", background: "#f8fafc", color: "#334155", border: "1px solid #cbd5e1" }} onClick={() => setViewOrderQR(o)}>
                        <QrCode size={18} /> QR
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "restock" && (
            <div className="kv-card" style={{ width: "100%", animation: "fadeIn 0.5s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
                <div style={{ background: "#fef3c7", padding: "0.5rem", borderRadius: "10px" }}>
                  <AlertTriangle size={24} color="#d97706" />
                </div>
                <h3 style={{ margin: 0, fontSize: "1.25rem", color: "#0f172a" }}>Critical Restock Alerts</h3>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Location</th>
                      <th>Menu Item</th>
                      <th>Type</th>
                      <th>Quantity</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {restockReqs.length === 0 ? (
                      <tr><td colSpan="6" style={{ textAlign: "center", padding: "3rem", color: "#64748b" }}>No pending stock requests.</td></tr>
                    ) : (
                      restockReqs.map(r => (
                        <tr key={r.id}>
                          <td style={{ fontWeight: 600, color: "#475569" }}>{r.outlet_name || `Outlet #${r.outlet_id}`}</td>
                          <td style={{ fontWeight: 700, color: "#0f172a" }}>{r.menu_item_name}</td>
                          <td>{r.type}</td>
                          <td>
                            <span style={{ background: "#e0e7ff", color: "#4338ca", padding: "0.25rem 0.75rem", borderRadius: "8px", fontWeight: 700 }}>
                              {r.quantity}
                            </span>
                          </td>
                          <td>
                            <span className={`status-badge status-${r.status.toLowerCase()}`}>
                              {r.status}
                            </span>
                          </td>
                          <td style={{ display: "flex", gap: "0.5rem" }}>
                            {r.status === "Pending" && (
                              <button className="btn btn-secondary btn-sm" onClick={async () => {
                                try {
                                  await api.updateStockRequestStatus(r.id, "In Progress");
                                  alertMsg("Request accepted.");
                                  const reqs = await api.getStockRequests();
                                  setRestockReqs(reqs);
                                } catch (e) { alertMsg(e.message); }
                              }}>Accept</button>
                            )}
                            {(r.status === "Pending" || r.status === "In Progress") && (
                              <button className="btn btn-primary btn-sm" onClick={async () => {
                                try {
                                  await api.updateStockRequestStatus(r.id, "Dispatched");
                                  alertMsg("Items dispatched to outlet!");
                                  const reqs = await api.getStockRequests();
                                  setRestockReqs(reqs);
                                } catch (e) { alertMsg(e.message); }
                              }}>Dispatch</button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>

        {showProduceModal && (
          <div className="kv-modal-overlay" onClick={() => setShowProduceModal(false)}>
            <div className="kv-modal" onClick={e => e.stopPropagation()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
                <h2 style={{ margin: 0, fontSize: "1.5rem", color: "#0f172a", display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <Package size={24} color="#ea580c" />
                  {producedQR ? "Batch Generated" : "Produce Batch"}
                </h2>
                <button className="kv-btn-icon" onClick={() => setShowProduceModal(false)} style={{ width: "36px", height: "36px" }}>
                  <LogOut size={16} />
                </button>
              </div>
              
              {!producedQR ? (
                <form onSubmit={handleProduceBatch} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 700, color: "#475569", marginBottom: "0.5rem" }}>Menu Item</label>
                    <select className="kv-input" required value={batchForm.menu_item_id} onChange={e => setBatchForm({...batchForm, menu_item_id: e.target.value})}>
                      <option value="">Select an item...</option>
                      {menuItems.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                    </select>
                  </div>
                  <div className="grid-responsive-2col" style={{ gap: "1rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 700, color: "#475569", marginBottom: "0.5rem" }}>Quantity</label>
                      <input type="number" className="kv-input" required min="1" value={batchForm.quantity} onChange={e => setBatchForm({...batchForm, quantity: e.target.value})} />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 700, color: "#475569", marginBottom: "0.5rem" }}>Expiry Date</label>
                      <input type="date" className="kv-input" required value={batchForm.expiry_date} onChange={e => setBatchForm({...batchForm, expiry_date: e.target.value})} />
                    </div>
                  </div>
                  <div style={{ marginTop: "1rem", display: "flex", gap: "1rem" }}>
                    <button type="button" className="kv-btn" style={{ flex: 1, background: "#f1f5f9", color: "#475569" }} onClick={() => setShowProduceModal(false)}>Cancel</button>
                    <button type="submit" className="kv-btn kv-btn-primary" style={{ flex: 2, justifyContent: "center" }} disabled={loading}>
                      Generate QR <ArrowRight size={18} />
                    </button>
                  </div>
                </form>
              ) : (
                <div style={{ textAlign: "center" }}>
                  <div style={{ background: "#f8fafc", padding: "1.5rem", borderRadius: "20px", display: "inline-block", marginBottom: "1.5rem", border: "2px dashed #cbd5e1" }}>
                    <img referrerPolicy="no-referrer" src={producedQR.qr_code_base64} alt="Batch QR Code" style={{ width: "200px", height: "200px" }} />
                  </div>
                  <h3 style={{ fontSize: "1.5rem", fontWeight: 800, color: "#ea580c", marginBottom: "0.5rem" }}>{producedQR.batch_number}</h3>
                  <div style={{ display: "inline-block", background: "#f1f5f9", padding: "1rem 2rem", borderRadius: "12px", marginBottom: "2rem" }}>
                    <p style={{ margin: 0, fontWeight: 700, color: "#334155", fontSize: "1.1rem" }}>{producedQR.quantity_produced}x {producedQR.menu_item_name}</p>
                    <p style={{ margin: "0.25rem 0 0", color: "#64748b", fontSize: "0.9rem", fontWeight: 600 }}>Expires: {producedQR.expiry_date}</p>
                  </div>
                  <button className="kv-btn kv-btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={() => setShowProduceModal(false)}>
                    Close & Continue
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {viewOrderQR && (
          <div className="kv-modal-overlay" style={{ position: "fixed", inset: 0, background: "rgba(15, 23, 42, 0.4)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
            <div className="kv-card" style={{ width: "90%", maxWidth: "400px", position: "relative", padding: "2.5rem", animation: "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)" }}>
              <div style={{ textAlign: "center" }}>
                <h3 style={{ fontSize: "1.5rem", fontWeight: 800, color: "#0f172a", marginBottom: "0.5rem" }}>Order #{viewOrderQR.id}</h3>
                <p style={{ margin: "0 0 1.5rem", color: "#64748b", fontWeight: 600 }}>Scan QR to track or fulfill</p>
                <div style={{ background: "#f8fafc", padding: "1.5rem", borderRadius: "20px", display: "inline-block", marginBottom: "1.5rem", border: "2px dashed #cbd5e1" }}>
                  <img referrerPolicy="no-referrer" src={viewOrderQR.qr_code_base64} alt="Order QR Code" style={{ width: "200px", height: "200px" }} />
                </div>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <button type="button" className="kv-btn" style={{ background: "#e2e8f0", color: "#475569" }} onClick={() => setViewOrderQR(null)}>
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {toast && (
          <div style={{
            position: "fixed", bottom: "2rem", right: "2rem",
            background: toast.type === "error" ? "#ef4444" : "#10b981",
            color: "white", padding: "1rem 2rem", borderRadius: "12px",
            fontWeight: 600, boxShadow: "0 10px 25px -5px rgba(0,0,0,0.2)",
            animation: "slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            zIndex: 9999
          }}>
            {toast.message}
          </div>
        )}
      </div>
    </>
  );
}
