import React, { useState, useMemo } from "react";
import {
  Trash2, ShoppingBag, Tag, Truck, ChevronDown, ChevronUp,
  CheckCircle, Lock, AlertCircle, Plus, Clock, ShieldCheck,
  ArrowRight, Zap, Minus, Star
} from "../ui/Icon";
import { checkCouponEligibility } from "./CouponCatalog";

const FALLBACK = "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=200&q=70";

// ─────────────────────────────────────────────────────────────
// Delivery progress bar
// ─────────────────────────────────────────────────────────────
function DeliveryBar({ cartTotal }) {
  const FREE_AT = 499;
  const pct = Math.min(100, (cartTotal / FREE_AT) * 100);
  const left = Math.max(0, FREE_AT - cartTotal);
  const done = cartTotal >= FREE_AT;

  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
          <Truck size={14} color={done ? "var(--green)" : "var(--text-2)"} />
          <span style={{ fontSize: "0.8rem", color: done ? "var(--green)" : "var(--text-2)", fontWeight: done ? 700 : 500 }}>
            {done ? "Free delivery unlocked!" : <>Add <strong style={{ color: "var(--text)" }}>₹{left.toFixed(0)}</strong> for free delivery</>}
          </span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>₹{FREE_AT}</span>
      </div>
      <div style={{ height: 6, background: "var(--bg)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${pct}%`,
          background: done
            ? "var(--green)"
            : "linear-gradient(90deg, var(--green) 0%, #95f5b4 100%)",
          borderRadius: 999,
          transition: "width 0.5s var(--ease)"
        }} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Single inline coupon row
// ─────────────────────────────────────────────────────────────
function InlineCouponRow({ coupon, eligibility, appliedCoupon, onApply, onRemove }) {
  const isApplied = appliedCoupon?.code === coupon.code;
  const { eligible, reason, nearlyEligible, savings } = eligibility;

  const discountLabel = coupon.discount_pct
    ? `${coupon.discount_pct}% OFF${coupon.max_discount_amount ? ` · max ₹${coupon.max_discount_amount}` : ""}`
    : `₹${coupon.discount_amount} OFF`;

  const accentColor = isApplied || eligible ? "var(--green)" : nearlyEligible ? "#f59e0b" : "var(--text-3)";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "0.75rem",
      padding: "0.75rem 0",
      borderBottom: "1px dashed var(--border)",
      opacity: (!eligible && !nearlyEligible && !isApplied) ? 0.55 : 1,
    }}>
      <div style={{ width: 3, alignSelf: "stretch", background: accentColor, borderRadius: 3, flexShrink: 0 }} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.2rem", flexWrap: "wrap" }}>
          <span style={{ fontFamily: "monospace", fontWeight: 800, fontSize: "0.875rem", letterSpacing: "1px", color: "var(--text)" }}>
            {coupon.code}
          </span>
          <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "white", background: accentColor, padding: "0.1rem 0.45rem", borderRadius: "var(--radius-pill)", whiteSpace: "nowrap" }}>
            {discountLabel}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
          {isApplied || eligible
            ? <CheckCircle size={11} color="var(--green)" />
            : nearlyEligible
            ? <AlertCircle size={11} color="#f59e0b" />
            : <Lock size={11} color="var(--text-3)" />}
          <span style={{ fontSize: "0.7rem", color: isApplied || eligible ? "var(--green)" : nearlyEligible ? "#f59e0b" : "var(--text-3)" }}>
            {isApplied ? "Applied" : reason}
          </span>
          {eligible && savings > 0 && !isApplied && (
            <span style={{ marginLeft: "auto", fontSize: "0.72rem", fontWeight: 800, color: "var(--green)" }}>Save ₹{savings.toFixed(0)}</span>
          )}
        </div>
      </div>

      {isApplied ? (
        <button onClick={onRemove} style={{ fontSize: "0.72rem", fontWeight: 700, padding: "0.3rem 0.65rem", background: "var(--green-dim)", border: "1px solid var(--green)", color: "var(--green)", borderRadius: "var(--radius-md)", cursor: "pointer", fontFamily: "inherit" }}>
          Remove
        </button>
      ) : eligible ? (
        <button onClick={() => onApply(coupon.code)} style={{ fontSize: "0.72rem", fontWeight: 700, padding: "0.3rem 0.65rem", background: "var(--green)", border: "none", color: "white", borderRadius: "var(--radius-md)", cursor: "pointer", fontFamily: "inherit" }}>
          Apply
        </button>
      ) : (
        <span style={{ fontSize: "0.7rem", color: "var(--text-3)", padding: "0.3rem 0.55rem", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}>
          {nearlyEligible ? "Soon" : <Lock size={10} style={{ display: "inline" }} />}
        </span>
      )}
    </div>
  );
}

