import React, { useState, useEffect, useMemo } from "react";
import './StaffPOS.css';
import { createPortal } from "react-dom";
import EmptyState from './EmptyState';
import { api, API_BASE_URL } from "../utils/api";
import {
  Plus, Minus, IndianRupee, QrCode, ShoppingCart, RefreshCw,
  AlertCircle, CheckCircle, Store, Trash2, FileText,
  Volume2, VolumeX, X, LogOut, User, Clock, ShieldAlert,
  KeyRound, Gift, Search, Package
} from "../ui/Icon";
import QRScanner from "./QRScanner";

export default function StaffPOS({ onLogout, _dbMode }) {
  const [outlet, setOutlet] = useState(null);
  const [menu, setMenu] = useState([]);
  const [activeSale, setActiveSale] = useState({}); // { itemId: quantity }
  const [storeSettings, setStoreSettings] = useState({});
  const [paymentMethod, setPaymentMethod] = useState("cash"); // "cash" or "scanner"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [alertMsg, setAlertMsg] = useState("");

  const [showProfileModal, setShowProfileModal] = useState(false);
  const [profileForm, setProfileForm] = useState({ full_name: "", phone: "", address: "", password: "" });
  const [profileUpdating, setProfileUpdating] = useState(false);

  const openProfileModal = () => {
    const user = api.getCurrentUser();
    if (user) {
      setProfileForm({
        full_name: user?.full_name || "",
        phone: user?.phone || "",
        address: user?.address || "",
        password: ""
      });
      setShowProfileModal(true);
    }
  };

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setProfileUpdating(true);
    try {
      await api.updateProfile(profileForm);
      alert("Profile updated successfully!");
      setShowProfileModal(false);
    } catch (err) {
      setAlertMsg("Failed to update profile: " + err.message);
    } finally {
      setProfileUpdating(false);
    }
  };
  // Coupon states
  const [couponCodeInput, setCouponCodeInput] = useState("");
  const [appliedCoupon, setAppliedCoupon] = useState(null);
  const [couponError, setCouponError] = useState("");
  const [availableCoupons, setAvailableCoupons] = useState([]);

  const displayOutlet = outlet || { name: "Loading Outlet...", address: "", needs_restock: false, current_stock: 0 };
  const displayMenu = menu || [];

  // Shift & POS history states
  const [salesHistory, setSalesHistory] = useState([]);
  const [showShiftReport, setShowShiftReport] = useState(false);
  const [lastCompletedSale, setLastCompletedSale] = useState(null);

  // Disposal states
  const [showDisposalForm, setShowDisposalForm] = useState(false);
  const [showRestockForm, setShowRestockForm] = useState(false);
  const [dispItemId, setDispItemId] = useState("");
  const [restockItemId, setRestockItemId] = useState("");
  const [restockQty, setRestockQty] = useState("50");
  const [dispQty, setDispQty] = useState("1");
  const [dispReason, setDispReason] = useState("damaged");

  // UPI payment state
  const [showUPIScanModal, setShowUPIScanModal] = useState(false);

  // Audio configuration
  const [soundEnabled, setSoundEnabled] = useState(true);

  // ---- NEW: Shift Management ----
  const [activeShift, setActiveShift] = useState(null);
  const [shiftChecked, setShiftChecked] = useState(false); // has the shift check completed?
  const [clockInEmail, setClockInEmail] = useState("");
  const [clockInPin, setClockInPin] = useState("");
  const [clockInLoading, setClockInLoading] = useState(false);
  const [clockInError, setClockInError] = useState("");

  // ---- NEW: Clock-Out ----
  const [showClockOutModal, setShowClockOutModal] = useState(false);
  const [showClockInModal, setShowClockInModal] = useState(false);
  const [actualCashInput, setActualCashInput] = useState("");
  const [clockOutLoading, setClockOutLoading] = useState(false);
  const [clockOutResult, setClockOutResult] = useState(null);

  const [showMyShiftsModal, setShowMyShiftsModal] = useState(false);
  const [myShifts, setMyShifts] = useState([]);
  const [myShiftsLoading, setMyShiftsLoading] = useState(false);

  // ---- NEW: CRM / Loyalty ----



  // ---- NEW: Product Code Scanning ----
  const [productCodeInput, setProductCodeInput] = useState("");
  const [scanError, setScanError] = useState("");
  const [isScanning, setIsScanning] = useState(false);

  // ---- NEW: Checkout Modal ----
  const [showCheckoutModal, setShowCheckoutModal] = useState(false);

  const [toast, setToast] = useState(null);
  const alert = (msg) => {
    setToast({ message: msg, type: msg.toLowerCase().includes("failed") || msg.toLowerCase().includes("error") ? "error" : "success" });
  };

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3500);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // ---- Check active shift on mount ----
  useEffect(() => {
    const checkAndClockIn = async () => {
      try {
        const res = await api.posGetActiveShift();
        if (res.shift) {
          setActiveShift(res.shift);
        } else {
          // Auto clock-in
          const clockInRes = await api.posClockIn("", "");
          setActiveShift(clockInRes.shift);
          alert("Shift started automatically.");
        }
      } catch (err) {
        console.error("Failed to check or start shift", err);
        setActiveShift(null);
      } finally {
        setShiftChecked(true);
      }
    };
    checkAndClockIn();
  }, []);

  // ---- Clock-In Handler (Fallback) ----
  const handleClockIn = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setClockInLoading(true);
    try {
      const res = await api.posClockIn("", "");
      setActiveShift(res.shift);
      alert("Shift started!");
      loadData();
    } catch (err) {
      alert("Clock-in failed: " + err.message);
    } finally {
      setClockInLoading(false);
    }
  };

  // ---- Clock-Out Handler ----
  const handleClockOut = async (e) => {
    e.preventDefault();
    const cashVal = parseFloat(actualCashInput);
    if (isNaN(cashVal) || cashVal < 0) {
      alert("Please enter a valid non-negative cash amount");
      return;
    }
    setClockOutLoading(true);
    try {
      const res = await api.posClockOut(cashVal);
      setClockOutResult({ ...res.shift, stats: shiftTotals });
      setActiveShift(null);
      setActualCashInput("");
      setShowClockOutModal(false);
    } catch (err) {
      alert("Clock-out failed: " + err.message);
    } finally {
      setClockOutLoading(false);
    }
  };

  // ---- CRM Customer Lookup ----


  // ---- Product Code Entry Handler ----
  const handleProductCodeEntry = async (e) => {
    e.preventDefault();
    if (!productCodeInput.trim()) return;
    setScanError("");
    try {
      const product = await api.getFoodByCode(productCodeInput.trim().toLowerCase());
      // Check if product is in this outlet's menu
      const itemInMenu = displayMenu.find(m => m.id === product.id);
      if (!itemInMenu) {
        throw new Error("Item not available in this outlet");
      }
      handleSelectItem(itemInMenu.id);
      setProductCodeInput("");
    } catch (err) {
      setScanError(err.message || "Product code not found");
    }
  };


  // Audio generator function using browser's AudioContext
  const playAlertSound = () => {
    if (!soundEnabled) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime); // high pitch warning beep
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15); // short beep
    } catch (err) {
      console.log("AudioContext blocked or unavailable:", err);
    }
  };

  const loadMyShifts = async () => {
    setMyShiftsLoading(true);
    try {
      const data = await api.posGetMyShifts();
      setMyShifts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load shifts:", err);
      setMyShifts([]);
    } finally {
      setMyShiftsLoading(false);
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError("");

    setAlertMsg("");
    try {
      const staffOutlet = await api.posGetMyOutlet();
      setOutlet(staffOutlet);

      const menuData = await api.getPOSMenu();
      setMenu(menuData);

      try {
        const settings = await api.getPublicStoreSettings();
        setStoreSettings(settings);
      } catch (err) {
        console.warn("Could not load settings:", err);
      }

      try {
        const couponsData = await api.getOutletCoupons();
        setAvailableCoupons(couponsData);
      } catch (err) {
        console.warn("Could not load coupons:", err);
      }
    
      if (showMyShiftsModal) {
        loadMyShifts();
      }

      // Check if any items are critical and trigger sound
      const lowItems = menuData.filter(item => item.current_stock <= item.restock_limit);
      if (lowItems.length > 0) {
        setAlertMsg(`Restock warning: ${lowItems.length} products below safety limits!`);
        playAlertSound();
      }

      // Load sales history
      const res = await fetch(`${API_BASE_URL}/pos/sales/history`, {
        headers: { "Authorization": `Bearer ${api.getAccessToken()}` }
      });
      if (res.ok) {
        const history = await res.json();
        setSalesHistory(history);
      }

    } catch (err) {
      setError(err.message || "Failed to load POS database");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelectItem = (itemId) => {
    const item = displayMenu.find(m => m.id === itemId);
    if (!item) return;
    const currentSelected = activeSale[itemId] || 0;
    if (item.current_stock <= currentSelected) {
      alert(`Cannot add more. Station only has ${item.current_stock} of ${item.name} in stock.`);
      return;
    }
    setActiveSale(prev => ({
      ...prev,
      [itemId]: currentSelected + 1
    }));
  };

  const handleIncrement = (itemId) => {
    const item = displayMenu.find(m => m.id === itemId);
    if (!item) return;
    if (item.current_stock <= (activeSale[itemId] || 0)) {
      alert(`Only ${item.current_stock} available in stock.`);
      return;
    }
    setActiveSale(prev => ({
      ...prev,
      [itemId]: prev[itemId] + 1
    }));
  };

  const handleDecrement = (itemId) => {
    setActiveSale(prev => {
      const next = { ...prev };
      if (next[itemId] <= 1) {
        delete next[itemId];
      } else {
        next[itemId] -= 1;
      }
      return next;
    });
  };

  const getSaleTotalQty = () => Object.values(activeSale).reduce((sum, qty) => sum + qty, 0);

  const getSaleTotalAmount = () => {
    return Object.entries(activeSale).reduce((sum, [id, qty]) => {
      const item = displayMenu.find(m => m.id === parseInt(id));
      return sum + (item ? item.price * qty : 0);
    }, 0);
  };

  const discountAmount = appliedCoupon ? (getSaleTotalAmount() * appliedCoupon.discount_pct / 100) : 0;
  const finalTotalAmount = getSaleTotalAmount() - discountAmount;

  const handleApplyCoupon = async () => {
    if (!couponCodeInput.trim()) return;
    setCouponError("");
    try {
      const coupon = await api.validateCoupon(couponCodeInput.trim());
      setAppliedCoupon(coupon);
      setCouponCodeInput("");
      alert(`Coupon "${coupon.code}" applied! (${coupon.discount_pct}% off)`);
    } catch (err) {
      setCouponError(err.message || "Invalid coupon code");
      setAppliedCoupon(null);
    }
  };

  const handleCompleteSale = async (forceComplete = false) => {
    const totalQty = getSaleTotalQty();
    if (totalQty === 0) return;

    for (const [itemId, qty] of Object.entries(activeSale)) {
      const item = displayMenu.find(m => m.id === parseInt(itemId));
      if (item && item.current_stock < qty) {
        setError(`Insufficient stock for ${item.name}. Available: ${item.current_stock}`);
        return;
      }
    }

    if (paymentMethod === "scanner" && !forceComplete) {
      setShowUPIScanModal(true);
      return;
    }

    setLoading(true);
    setError("");


    const items = Object.entries(activeSale).map(([id, qty]) => ({
      menu_item_id: parseInt(id),
      quantity: qty
    }));

    try {
      const res = await api.posSellWithCRM(
        items,
        paymentMethod,
        appliedCoupon ? appliedCoupon.code : null,
        null,
        0
      );
      alert(`POS Transaction successful! Total: ₹${finalTotalAmount.toFixed(2)}`);
      setActiveSale({});
      setShowUPIScanModal(false);
      
      // Update shift sales locally for instant update
      const newSaleEntry = {
        id: Date.now(),
        created_at: new Date().toISOString(),
        total_amount: finalTotalAmount,
        payment_method: paymentMethod,
        items: items.map(it => {
          const mItem = displayMenu.find(m => m.id === it.menu_item_id);
          return {
            menu_item_name: mItem ? mItem.name : "Item",
            quantity: it.quantity,
            price: mItem ? mItem.price : 0
          };
        })
      };
      setSalesHistory(prev => [newSaleEntry, ...prev]);
      setAppliedCoupon(null);
      setCouponCodeInput("");

      setOutlet(prev => ({
        ...prev,
        current_stock: res.remaining_stock,
        needs_restock: res.restock_alert
      }));

      // Store the last completed sale details
      setLastCompletedSale({
        id: Date.now(),
        created_at: new Date().toISOString(),
        total_amount: getSaleTotalAmount(),
        payment_method: paymentMethod,
        items: items.map(it => {
          const mItem = displayMenu.find(m => m.id === it.menu_item_id);
          return {
            menu_item_name: mItem ? mItem.name : "Item",
            quantity: it.quantity,
            price: mItem ? mItem.price : 0
          };
        })
      });

      if (res.restock_alert) {
        setAlertMsg(`Stock alert: Station requires replenishment!`);
        playAlertSound();
      }

      setTimeout(loadData, 2000);

    } catch (err) {
      setError(err.message || "Failed to submit transaction");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPOSReceipt = (sale) => {
    try {
      const doc = new jsPDF({
        unit: "mm",
        format: [80, 200]
      });

      let yPos = 10;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(14);
      doc.text("FoodPilot ERP", 40, yPos, { align: "center" });
      
      yPos += 6;
      doc.setFontSize(9);
      doc.setFont("helvetica", "normal");
      doc.text(`Outlet: ${outlet ? outlet.name : "Retail Station"}`, 40, yPos, { align: "center" });
      
      yPos += 5;
      doc.text(`Address: ${outlet ? outlet.address : "Location"}`, 40, yPos, { align: "center" });
      
      yPos += 5;
      doc.text("-----------------------------------------", 40, yPos, { align: "center" });
      
      yPos += 6;
      doc.setFont("helvetica", "bold");
      doc.text("POS SALES RECEIPT", 40, yPos, { align: "center" });
      
      yPos += 5;
      doc.setFont("helvetica", "normal");
      doc.text("-----------------------------------------", 40, yPos, { align: "center" });
      
      yPos += 6;
      doc.text(`Receipt ID: #POS-${sale.id}`, 5, yPos);
      
      yPos += 5;
      doc.text(`Date: ${new Date(sale.created_at).toLocaleString()}`, 5, yPos);
      
      yPos += 5;
      doc.text(`Cashier: Alex (Staff)`, 5, yPos);
      
      yPos += 5;
      doc.text(`Payment: ${sale.payment_method.toUpperCase()}`, 5, yPos);
      
      yPos += 5;
      doc.text("-----------------------------------------", 40, yPos, { align: "center" });
      
      yPos += 6;
      doc.setFont("helvetica", "bold");
      doc.text("Items Sold", 5, yPos);
      doc.setFont("helvetica", "normal");
      
      yPos += 5;
      let subtotal = 0;
      sale.items.forEach(it => {
        const itemTotal = (it.price * it.quantity);
        subtotal += itemTotal;
        doc.text(`- ${it.menu_item_name}`, 5, yPos);
        yPos += 4;
        doc.text(`  Qty: ${it.quantity} @ Rs.${parseFloat(it.price).toFixed(2)}`, 5, yPos);
        doc.text(`Rs.${itemTotal.toFixed(2)}`, 75, yPos, { align: "right" });
        yPos += 5;
      });
      
      doc.text("-----------------------------------------", 40, yPos, { align: "center" });
      
      const grandTotal = parseFloat(sale.total_amount);
      if (subtotal > grandTotal && (subtotal - grandTotal) > 0.01) {
          yPos += 5;
          doc.text("Subtotal:", 5, yPos);
          doc.text(`Rs.${subtotal.toFixed(2)}`, 75, yPos, { align: "right" });
          yPos += 5;
          doc.text("Discount applied:", 5, yPos);
          doc.text(`-Rs.${(subtotal - grandTotal).toFixed(2)}`, 75, yPos, { align: "right" });
      }

      yPos += 6;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(11);
      doc.text(`Grand Total:`, 5, yPos);
      doc.text(`Rs.${grandTotal.toFixed(2)}`, 75, yPos, { align: "right" });
      
      yPos += 8;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.text("Thank you for shopping!", 40, yPos, { align: "center" });

      doc.save(`POS_Receipt_${sale.id}.pdf`);
      alert("Receipt PDF downloaded successfully!");
    } catch (err) {
      alert("Failed to download POS receipt: " + err.message);
    }
  };


  const handleLogDisposal = async (e) => {
    e.preventDefault();
    if (!dispItemId) {
      alert("Please select a food item to dispose of");
      return;
    }
    setLoading(true);
    try {
      await api.posLogDisposal(dispItemId, parseInt(dispQty), dispReason);
      alert("Inventory disposal logged successfully!");
      setShowDisposalForm(false);
      setDispQty("1");
      loadData();
    } catch (err) {
      alert("Disposal failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRequestRestock = async (e) => {
    e.preventDefault();
    if (!restockItemId) return;
    setLoading(true);
    try {
      await api.createStockRequest({
        outlet_id: outlet.id,
        menu_item_id: restockItemId,
        quantity: parseInt(restockQty),
        type: "Restock"
      });
      alert("Restock request sent to kitchen!");
      setShowRestockForm(false);
    } catch (err) {
      alert("Request failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const _getStockColor = () => {
    if (!outlet) return "var(--text-muted)";
    if (displayOutlet.needs_restock) return "var(--alert-color)";
    return "var(--success-color)";
  };

  // Compute stats for EOD Report
  const shiftTotals = useMemo(() => {
    const cash = salesHistory.reduce((sum, s) => sum + (s.payment_method === "cash" ? (parseFloat(s.total_amount) || 0) : 0), 0);
    const upi = salesHistory.reduce((sum, s) => sum + (s.payment_method !== "cash" ? (parseFloat(s.total_amount) || 0) : 0), 0);
    const count = salesHistory.length;
    return { cash, upi, total: cash + upi, count };
  }, [salesHistory]);

  const isUnassigned = useMemo(() => {
    return error && (error.toLowerCase().includes("assigned outlet") || error.includes("403"));
  }, [error]);

  return (
    <div className="pos-container">



      {/* ================================================================
          CLOCK-OUT RESULT MODAL (shown after successful clock-out)
      ================================================================ */}
      {clockOutResult && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(13,17,23,0.9)", display: "flex",
          alignItems: "center", justifyContent: "center", zIndex: 9997
        }}>
          <div style={{
            background: "var(--bg-card)", border: "1px solid var(--border-subtle)",
            borderRadius: "1.25rem", padding: "2.5rem", maxWidth: 480, width: "100%", textAlign: "center"
          }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}></div>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.4rem", fontWeight: 800, marginBottom: "1rem" }}>Shift Closed</h2>
            <div className="grid-responsive-2col" style={{ gap: "0.75rem", marginBottom: "1.5rem" }}>
              {[
                ["Duration", `${clockOutResult.duration_hours ?? "—"} hrs`],
                ["Expected Cash", `₹${(clockOutResult.expected_cash ?? 0).toFixed(2)}`],
                ["Actual Cash", `₹${(clockOutResult.actual_cash ?? 0).toFixed(2)}`],
                ["Discrepancy", `₹${(clockOutResult.cash_discrepancy ?? 0).toFixed(2)}`,
                  (clockOutResult.cash_discrepancy ?? 0) < 0 ? "#ef4444" :
                  (clockOutResult.cash_discrepancy ?? 0) > 0 ? "#22c55e" : "var(--text-primary)"]
              ].map(([label, val, color]) => (
                <div key={label} style={{ background: "var(--bg-hover)", borderRadius: "0.75rem", padding: "0.875rem" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.06em", marginBottom: "0.25rem" }}>{label}</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 800, color: color || "var(--text-primary)" }}>{val}</div>
                </div>
              ))}
            </div>
            {(clockOutResult.cash_discrepancy ?? 0) < 0 && (
              <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
                Cash is short by ₹{Math.abs(clockOutResult.cash_discrepancy).toFixed(2)}. Please investigate.
              </div>
            )}
            
            {clockOutResult.stats && (
              <div style={{ background: "var(--bg-inset)", padding: "1.25rem", borderRadius: "1rem", marginBottom: "1.5rem", border: "1px solid var(--border-subtle)", textAlign: "left" }}>
                <h4 style={{ margin: "0 0 1rem 0", fontSize: "0.9rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>End of Day Summary</h4>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                  <span>Ticket Count:</span>
                  <strong>{clockOutResult.stats.count}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                  <span>Cash Sales:</span>
                  <strong>₹{clockOutResult.stats.cash.toFixed(2)}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", fontSize: "0.85rem" }}>
                  <span>UPI/Card Sales:</span>
                  <strong>₹{clockOutResult.stats.upi.toFixed(2)}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", paddingTop: "0.75rem", borderTop: "1px dashed var(--border-subtle)", fontSize: "1rem", fontWeight: "800", color: "var(--brand)" }}>
                  <span>Total Sales:</span>
                  <span>₹{clockOutResult.stats.total.toFixed(2)}</span>
                </div>
              </div>
            )}

            <button
              id="clock-out-done-btn"
              className="btn btn-primary"
              style={{ width: "100%", padding: "0.875rem", marginBottom: "0.75rem" }}
              onClick={() => { setClockOutResult(null); onLogout(); }}
            >
              Done & Sign Out
            </button>
          </div>
        </div>
      )}

      {/* ================================================================
          CLOCK-OUT MODAL
      ================================================================ */}
      {showClockOutModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(13,17,23,0.85)", display: "flex",
          alignItems: "center", justifyContent: "center", zIndex: 9996
        }}>
          <div style={{
            background: "var(--bg-card)", border: "1px solid var(--border-subtle)",
            borderRadius: "1.25rem", padding: "2rem", maxWidth: 420, width: "100%"
          }}>
            <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>Clock Out</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
              Enter the actual cash amount counted in the drawer to close your shift.
            </p>
            <form onSubmit={handleClockOut} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Actual Cash in Drawer (₹)</label>
                <input
                  id="clock-out-cash-input"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  className="form-input"
                  placeholder="0.00"
                  value={actualCashInput}
                  onChange={e => setActualCashInput(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="pos-header-actions">
                <button
                  id="clock-out-submit-btn"
                  type="submit"
                  disabled={clockOutLoading}
                  className="btn btn-primary"
                  style={{ flex: 1, padding: "0.8rem" }}
                >
                  {clockOutLoading ? "Closing Shift…" : "Confirm Clock Out"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "0.8rem 1rem" }}
                  onClick={() => setShowClockOutModal(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


      <div style={{ display: "flex", height: "100%", width: "100%", overflow: "hidden", background: "var(--pos-bg)" }}>
        {/* Sidebar */}
        <div style={{ width: "240px", background: "var(--pos-surface)", borderRight: "1px solid var(--pos-border)", display: "flex", flexDirection: "column", padding: "1.5rem" }}>
          <div style={{ marginBottom: "2rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div style={{ width: 36, height: 36, background: "var(--brand-dim)", borderRadius: "var(--r-md)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--brand)" }}>
              <Store size={18} />
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: "1.1rem", color: "var(--text-primary)" }}>Cashier</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{displayOutlet.name}</div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", flex: 1 }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--text-muted)", marginBottom: "0.5rem", letterSpacing: "0.05em" }}>Shift</div>
            

            <button onClick={() => setShowShiftReport(true)} className="sidebar-btn"><FileText size={16} /> Shift Report</button>
            <button onClick={() => { setShowMyShiftsModal(true); loadMyShifts(); }} className="sidebar-btn"><FileText size={16} /> My Shifts</button>

            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--text-muted)", marginBottom: "0.5rem", marginTop: "1rem", letterSpacing: "0.05em" }}>Inventory</div>
            <button onClick={() => { if (displayMenu.length > 0 && !restockItemId) setRestockItemId(displayMenu[0].id.toString()); setShowRestockForm(true); }} className="sidebar-btn">
              <Package size={16} /> Request Restock
            </button>
            <button onClick={() => { if (displayMenu.length > 0 && !dispItemId) setDispItemId(displayMenu[0].id.toString()); setShowDisposalForm(true); }} className="sidebar-btn">
              <Trash2 size={16} /> Log Damage
            </button>
          </div>


        </div>

        {/* Main Content Area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1.5rem", gap: "1rem", overflow: "hidden" }}>
          <div className="pos-header" style={{ marginBottom: 0, border: "none", boxShadow: "none", background: "transparent", padding: 0 }}>
            <div style={{ display: "flex", gap: "2rem" }}>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700 }}>Total Inventory</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: displayOutlet.needs_restock ? "var(--error)" : "var(--success)" }}>{displayOutlet.current_stock}</div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700 }}>Low Stock Alerts</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: alertMsg ? "var(--error)" : "var(--success)" }}>
                  {displayMenu.filter(i => i.current_stock <= i.restock_limit).length}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              {activeShift && (
                <div style={{ background: "rgba(34, 197, 94, 0.1)", color: "#22c55e", padding: "0.5rem 1rem", borderRadius: "99px", fontWeight: 700, fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ width: 8, height: 8, background: "#22c55e", borderRadius: "50%", display: "inline-block" }}></span>
                  Shift Active
                </div>
              )}
              <div className="pos-header-actions">
                <button onClick={() => setSoundEnabled(!soundEnabled)} title={soundEnabled ? "Mute alerts" : "Enable alerts"}>
                  {soundEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />} <span>{soundEnabled ? "Sound On" : "Muted"}</span>
                </button>
                <button onClick={openProfileModal}><User size={14} /> <span>Profile</span></button>
                <button onClick={() => { if (activeShift) { setShowClockOutModal(true); } else { onLogout(); } }}><LogOut size={14} /> <span>Sign Out</span></button>
                <button onClick={loadData} className="btn-icon" title="Refresh Database" style={{ padding: "0.5rem" }}><RefreshCw size={14} /></button>
              </div>
            </div>
          </div>

          {error && !isUnassigned && (
            <div className="alert alert-error" style={{ marginBottom: "0.5rem" }}>
              <AlertCircle size={15} /> {error}
            </div>
          )}

          {false ? (
            <div style={{ textAlign: "center", padding: "4rem 2rem", maxWidth: "500px", margin: "3rem auto" }} className="panel animate-fade-in">
              <div style={{ width: 64, height: 64, background: "rgba(239, 68, 68, 0.1)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--error)", margin: "0 auto 1.5rem" }}>
                <AlertCircle size={32} />
              </div>
              <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "1.25rem", fontWeight: 800, color: "var(--text-primary)", marginBottom: "0.75rem" }}>
                Unassigned Outlet
              </h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", lineHeight: 1.5, marginBottom: "1.5rem" }}>
                Your staff account is currently not assigned to any supply outlet. An administrator must assign your account to an active outlet in the Admin View before you can launch the cashier terminal.
              </p>
              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
                <button onClick={loadData} className="btn btn-primary" style={{ padding: "0.6rem 1.25rem" }}>
                  <RefreshCw size={14} /> Retry Sync
                </button>
                <button onClick={onLogout} className="btn btn-secondary" style={{ padding: "0.6rem 1.25rem" }}>
                  <LogOut size={14} /> Sign Out
                </button>
              </div>
            </div>
          ) : false ? (
            <div style={{ textAlign: "center", padding: "4rem 0", color: "var(--text-muted)" }}>
              <RefreshCw size={26} className="animate-spin" style={{ marginBottom: "0.5rem" }} />
              <div style={{ fontSize: "0.85rem" }}>Syncing with outlet database...</div>
            </div>
          ) : true ? (
            <>
              <div className="pos-grid" style={{ height: "100%", gridTemplateColumns: "1fr 340px" }}>
                
                {/* ── REGISTER CATALOG ITEMS ── */}
                <div className="panel" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", height: "100%" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                    <div>
                      <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>Products</h2>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <form onSubmit={handleProductCodeEntry} style={{ display: "flex", gap: "0.5rem" }}>
                        <input
                          type="text"
                          className="form-input"
                          placeholder="Enter Code (e.g. som1)"
                          value={productCodeInput}
                          onChange={e => setProductCodeInput(e.target.value)}
                          style={{ width: "160px", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
                        />
                        <button type="submit" className="btn btn-secondary" style={{ padding: "0.4rem 0.6rem", fontSize: "0.8rem" }}>Add</button>
                      </form>
                      <button onClick={() => setIsScanning(!isScanning)} className="btn-icon" title="Scan Barcode">
                        <QrCode size={14} />
                      </button>
                    </div>
                  </div>

                  {isScanning && (
                    <div style={{ marginBottom: "1rem" }}>
                      <QRScanner onStockUpdated={async (code) => { 
                        setIsScanning(false);
                        if (code) {
                          try {
                            const product = await api.getFoodByCode(code.trim().toLowerCase());
                            const itemInMenu = displayMenu.find(m => m.id === product.id);
                            if (!itemInMenu) throw new Error("Item not available in this outlet");
                            handleSelectItem(itemInMenu.id);
                          } catch (err) {
                            setScanError(err.message || "Product code not found");
                          }
                        }
                      }} />
                    </div>
                  )}
                  {scanError && <p style={{ color: "var(--error)", fontSize: "0.75rem", marginBottom: "1rem", marginTop: "-0.5rem" }}>{scanError}</p>}

                  {/* Grid of items */}
                  <div className="pos-items-grid" style={{ overflowY: "auto", flex: 1, paddingRight: "0.5rem", marginTop: "2rem" }}>
                    {displayMenu.map(item => {
                      const isLow = item.current_stock <= item.restock_limit;
                      const inSale = activeSale[item.id] || 0;
                      return (
                        <button
                          key={item.id}
                          onClick={() => handleSelectItem(item.id)}
                          className={`pos-item-card ${inSale > 0 ? "selected" : ""} ${isLow ? "low-stock" : ""}`}
                          style={{ cursor: "pointer", fontFamily: "var(--font-body)", padding: "1rem" }}
                        >
                          {isLow && (
                            <div style={{ position: "absolute", top: 8, right: 8, width: 8, height: 8, borderRadius: "50%", background: "var(--error)" }} />
                          )}
                          {inSale > 0 && (
                            <div style={{ position: "absolute", top: 6, left: 6, width: 20, height: 20, borderRadius: "50%", background: "var(--brand)", color: "#fff", fontSize: "0.68rem", fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>{inSale}</div>
                          )}
                          <h4 style={{ fontSize: "0.85rem", fontWeight: 700, margin: "0.5rem 0", color: "var(--text-primary)", lineHeight: 1.3 }}>{item.name}</h4>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", marginTop: "auto" }}>
                            <span style={{ fontFamily: "var(--font-heading)", fontSize: "1.1rem", fontWeight: 800, color: "var(--brand)" }}>₹{item.price.toFixed(0)}</span>
                            <span style={{ fontSize: "0.7rem", fontWeight: 800, color: isLow ? "var(--error)" : "var(--success)", background: isLow ? "var(--error-bg)" : "var(--success-bg)", padding: "2px 6px", borderRadius: "var(--r-full)" }}>
                              {item.current_stock} left
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* ── POS TICKET & TOOLS ── */}
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", height: "100%", overflow: "hidden", minHeight: 0 }}>



                  {/* Ticket */}
                  <div className="pos-ticket" style={{ border: "none", boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)" }}>
                    <div className="pos-ticket-header" style={{ padding: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <ShoppingCart size={16} style={{ color: "var(--brand)" }} />
                        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "1rem", fontWeight: 700, margin: 0 }}>Current Ticket</h3>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        {Object.keys(activeSale).length > 0 && (
                          <button className="btn-icon" onClick={() => setActiveSale({})} title="Clear ticket">
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="pos-ticket-items" style={{ padding: "1rem" }}>

                      {lastCompletedSale && (
                        <div className="alert alert-success animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", alignItems: "flex-start", width: "100%", marginBottom: "1rem" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            <CheckCircle size={14} /> <span>Transaction successful!</span>
                          </div>
                          <button
                            onClick={() => handleDownloadPOSReceipt(lastCompletedSale)}
                            className="btn"
                            style={{
                              padding: "0.3rem 0.6rem", fontSize: "0.72rem",
                              background: "#fff", color: "var(--success)",
                              border: "1px solid var(--success)", borderRadius: "var(--r-sm)",
                              cursor: "pointer", fontWeight: 700, alignSelf: "flex-end",
                              display: "flex", alignItems: "center", gap: "0.25rem"
                            }}
                          >
                            <FileText size={12} /> Download Receipt
                          </button>
                        </div>
                      )}
                      {alertMsg && (
                        <div className="alert alert-warning animate-fade-in" style={{ marginBottom: "1rem" }}>{alertMsg}</div>
                      )}

                      {Object.keys(activeSale).length === 0 ? (
                        <div style={{ padding: "3rem 1rem", textAlign: "center", color: "var(--text-muted)", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.75rem" }}>
                          <ShoppingCart size={32} style={{ opacity: 0.5 }} />
                          <p style={{ margin: 0, fontSize: "0.9rem" }}>Tap items on the left to add them to the ticket</p>
                        </div>
                      ) : (
                        Object.entries(activeSale).map(([id, qty]) => {
                          const item = displayMenu.find(m => m.id === parseInt(id));
                          if (!item) return null;
                          return (
                            <div key={id} className="pos-cart-item">
                              <span style={{ fontSize: "0.85rem", fontWeight: 700, flex: 1, marginRight: "0.5rem" }}>{item.name}</span>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <div className="pos-qty-controls">
                                  <button onClick={() => handleDecrement(item.id)}><Minus size={11} /></button>
                                  <span>{qty}</span>
                                  <button onClick={() => handleIncrement(item.id)}><Plus size={11} /></button>
                                </div>
                                <span style={{ fontFamily: "var(--font-heading)", fontSize: "0.95rem", fontWeight: 800, color: "var(--brand)", width: 44, textAlign: "right" }}>₹{(item.price * qty).toFixed(0)}</span>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>

                    <div className="pos-ticket-footer" style={{ padding: "1.25rem" }}>
                      {/* Totals */}
                      <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "0.875rem", marginBottom: "1rem" }}>
                        <div className="pos-summary-row">
                          <span>Items</span><span style={{ fontWeight: 600 }}>{getSaleTotalQty()} units</span>
                        </div>
                        {appliedCoupon && (
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", color: "var(--success)", marginBottom: "0.35rem", fontWeight: "600" }}>
                            <span>Discount ({appliedCoupon.code})</span><span>-₹{discountAmount.toFixed(0)}</span>
                          </div>
                        )}
                        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-heading)", fontSize: "1.4rem", fontWeight: 800, marginTop: "0.5rem" }}>
                          <span>Total</span>
                          <span style={{ color: "var(--brand)" }}>₹{finalTotalAmount.toFixed(0)}</span>
                        </div>
                      </div>

                      <button onClick={() => {
                        if (!activeShift) {
                          alert("Please clock in to start taking orders.");
                          return;
                        }
                        setShowCheckoutModal(true);
                      }} disabled={getSaleTotalQty() === 0 || loading} className={`pos-checkout-btn `}>
                        {loading ? "Processing…" : `Checkout · ₹${finalTotalAmount.toFixed(0)}`}
                      </button>
                    </div>
                  </div>

                </div>{/* end right panel */}

              </div>{/* end pos-grid */}

            </>
          ) : (
            !loading && (
              <div style={{ textAlign: "center", padding: "4rem", color: "var(--text-muted)" }}>
                <AlertCircle size={32} style={{ color: "var(--alert-color)", marginBottom: "1rem" }} />
                <h4>Terminal Offline</h4>
              </div>
            )
          )}
        </div>
      </div>

      {/* SHIFT REPORT MODAL */}
      {showShiftReport && (
        <div className="modal-overlay" onClick={() => setShowShiftReport(false)}>
          <div className="modal-box" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Store size={18} style={{ color: "var(--brand)" }} /> Shift Report
              </h2>
              <button className="modal-close" onClick={() => setShowShiftReport(false)}><X size={16} /></button>
            </div>
            <div style={{ textAlign: "center", marginBottom: "1.25rem", color: "var(--text-secondary)", fontSize: "0.8rem" }}>Outlet: <strong style={{ color: "var(--text-primary)" }}>{displayOutlet.name}</strong></div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem", marginBottom: "1.5rem" }}>
              {[
                { label: "Total Ticket Sales", value: `${shiftTotals.count} receipts` },
                { label: "Cash Receipts", value: `₹${shiftTotals.cash.toFixed(0)}` },
                { label: "UPI/Scanner", value: `₹${shiftTotals.upi.toFixed(0)}` },
              ].map(r => (
                <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem", padding: "0.6rem 0.875rem", background: "var(--bg-elevated)", borderRadius: "var(--r-md)" }}>
                  <span style={{ color: "var(--text-secondary)" }}>{r.label}</span>
                  <strong>{r.value}</strong>
                </div>
              ))}
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "1.1rem", fontWeight: 800, padding: "0.75rem 0.875rem", background: "var(--brand-dim)", borderRadius: "var(--r-md)", border: "1px solid var(--border-brand)" }}>
                <span style={{ color: "var(--brand)" }}>Total Drawer</span>
                <span style={{ color: "var(--brand)" }}>₹{shiftTotals.total.toFixed(0)}</span>
              </div>
            </div>
            <button onClick={() => { setShowShiftReport(false); alert("Shift summary printed!"); }} className="btn btn-primary" style={{ width: "100%", padding: "0.875rem" }}>
              Print Summary
            </button>
          </div>
        </div>
      )}
      {/* MY SHIFTS MODAL */}
      {showMyShiftsModal && (
        <div className="modal-overlay" onClick={() => setShowMyShiftsModal(false)}>
          <div className="modal-box" style={{ maxWidth: 600, width: "95%", maxHeight: "80vh", overflowY: "auto" }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Clock size={18} style={{ color: "var(--brand)" }} /> My Past Shifts
              </h2>
              <button className="modal-close" onClick={() => setShowMyShiftsModal(false)}><X size={16} /></button>
            </div>
            {myShiftsLoading ? (
              <div style={{ textAlign: "center", padding: "4rem 2rem" }}>
                <RefreshCw className="animate-spin" size={32} style={{ color: "var(--brand)", margin: "0 auto" }} />
              </div>
            ) : myShifts.length === 0 ? (
              <EmptyState icon={Clock} message="No shift history found." />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {myShifts.map(s => (
                  <div key={s.id} style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--r-md)", padding: "1rem", background: "var(--bg-secondary)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontWeight: 800 }}>{new Date(s.clock_in_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 700, padding: "0.2rem 0.5rem", borderRadius: "10px", background: s.status === "active" ? "rgba(34, 197, 94, 0.1)" : "rgba(0,0,0,0.05)", color: s.status === "active" ? "#22c55e" : "var(--text-secondary)" }}>{s.status.toUpperCase()}</span>
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                      <strong>Clock Out:</strong> {s.clock_out_time ? new Date(s.clock_out_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : "Ongoing"}<br/>
                      <strong>Discrepancy:</strong> <span style={{ color: s.cash_discrepancy < 0 ? "var(--error)" : s.cash_discrepancy > 0 ? "var(--success)" : "inherit" }}>
                        {s.cash_discrepancy !== null ? (s.cash_discrepancy > 0 ? "+" : "") + "₹" + s.cash_discrepancy : "N/A"}
                      </span>
                    </div>
                    {s.sales_summary && s.sales_summary.length > 0 && (
                      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", borderTop: "1px solid var(--border-light)", paddingTop: "0.5rem" }}>
                        <strong style={{ color: "var(--text-primary)" }}>Sales Summary:</strong>
                        <ul style={{ paddingLeft: "1.2rem", margin: "0.3rem 0 0", color: "var(--text-secondary)" }}>
                          {s.sales_summary.map((ss, idx) => (
                            <li key={idx}>{ss.total_qty}x {ss.item_name} (₹{ss.total_revenue})</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* DISPOSAL MODAL */}
      {showDisposalForm && (
        <div className="modal-overlay" onClick={() => setShowDisposalForm(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--error)" }}>
                <Trash2 size={18} /> Log Spoilage
              </h2>
              <button className="modal-close" onClick={() => setShowDisposalForm(false)}><X size={16} /></button>
            </div>
            <form onSubmit={handleLogDisposal} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Damaged Item</label>
                <select className="form-select" value={dispItemId} onChange={e => setDispItemId(e.target.value)} required>
                  {displayMenu.map(i => <option key={i.id} value={i.id}>{i.name} (Stock: {i.current_stock})</option>)}
                </select>
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Write-off Quantity</label>
                <input type="number" className="form-input" value={dispQty} onChange={e => setDispQty(e.target.value)} min="1" required />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Reason</label>
                <select className="form-select" value={dispReason} onChange={e => setDispReason(e.target.value)}>
                  <option value="damaged">Damaged in Transit / Storage</option>
                  <option value="expired">Approaching Shelf Expiry</option>
                  <option value="spoiled">Spillage / Bag Leakage</option>
                  <option value="returned">Customer Return/Refund</option>
                </select>
              </div>
              <button type="submit" disabled={loading} className="btn btn-danger" style={{ width: "100%", padding: "0.875rem" }}>
                <Trash2 size={15} /> Confirm Disposal
              </button>
            </form>
          </div>
        </div>
      )}

      {showRestockForm && (
        <div className="modal-overlay" onClick={() => setShowRestockForm(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">
                <Package size={20} style={{ color: "var(--brand)" }} />
                Request Kitchen Restock
              </h2>
              <button className="modal-close" onClick={() => setShowRestockForm(false)}><X size={16} /></button>
            </div>
            <form onSubmit={handleRequestRestock} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Menu Item</label>
                <select className="form-select" value={restockItemId} onChange={e => setRestockItemId(e.target.value)} required>
                  {displayMenu.map(i => <option key={i.id} value={i.id}>{i.name} (Stock: {i.current_stock})</option>)}
                </select>
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Quantity</label>
                <input type="number" min="1" className="form-input" value={restockQty} onChange={e => setRestockQty(e.target.value)} required />
              </div>
              <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setShowRestockForm(false)}>Cancel</button>
                <button type="submit" disabled={loading} className="btn btn-primary" style={{ flex: 2, background: "var(--brand)", color: "white" }}>
                  {loading ? "Sending..." : "Send Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CHECKOUT MODAL */}
      {showCheckoutModal && (
        <div className="modal-overlay" onClick={() => setShowCheckoutModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 450 }}>
            <div className="modal-header">
              <h2 className="modal-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <ShoppingCart size={18} style={{ color: "var(--brand)" }} /> Checkout
              </h2>
              <button className="modal-close" onClick={() => setShowCheckoutModal(false)}><X size={16} /></button>
            </div>
            
            {/* Payment Method */}
            <div style={{ marginBottom: "1.5rem" }}>
              <span className="pos-section-label">Payment Method</span>
              <div className="pos-pill-group">
                <button type="button" onClick={() => setPaymentMethod("cash")} className={`pos-pill ${paymentMethod === "cash" ? "active" : ""}`} style={{ flex: 1, justifyContent: "center", padding: "0.75rem" }}>
                  <IndianRupee size={15} /> Cash
                </button>
                <button type="button" onClick={() => setPaymentMethod("scanner")} className={`pos-pill ${paymentMethod === "scanner" ? "active" : ""}`} style={{ flex: 1, justifyContent: "center", padding: "0.75rem" }}>
                  <QrCode size={15} /> UPI
                </button>
              </div>
            </div>

            {/* Discount Coupon */}
            <div style={{ marginBottom: "1.5rem" }}>
              <span className="pos-section-label">Discount Coupon</span>
              <div className="pos-input-group">
                <input
                  type="text"
                  className="form-input"
                  placeholder="Enter code (e.g. WELCOME10)"
                  style={{ fontSize: "0.9rem", padding: "0.5rem 0.75rem", textTransform: "uppercase", height: "auto" }}
                  value={couponCodeInput}
                  onChange={e => setCouponCodeInput(e.target.value)}
                />
                <button id="apply-coupon-btn" type="button" onClick={handleApplyCoupon} className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.9rem", height: "auto" }}>
                  Apply
                </button>
              </div>
              {availableCoupons && availableCoupons.length > 0 && (
                <div className="pos-pill-group" style={{ marginTop: "0.75rem" }}>
                  {availableCoupons.map(c => (
                    <button
                      key={c.id}
                      type="button"
                      className="pos-pill coupon-pill"
                      onClick={() => {
                        setCouponCodeInput(c.code);
                        setTimeout(() => document.getElementById('apply-coupon-btn')?.click(), 50);
                      }}
                    >
                      {c.code}
                    </button>
                  ))}
                </div>
              )}
              {couponError && (
                <div style={{ fontSize: "0.8rem", color: "var(--error)", marginTop: "0.4rem", fontWeight: "600" }}>
                  {couponError}
                </div>
              )}
              {appliedCoupon && (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)", borderRadius: "6px", padding: "0.5rem 0.75rem", marginTop: "0.5rem" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--success)", fontWeight: "700" }}>
                    Applied "{appliedCoupon.code}" ({appliedCoupon.discount_pct}% Off)
                  </span>
                  <button
                    type="button"
                    onClick={() => setAppliedCoupon(null)}
                    style={{ background: "none", border: "none", color: "var(--error)", fontSize: "0.8rem", cursor: "pointer", fontWeight: "700" }}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
            
            {/* Order Total summary */}
            <div style={{ background: "var(--bg-elevated)", padding: "1rem", borderRadius: "var(--r-md)", marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                <span>Subtotal ({getSaleTotalQty()} items)</span>
                <span>₹{getSaleTotalAmount().toFixed(0)}</span>
              </div>
              {appliedCoupon && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem", fontSize: "0.9rem", color: "var(--success)", fontWeight: 700 }}>
                  <span>Discount</span>
                  <span>-₹{discountAmount.toFixed(0)}</span>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.5rem", paddingTop: "0.5rem", borderTop: "1px dashed var(--border-subtle)", fontSize: "1.2rem", fontWeight: 800 }}>
                <span>Final Total</span>
                <span style={{ color: "var(--brand)" }}>₹{finalTotalAmount.toFixed(0)}</span>
              </div>
            </div>

            <button 
              onClick={() => {
                setShowCheckoutModal(false);
                handleCompleteSale();
              }} 
              disabled={loading} 
              className={`pos-checkout-btn `}
              style={{ width: "100%", padding: "1rem", fontSize: "1.1rem" }}
            >
              {loading ? "Processing…" : `Confirm & Pay ₹${finalTotalAmount.toFixed(0)}`}
            </button>
          </div>
        </div>
      )}

      {showUPIScanModal && (
        <div className="modal-overlay" style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(13, 17, 23, 0.95)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 1000
        }}>
          <div className="modal-content animate-fade-in" style={{
            background: "rgba(18, 22, 28, 0.95)", border: "1px solid rgba(249, 115, 22, 0.2)",
            boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)", borderRadius: "var(--r-lg)",
            padding: "2rem", width: "100%", maxWidth: "420px", textAlign: "center"
          }}>
            <h3 style={{ fontFamily: "var(--font-heading)", color: "var(--text-primary)", fontSize: "1.25rem", marginBottom: "0.5rem", fontWeight: 700, display: "flex", gap: "0.5rem", alignItems: "center", justifyContent: "center" }}>
              <QrCode size={20} style={{ color: "var(--brand)" }} /> Scan to Pay
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginBottom: "1.25rem", lineHeight: 1.4 }}>
              Ask the customer to scan the QR code using any UPI application (GPay, PhonePe, Paytm, BHIM) to pay the bill.
            </p>

            <div style={{
              background: "#fff", padding: "1rem", borderRadius: "12px",
              display: "inline-block", marginBottom: "1.25rem", boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
            }}>
              <img
                src={`https://chart.googleapis.com/chart?cht=qr&chs=220x220&chl=${encodeURIComponent(
                  `upi://pay?pa=FoodPilot@icici&pn=FoodPilot%20Kitchen%20ERP&am=${getSaleTotalAmount().toFixed(2)}&cu=INR`
                )}`}
                alt="UPI QR Code"
                style={{ display: "block", width: "220px", height: "220px" }}
              />
            </div>

            <div style={{
              fontSize: "1.4rem", fontWeight: 800, color: "var(--brand)",
              marginBottom: "1.5rem", fontFamily: "var(--font-heading)"
            }}>
              ₹{getSaleTotalAmount().toFixed(2)}
            </div>

            <div className="pos-header-actions">
              <button
                type="button"
                onClick={() => setShowUPIScanModal(false)}
                className="btn btn-secondary"
                style={{ flex: 1, padding: "0.75rem" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleCompleteSale(true)}
                className="btn btn-primary"
                style={{ flex: 1, padding: "0.75rem" }}
                disabled={loading}
              >
                {loading ? "Completing..." : "Confirm Payment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showProfileModal && createPortal(
        <div className="modal-overlay" onClick={() => setShowProfileModal(false)}>
          <div className="modal-box" style={{ maxWidth: 450 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">My Profile</h2>
              <button className="modal-close" onClick={() => setShowProfileModal(false)}><X size={16} /></button>
            </div>
            <form onSubmit={handleUpdateProfile} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Full Name</label>
                <input type="text" className="form-input" value={profileForm.full_name} onChange={e => setProfileForm({ ...profileForm, full_name: e.target.value })} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Phone Number</label>
                <input type="tel" maxLength={10} className="form-input" pattern="\d{10}" placeholder="9876543210" value={profileForm.phone} onChange={e => { const val = e.target.value.replace(/\D/g, ''); if (val.length <= 10) setProfileForm({ ...profileForm, phone: val }); }} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">New Password</label>
                <input type="password" minLength={8} className="form-input" value={profileForm.password || ""} onChange={e => setProfileForm({ ...profileForm, password: e.target.value })} placeholder="Leave blank to keep current password" />
                <small style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "4px", display: "block" }}>Must be at least 8 characters with letters and numbers.</small>
              </div>
              <button type="submit" disabled={profileUpdating} className="btn btn-primary" style={{ marginTop: "0.5rem" }}>
                {profileUpdating ? "Saving..." : "Save Changes"}
              </button>
            </form>
          </div>
        </div>,
        document.body
      )}

      {toast && (
        <div style={{
          position: "fixed", bottom: "2rem", right: "2rem",
          background: toast.type === "success" ? "rgba(16,185,129,0.95)" : "var(--brand-dark)",
          border: `1px solid ${toast.type === "success" ? "rgba(52,211,153,0.3)" : "var(--brand-glow)"}`,
          color: "#fff", padding: "0.85rem 1.5rem", borderRadius: "12px",
          boxShadow: "0 10px 25px -5px rgba(0,0,0,0.3)", zIndex: 99999,
          fontWeight: 600, fontSize: "0.88rem", display: "flex",
          alignItems: "center", gap: "0.6rem"
        }}>
          <span style={{ fontSize: "1.1rem" }}>{toast.type === "success" ? "" : ""}</span>
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)} style={{ background: "transparent", border: "none", color: "#fff", cursor: "pointer", marginLeft: "1rem", opacity: 0.8, fontSize: "0.8rem", display: "flex", alignItems: "center" }}><X size={14} /></button>
        </div>
      )}

    </div>
  );
}
