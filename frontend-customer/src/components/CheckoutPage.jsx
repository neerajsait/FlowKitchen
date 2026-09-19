import React, { useState } from "react";
import { MapPin, Banknote, Plus, Check, Wallet } from "../ui/Icon";

export default function CheckoutPage({
  currentUser,
  cart, menu, addresses, selectedAddressId, setSelectedAddressId,
  checkoutAddress, setCheckoutAddress,
  newAddrVal, setNewAddrVal, newAddrLabel, setNewAddrLabel,
  showAddressManager, setShowAddressManager,
  onAddAddress, onDeleteAddress,
  paymentMethod, setPaymentMethod,
  appliedCoupon, onRemoveCoupon, couponCodeInput, setCouponCodeInput, onApplyCoupon, couponError, activeCoupons,
  useLoyaltyPoints, setUseLoyaltyPoints, loyaltyPoints, maxLoyaltyDiscount,
  finalSubtotal, deliveryCharge, finalTotal, discountAmount, actualLoyaltyDiscount,
  paymentProcessing, onPlaceOrder, storeSettings, checkoutBanners,
  guestName, setGuestName, guestEmail, setGuestEmail, guestPhone, setGuestPhone
}) {
  const [step, setStep] = useState(1); // 1: address, 2: payment, 3: review
  const [privacyAccepted, setPrivacyAccepted] = useState(false);

  const cartItems = Object.entries(cart)
    .map(([id, qty]) => {
      const item = menu.find(m => m.id === parseInt(id));
      return item ? { ...item, qty } : null;
    })
    .filter(Boolean);

  const cartTotal = cartItems.reduce((s, i) => s + i.price * i.qty, 0);

  const PAYMENT_OPTIONS = [
    { id: "COD",    icon: <Banknote size={22} />, label: "Cash on Delivery", desc: "Pay when your order arrives" },
    { id: "ONLINE", icon: <Wallet size={22} />,   label: "Pay Online",       desc: "UPI / Cards / NetBanking — secured by Razorpay" },
  ];

  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.5rem", fontWeight: 900, marginBottom: "1.5rem", color: "var(--text)" }}>Checkout</h1>

      {/* Steps */}
      <div className="checkout-steps" style={{ marginBottom: "2rem" }}>
        {[["Delivery", 1], ["Payment", 2], ["Review", 3]].map(([label, s], idx) => (
          <React.Fragment key={s}>
            <div className={`checkout-step${step === s ? " active" : ""}${step > s ? " done" : ""}`}>
              <div className="checkout-step-num">
                {step > s ? <Check size={13} /> : s}
              </div>
              <span className="checkout-step-label">{label}</span>
            </div>
            {idx < 2 && <div className={`checkout-step-line${step > s ? " done" : ""}`} />}
          </React.Fragment>
        ))}
      </div>

      <div className="cart-layout" style={{ alignItems: "start" }}>
        {/* Left: step content */}
        <div>
          {/* Step 1: Address */}
          {step === 1 && (
            <div className="card card-padded animate-fade-in">
              <h2 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <MapPin size={18} color="var(--green)" /> {currentUser ? "Delivery Address" : "Contact & Delivery Info"}
              </h2>

              {!currentUser && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1.5rem" }}>
                  <div className="form-group">
                    <label className="form-label">Full Name</label>
                    <input className="form-input" placeholder="Enter your name" value={guestName} onChange={e => setGuestName(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email</label>
                    <input className="form-input" type="email" placeholder="Enter your email" value={guestEmail} onChange={e => setGuestEmail(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Phone</label>
                    <input className="form-input" type="tel" placeholder="Enter your phone number" value={guestPhone} onChange={e => setGuestPhone(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Delivery Address</label>
                    <textarea className="form-input" placeholder="Enter full delivery address…" value={checkoutAddress} onChange={e => setCheckoutAddress(e.target.value)} rows={3} required />
                  </div>
                </div>
              )}

              {currentUser && (
                <>
                  {/* Existing addresses */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem", marginBottom: "1.25rem" }}>
                    {addresses.map(addr => (
                      <div
                        key={addr.id}
                        onClick={() => { setSelectedAddressId(addr.id); setCheckoutAddress(addr.address_line); }}
                        style={{
                          display: "flex", alignItems: "flex-start", gap: "0.875rem",
                          padding: "1rem", borderRadius: "var(--radius-lg)", cursor: "pointer",
                          border: `1.5px solid ${selectedAddressId === addr.id ? "var(--green)" : "var(--border)"}`,
                          background: selectedAddressId === addr.id ? "var(--green-dim)" : "var(--bg-card)",
                          transition: "all var(--t-fast)",
                        }}
                      >
                        <div style={{ width: 18, height: 18, borderRadius: "50%", border: `2px solid ${selectedAddressId === addr.id ? "var(--green)" : "var(--border)"}`, background: selectedAddressId === addr.id ? "var(--green)" : "transparent", boxShadow: selectedAddressId === addr.id ? "inset 0 0 0 3px var(--bg-card)" : "none", flexShrink: 0, marginTop: 2, transition: "all var(--t-fast)" }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.25rem" }}>{addr.label || "Address"}</div>
                          <div style={{ fontSize: "0.8125rem", color: "var(--text-2)", lineHeight: 1.5 }}>{addr.address_line}</div>
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); onDeleteAddress(addr.id, e); }}
                          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", fontSize: "0.75rem", padding: "0.25rem", flexShrink: 0 }}
                          aria-label="Delete address"
                        ></button>
                      </div>
                    ))}
                  </div>

                  {/* Add new address */}
                  {!showAddressManager ? (
                    <button className="btn btn-ghost btn-sm" onClick={() => setShowAddressManager(true)} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Plus size={15} /> Add New Address
                    </button>
                  ) : (
                    <form onSubmit={onAddAddress} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      <div className="form-group">
                        <label className="form-label">Label</label>
                        <select className="form-input" value={newAddrLabel} onChange={e => setNewAddrLabel(e.target.value)}>
                          <option>Home</option><option>Work</option><option>Other</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Address</label>
                        <textarea className="form-input" placeholder="Enter full address…" value={newAddrVal} onChange={e => setNewAddrVal(e.target.value)} rows={3} required />
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button type="submit" className="btn btn-primary btn-sm">Save Address</button>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowAddressManager(false)}>Cancel</button>
                      </div>
                    </form>
                  )}
                </>
              )}

              <button className="btn btn-primary" style={{ width: "100%", marginTop: "1.5rem" }} onClick={() => setStep(2)} disabled={!checkoutAddress.trim() || (!currentUser && (!guestName.trim() || !guestEmail.trim() || !guestPhone.trim()))}>
                Continue to Payment →
              </button>
            </div>
          )}

          {/* Step 2: Payment */}
          {step === 2 && (
            <div className="card card-padded animate-fade-in">
              <h2 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "1.25rem" }}>Payment Method</h2>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1.5rem" }}>
                {PAYMENT_OPTIONS.map(opt => (
                  <div key={opt.id} className={`payment-option${paymentMethod === opt.id ? " selected" : ""}`} onClick={() => setPaymentMethod(opt.id)}>
                    <span className="payment-option-icon">{opt.icon}</span>
                    <div>
                      <div className="payment-option-name">{opt.label}</div>
                      <div className="payment-option-desc">{opt.desc}</div>
                    </div>
                    <div className="payment-radio" />
                  </div>
                ))}
              </div>

              {/* Online payment note */}
              {paymentMethod === "ONLINE" && (
                <div style={{ background: "var(--bg)", padding: "1rem 1.25rem", borderRadius: "var(--radius-lg)", marginBottom: "1.25rem", textAlign: "center" }}>
                  <p style={{ fontSize: "0.875rem", color: "var(--text-2)", margin: 0 }}>
                    A secure Razorpay window opens after you place the order. Pay via UPI, card or net banking.
                  </p>
                </div>
              )}

              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button className="btn btn-secondary" onClick={() => setStep(1)}>← Back</button>
                <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => setStep(3)}>Review Order →</button>
              </div>
            </div>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <div className="card card-padded animate-fade-in">
              <h2 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "1.25rem" }}>Review Your Order</h2>

              {/* Delivery address recap */}
              <div style={{ background: "var(--bg)", borderRadius: "var(--radius-md)", padding: "0.875rem 1rem", marginBottom: "1.25rem" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-3)", marginBottom: "0.375rem" }}>Delivering to</div>
                <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text)" }}>{checkoutAddress}</div>
              </div>

              {/* Items recap */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem", marginBottom: "1.25rem" }}>
                {cartItems.map(item => (
                  <div key={item.id} style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                    <div style={{ width: 48, height: 48, borderRadius: "var(--radius-md)", overflow: "hidden", background: "var(--bg)", flexShrink: 0 }}>
                      <img src={item.image_url || "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=100"} alt={item.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: "0.875rem" }}>{item.name}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-2)" }}>×{item.qty}</div>
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>₹{(item.price * item.qty).toFixed(2)}</div>
                  </div>
                ))}
              </div>

              {storeSettings.is_store_online === "false" && (
                <div className="alert alert-error" style={{ marginBottom: "1rem" }}>Store is currently offline. Orders are paused.</div>
              )}
              {storeSettings.is_holiday === "true" && (
                <div className="alert alert-warning" style={{ marginBottom: "1rem" }}>We're on a holiday break. Check back soon.</div>
              )}

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", cursor: "pointer", background: "var(--bg)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border)" }}>
                  <input type="checkbox" checked={privacyAccepted} onChange={e => setPrivacyAccepted(e.target.checked)} style={{ width: "1.2rem", height: "1.2rem", marginTop: "0.15rem", accentColor: "var(--green)" }} />
                  <div style={{ fontSize: "0.85rem", color: "var(--text-2)", lineHeight: "1.4" }}>
                    {storeSettings.privacy_policy_text !== undefined ? storeSettings.privacy_policy_text : "I agree to the Privacy Policy and consent to my data being processed for this order."}
                  </div>
                </label>
              </div>

              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button className="btn btn-secondary" onClick={() => setStep(2)}>← Back</button>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, minHeight: 52 }}
                  onClick={onPlaceOrder}
                  disabled={!privacyAccepted || paymentProcessing || storeSettings.is_store_online === "false"}
                >
                  {paymentProcessing
                    ? <><span className="spinner" /> Processing…</>
                    : <>{paymentMethod === "COD" ? "Place Order" : "Pay & Order"} • ₹{finalTotal.toFixed(2)}</>}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Order Summary sidebar */}
        <div className="order-summary-card">
          <h2 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "1rem" }}>Summary</h2>
          <div className="summary-row"><span style={{ color: "var(--text-2)" }}>Items ({cartItems.reduce((s, i) => s + i.qty, 0)})</span><span>₹{cartTotal.toFixed(2)}</span></div>
          {discountAmount > 0 && <div className="summary-row"><span style={{ color: "var(--green)" }}>Coupon</span><span style={{ color: "var(--green)" }}>−₹{discountAmount.toFixed(2)}</span></div>}
          {actualLoyaltyDiscount > 0 && <div className="summary-row"><span style={{ color: "var(--green)" }}>Points</span><span style={{ color: "var(--green)" }}>−₹{actualLoyaltyDiscount.toFixed(2)}</span></div>}
          <div className="summary-row"><span style={{ color: "var(--text-2)" }}>Delivery</span><span style={{ color: deliveryCharge === 0 ? "var(--green)" : "inherit" }}>{deliveryCharge === 0 ? "FREE" : `₹${deliveryCharge.toFixed(2)}`}</span></div>
          <div className="summary-row total"><span>Total</span><span>₹{finalTotal.toFixed(2)}</span></div>
          <p style={{ fontSize: "0.7rem", color: "var(--text-3)", marginTop: "0.75rem", textAlign: "center" }}> Secure checkout powered by your trust</p>
        </div>
      </div>
    </div>
  );
}