function InlineCouponPanel({ coupons, cartTotal, cartItemIds, user, orders, appliedCoupon, onApply, onRemove }) {
  const eligibilityMap = useMemo(() => {
    const map = {};
    coupons.forEach(c => { map[c.id] = checkCouponEligibility(c, { cartTotal, cartItemIds, user, orders }); });
    return map;
  }, [coupons, cartTotal, cartItemIds, user, orders]);

  const sorted = useMemo(() => {
    return [...coupons].sort((a, b) => {
      const ea = eligibilityMap[a.id], eb = eligibilityMap[b.id];
      if (a.code === appliedCoupon?.code) return -1;
      if (b.code === appliedCoupon?.code) return 1;
      if (ea.eligible && !eb.eligible) return -1;
      if (!ea.eligible && eb.eligible) return 1;
      if (ea.eligible && eb.eligible) return eb.savings - ea.savings;
      if (ea.nearlyEligible && !eb.nearlyEligible) return -1;
      if (!ea.nearlyEligible && eb.nearlyEligible) return 1;
      return 0;
    });
  }, [coupons, eligibilityMap, appliedCoupon]);

  return (
    <div className="coupon-panel-scroll" style={{ maxHeight: 300, paddingRight: 2 }}>
      {sorted.map(c => (
        <InlineCouponRow key={c.id} coupon={c} eligibility={eligibilityMap[c.id]} appliedCoupon={appliedCoupon} onApply={onApply} onRemove={onRemove} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Combo recommender
// ─────────────────────────────────────────────────────────────
function ComboRecommender({ cartTotal, menu, cart, coupons, onAddItem }) {
  const couponMins = coupons
    .filter(c => c.min_order_value && c.is_active && cartTotal < c.min_order_value)
    .map(c => ({ amount: c.min_order_value, label: `Unlock ${c.code}` }));

  const allTargets = [
    { amount: 499, label: "Get Free Delivery" },
    { amount: 1000, label: "₹1000 Big Saver!" },
    ...couponMins,
  ].filter(t => t.amount > cartTotal).sort((a, b) => a.amount - b.amount);

  if (allTargets.length === 0) return null;
  const nearest = allTargets[0];
  const needed = nearest.amount - cartTotal;

  const cartItemIds = new Set(Object.keys(cart).map(Number));
  const candidates = menu
    .filter(m => m.is_active && !cartItemIds.has(m.id) && m.price <= needed + 150)
    .sort((a, b) => Math.abs(a.price - needed) - Math.abs(b.price - needed))
    .slice(0, 5);

  if (candidates.length === 0) return null;

  return (
    <div style={{ marginBottom: "1rem", background: "var(--green-dim)", border: "1.5px dashed var(--green)", borderRadius: "var(--radius-lg)", padding: "0.875rem 0.875rem 0.75rem", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "0.75rem" }}>
        <Zap size={14} color="var(--green)" />
        <span style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--green)" }}>
          Add ₹{needed.toFixed(0)} more → {nearest.label}
        </span>
      </div>
      <div className="combo-scroll" style={{ display: "flex", gap: "0.5rem", paddingBottom: 4 }}>
        {candidates.map(item => (
          <button
            key={item.id}
            onClick={() => onAddItem(item.id)}
            title={item.name}
            style={{
              flexShrink: 0, width: 90,
              display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem",
              background: "var(--bg-card)",
              border: "1.5px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "0.5rem 0.4rem 0.4rem",
              cursor: "pointer", fontFamily: "inherit",
              transition: "border-color var(--t-fast), transform var(--t-fast)",
              textAlign: "center"
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--green)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.transform = "none"; }}
          >
            <img src={item.image_url || FALLBACK} alt={item.name} onError={e => { e.target.src = FALLBACK; }}
              style={{ width: 52, height: 52, objectFit: "cover", borderRadius: "var(--radius-sm)", marginBottom: 2 }} />
            <span style={{ fontSize: "0.65rem", color: "var(--text)", fontWeight: 600, lineHeight: 1.25, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", width: "100%" }}>
              {item.name}
            </span>
            <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "var(--green)" }}>₹{item.price}</span>
            <span style={{ fontSize: "0.65rem", color: "var(--green)", fontWeight: 700, display: "flex", alignItems: "center", gap: 2 }}>
              <Plus size={9} /> Add
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main CartPage — Premium Redesign
// ─────────────────────────────────────────────────────────────
export default function CartPage({
  menu, cart, addresses, selectedAddressId, onAdd, onRemove, onClearItem,
  couponCodeInput, setCouponCodeInput, appliedCoupon, onApplyCoupon, onRemoveCoupon,
  couponError, activeCoupons, useLoyaltyPoints, setUseLoyaltyPoints,
  loyaltyPoints, maxLoyaltyDiscount, finalSubtotal, deliveryCharge, finalTotal,
  discountAmount, actualLoyaltyDiscount, storeSettings, isLoyaltyEnabled, onCheckout, checkoutBanners,
  currentUser, orders
}) {
  const [showCouponPanel, setShowCouponPanel] = useState(false);

  const cartItems = Object.entries(cart)
    .map(([id, qty]) => {
      const item = menu.find(m => m.id === parseInt(id));
      return item ? { ...item, qty } : null;
    })
    .filter(Boolean);

  if (cartItems.length === 0) {
    return (
      <div className="page-content" style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "4rem", marginBottom: "1rem" }}></div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--text)", marginBottom: "0.5rem" }}>Your cart is empty</h2>
          <p style={{ color: "var(--text-2)", fontSize: "0.9rem" }}>Add some delicious items to get started!</p>
        </div>
      </div>
    );
  }

  const cartTotal = Object.entries(cart).reduce((s, [id, qty]) => {
    const item = menu.find(m => m.id === parseInt(id));
    return s + (item ? item.price * qty : 0);
  }, 0);
  const cartItemIds = Object.keys(cart).map(id => parseInt(id));
  const itemCount = Object.values(cart).reduce((a, b) => a + b, 0);

  const eligibleCount = activeCoupons.filter(c => {
    if (!c.is_active) return false;
    if (c.min_order_value && cartTotal < c.min_order_value) return false;
    if (c.applicable_customer_id && currentUser?.id !== c.applicable_customer_id) return false;
    if (c.is_first_order_only && orders?.filter(o => o.status !== "cancelled").length > 0) return false;
    if (c.applicable_menu_item_id && !cartItemIds.includes(c.applicable_menu_item_id)) return false;
    return true;
  }).length;

  return (
    <div className="page-content">

      {/* ── Page header */}
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "1.75rem" }}>
        <h1 style={{ fontSize: "1.625rem", fontWeight: 900, color: "var(--text)" }}>Your Cart</h1>
        <span style={{ fontSize: "0.825rem", color: "var(--text-3)", fontWeight: 500 }}>
          {itemCount} item{itemCount !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="cart-layout">

        {/* ── LEFT: Cart items */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
          {cartItems.map((item, idx) => (
            <div
              key={item.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "1rem",
                padding: "1.125rem 0",
                borderBottom: idx < cartItems.length - 1 ? "1px solid var(--border)" : "none",
              }}
            >
              {/* Image */}
              <div style={{ position: "relative", flexShrink: 0 }}>
                <img
                  src={item.image_url || FALLBACK}
                  alt={item.name}
                  onError={e => { e.target.src = FALLBACK; }}
                  style={{ width: 80, height: 80, objectFit: "cover", borderRadius: "var(--radius-md)", border: "1.5px solid var(--border)" }}
                />
                {item.is_best_seller && (
                  <div style={{ position: "absolute", top: -6, left: -6, background: "#f59e0b", color: "white", borderRadius: "var(--radius-pill)", padding: "0.1rem 0.4rem", fontSize: "0.6rem", fontWeight: 800, display: "flex", alignItems: "center", gap: 2 }}>
                    <Star size={8} fill="white" /> BEST
                  </div>
                )}
              </div>

              {/* Details */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--text)", marginBottom: "0.2rem", lineHeight: 1.3 }}>
                  {item.name}
                </h3>
                <p style={{ fontSize: "0.78rem", color: "var(--text-2)", marginBottom: "0.6rem" }}>{item.category}</p>

                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  {/* Qty controls */}
                  <div style={{ display: "flex", alignItems: "center", background: "var(--bg)", border: "1.5px solid var(--border)", borderRadius: "var(--radius-pill)", overflow: "hidden" }}>
                    <button
                      onClick={() => onRemove(item.id)}
                      style={{ width: 32, height: 32, border: "none", background: "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-2)", transition: "background var(--t-fast)" }}
                      onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                    >
                      <Minus size={13} />
                    </button>
                    <span style={{ minWidth: 28, textAlign: "center", fontWeight: 800, fontSize: "0.875rem", color: "var(--text)" }}>
                      {item.qty}
                    </span>
                    <button
                      onClick={() => onAdd(item.id)}
                      style={{ width: 32, height: 32, border: "none", background: "transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--green)", transition: "background var(--t-fast)" }}
                      onMouseEnter={e => e.currentTarget.style.background = "var(--green-dim)"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                    >
                      <Plus size={13} />
                    </button>
                  </div>

                  {/* Unit price */}
                  {item.qty > 1 && (
                    <span style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>₹{item.price} each</span>
                  )}
                </div>
              </div>

              {/* Right: price + remove */}
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{ fontSize: "1.0625rem", fontWeight: 900, color: "var(--text)", marginBottom: "0.5rem" }}>
                  ₹{(item.price * item.qty).toFixed(0)}
                </div>
                <button
                  onClick={() => onClearItem(item.id)}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: "0.2rem", transition: "color var(--t-fast)", fontFamily: "inherit" }}
                  onMouseEnter={e => e.currentTarget.style.color = "var(--error)"}
                  onMouseLeave={e => e.currentTarget.style.color = "var(--text-3)"}
                >
                  <Trash2 size={12} /> Remove
                </button>
              </div>
            </div>
          ))}

          {/* Delivery & Combos (Moved from Right Side) */}
          <div style={{ marginTop: "2rem" }}>
            <DeliveryBar cartTotal={cartTotal} />
            <ComboRecommender
              cartTotal={cartTotal}
              menu={menu}
              cart={cart}
              coupons={activeCoupons}
              onAddItem={onAdd}
            />
          </div>
        </div>

        {/* ── RIGHT: Order Summary — CTA always visible */}
        <div>
          <div style={{
            background: "var(--bg-card)",
            borderRadius: "var(--radius-xl)",
            border: "1.5px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
            display: "flex",
            flexDirection: "column",
            /* Cap height so the card never exceeds the viewport */
            maxHeight: "calc(100vh - var(--header-h) - 2rem)",
            position: "sticky",
            top: "calc(var(--header-h) + 1rem)",
            overflow: "hidden"
          }}>

            {/* ── Card header — fixed */}
            <div style={{ padding: "1.125rem 1.25rem 0.875rem", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 800, color: "var(--text)" }}>Order Summary</h2>
            </div>

            {/* ── Scrollable body */}
            <div style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem", scrollbarWidth: "none" }}
              className="coupon-panel-scroll">

              {/* Coupon section */}
              <div style={{ marginBottom: "1rem" }}>
                {appliedCoupon ? (
                  <div style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    background: "var(--green-dim)", border: "1.5px solid var(--green)",
                    borderRadius: "var(--radius-md)", padding: "0.625rem 0.875rem"
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8125rem", color: "var(--green)", fontWeight: 700 }}>
                      <Tag size={14} />
                      {appliedCoupon.code} — {appliedCoupon.discount_pct ? `${appliedCoupon.discount_pct}% off` : `₹${appliedCoupon.discount_amount} off`}
                    </div>
                    <button onClick={onRemoveCoupon} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", fontSize: "0.72rem", fontFamily: "inherit" }}>
                       Remove
                    </button>
                  </div>
                ) : (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <input
                      className="form-input"
                      placeholder="Enter coupon code"
                      value={couponCodeInput}
                      onChange={e => setCouponCodeInput(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && onApplyCoupon()}
                      style={{ flex: 1, fontSize: "0.85rem", padding: "0.6rem 0.875rem", minHeight: 42 }}
                    />
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => onApplyCoupon()}
                      style={{ flexShrink: 0, minHeight: 42, borderRadius: "var(--radius-md)", fontWeight: 700 }}
                    >Apply</button>
                  </div>
                )}

                {couponError && (
                  <p style={{ fontSize: "0.74rem", color: "var(--error)", marginTop: "0.375rem" }}>{couponError}</p>
                )}

                {activeCoupons.length > 0 && (
                  <>
                    <button
                      onClick={() => setShowCouponPanel(p => !p)}
                      style={{
                        marginTop: "0.5rem", width: "100%",
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        background: showCouponPanel ? "var(--green-dim)" : "transparent",
                        border: "1.5px dashed var(--green)",
                        borderRadius: showCouponPanel ? "var(--radius-md) var(--radius-md) 0 0" : "var(--radius-md)",
                        padding: "0.55rem 0.875rem",
                        cursor: "pointer", color: "var(--green)",
                        fontSize: "0.8rem", fontWeight: 700, fontFamily: "inherit",
                        transition: "all var(--t-fast)"
                      }}
                    >
                      <span style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                        <Tag size={13} />
                        View All Coupons
                        {eligibleCount > 0 && (
                          <span style={{ background: "var(--green)", color: "white", fontSize: "0.66rem", fontWeight: 800, padding: "0.1rem 0.45rem", borderRadius: "var(--radius-pill)" }}>
                            {eligibleCount} available
                          </span>
                        )}
                      </span>
                      {showCouponPanel ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {showCouponPanel && (
                      <div style={{
                        border: "1.5px dashed var(--green)", borderTop: "none",
                        borderRadius: "0 0 var(--radius-md) var(--radius-md)",
                        padding: "0 0.875rem", background: "var(--bg-card)",
                        animation: "fadeIn 0.15s ease-out"
                      }}>
                        <InlineCouponPanel
                          coupons={activeCoupons}
                          cartTotal={cartTotal}
                          cartItemIds={cartItemIds}
                          user={currentUser}
                          orders={orders || []}
                          appliedCoupon={appliedCoupon}
                          onApply={(code) => { onApplyCoupon(code); setShowCouponPanel(false); }}
                          onRemove={() => { onRemoveCoupon(); setShowCouponPanel(false); }}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Loyalty points */}
              {(isLoyaltyEnabled && loyaltyPoints > 0) && (
                <div style={{ marginBottom: "1rem", background: "var(--bg)", borderRadius: "var(--radius-md)", padding: "0.75rem 0.875rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.625rem", cursor: "pointer", fontSize: "0.85rem" }}>
                    <input type="checkbox" checked={useLoyaltyPoints} onChange={e => setUseLoyaltyPoints(e.target.checked)}
                      style={{ accentColor: "var(--green)", width: 16, height: 16 }} />
                    <div>
                      <div style={{ fontWeight: 700, color: "var(--text)" }}>Use {loyaltyPoints} loyalty points</div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-3)" }}>Saves ₹{maxLoyaltyDiscount.toFixed(2)}</div>
                    </div>
                  </label>
                </div>
              )}

              {/* Totals */}
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.875rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span style={{ color: "var(--text-2)" }}>Subtotal ({itemCount} item{itemCount !== 1 ? "s" : ""})</span>
                  <span style={{ fontWeight: 600 }}>₹{cartTotal.toFixed(2)}</span>
                </div>
                {discountAmount > 0 && (
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                    <span style={{ color: "var(--green)" }}>Coupon discount</span>
                    <span style={{ color: "var(--green)", fontWeight: 700 }}>−₹{discountAmount.toFixed(2)}</span>
                  </div>
                )}
                {actualLoyaltyDiscount > 0 && (
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                    <span style={{ color: "var(--green)" }}>Loyalty points</span>
                    <span style={{ color: "var(--green)", fontWeight: 700 }}>−₹{actualLoyaltyDiscount.toFixed(2)}</span>
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span style={{ color: "var(--text-2)" }}>Delivery</span>
                  <span style={{ fontWeight: 600, color: deliveryCharge === 0 ? "var(--green)" : "var(--text)" }}>
                    {deliveryCharge === 0 ? "Free" : `₹${deliveryCharge.toFixed(2)}`}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "1.0625rem", fontWeight: 900, color: "var(--text)", paddingTop: "0.5rem", borderTop: "1.5px solid var(--border)", marginTop: "0.25rem" }}>
                  <span>Total</span>
                  <span>₹{finalTotal.toFixed(2)}</span>
                </div>
                {(discountAmount > 0 || actualLoyaltyDiscount > 0 || deliveryCharge === 0) && (
                  <div style={{ textAlign: "center", fontSize: "0.775rem", color: "var(--green)", fontWeight: 700, background: "var(--green-dim)", padding: "0.4rem 0.75rem", borderRadius: "var(--radius-md)" }}>
                    "You are saving ₹{(discountAmount + actualLoyaltyDiscount + (deliveryCharge === 0 ? 49 : 0)).toFixed(0)} on this order!
                  </div>
                )}
              </div>
            </div>

            {/* ── CTA — always pinned at bottom, never scrolls away */}
            <div style={{
              padding: "0.875rem 1.25rem 1.125rem",
              borderTop: "1px solid var(--border)",
              background: "var(--bg-card)",
              flexShrink: 0
            }}>
              <button
                className="btn btn-primary btn-full"
                style={{ minHeight: 52, fontSize: "1rem", fontWeight: 800, borderRadius: "var(--radius-lg)", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.625rem" }}
                onClick={onCheckout}
              >
                <ShoppingBag size={19} />
                Proceed to Checkout
                <ArrowRight size={16} />
              </button>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem", marginTop: "0.625rem", fontSize: "0.72rem", color: "var(--text-3)" }}>
                <ShieldCheck size={13} />
                Safe &amp; Secure Checkout — 100% encrypted
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
