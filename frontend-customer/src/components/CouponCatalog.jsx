import React, { useMemo } from "react";
import { X, Tag, Lock, CheckCircle, AlertCircle, Sparkles, Zap, Clock, ShoppingBag } from "../ui/Icon";
import { createPortal } from "react-dom";

// ─────────────────────────────────────────────────────────────
// Coupon eligibility checker
// Returns { eligible: bool, reason: string, savingsText: string }
// ─────────────────────────────────────────────────────────────
export function checkCouponEligibility(coupon, { cartTotal, cartItemIds, user, orders }) {
  const now = new Date();

  if (!coupon.is_active) {
    return { eligible: false, reason: "This coupon is no longer active", savings: 0 };
  }

  if (coupon.expiry_date && new Date(coupon.expiry_date) < now) {
    return { eligible: false, reason: "This coupon has expired", savings: 0 };
  }

  if (coupon.usage_limit && (coupon.usage_count || 0) >= coupon.usage_limit) {
    return { eligible: false, reason: "This coupon has reached its usage limit", savings: 0 };
  }

  if (coupon.applicable_customer_id && user?.id !== coupon.applicable_customer_id) {
    return { eligible: false, reason: "This coupon is not available for your account", savings: 0 };
  }

  if (coupon.is_first_order_only && orders && orders.filter(o => o.status !== "cancelled").length > 0) {
    return { eligible: false, reason: "This coupon is for first-time orders only", savings: 0 };
  }

  if (coupon.min_order_value && cartTotal < coupon.min_order_value) {
    const needed = (coupon.min_order_value - cartTotal).toFixed(0);
    return {
      eligible: false,
      reason: `Add ₹${needed} more to unlock this coupon (min. ₹${coupon.min_order_value})`,
      nearlyEligible: true,
      savings: 0
    };
  }

  if (coupon.applicable_menu_item_id && !cartItemIds.includes(coupon.applicable_menu_item_id)) {
    return { eligible: false, reason: "Add the required product to your cart to use this coupon", savings: 0 };
  }

  // Compute savings
  let savings = 0;
  if (coupon.discount_pct) {
    savings = cartTotal * (coupon.discount_pct / 100);
    if (coupon.max_discount_amount) savings = Math.min(savings, coupon.max_discount_amount);
  } else if (coupon.discount_amount) {
    savings = coupon.discount_amount;
  }

  return { eligible: true, reason: "You're eligible!", savings };
}

// ─────────────────────────────────────────────────────────────
// Individual Coupon Card
// ─────────────────────────────────────────────────────────────
function CouponCard({ coupon, eligibility, appliedCoupon, onApply, onRemove }) {
  const isApplied = appliedCoupon?.code === coupon.code;
  const { eligible, reason, nearlyEligible, savings } = eligibility;

  const discountLabel = coupon.discount_pct
    ? `${coupon.discount_pct}% OFF${coupon.max_discount_amount ? ` (up to ₹${coupon.max_discount_amount})` : ""}`
    : `₹${coupon.discount_amount} OFF`;

  const statusColor = isApplied
    ? "var(--green)"
    : eligible
    ? "var(--green)"
    : nearlyEligible
    ? "#f59e0b"
    : "var(--text-3)";

  const cardBg = isApplied
    ? "var(--green-dim)"
    : eligible
    ? "var(--bg-card)"
    : "var(--bg-hover)";

  const borderColor = isApplied
    ? "var(--green)"
    : eligible
    ? "var(--border)"
    : nearlyEligible
    ? "rgba(245,158,11,0.3)"
    : "var(--border)";

  return (
    <div style={{
      background: cardBg,
      border: `1.5px solid ${borderColor}`,
      borderRadius: "var(--radius-xl)",
      padding: "1rem 1.125rem",
      display: "flex",
      flexDirection: "column",
      gap: "0.625rem",
      opacity: (!eligible && !nearlyEligible) ? 0.65 : 1,
      transition: "all var(--t-fast)",
      position: "relative",
      overflow: "hidden"
    }}>
      {/* Decorative dashed left border accent */}
      <div style={{
        position: "absolute",
        left: 0, top: 0, bottom: 0,
        width: 4,
        background: statusColor,
        borderRadius: "4px 0 0 4px"
      }} />

      {/* Top: code + badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Tag size={15} color={statusColor} />
          <span style={{
            fontFamily: "monospace",
            fontWeight: 800,
            fontSize: "1rem",
            letterSpacing: "1.5px",
            color: "var(--text)",
            background: "var(--bg)",
            padding: "0.2rem 0.6rem",
            borderRadius: "var(--radius-md)",
            border: "1px dashed var(--border)"
          }}>{coupon.code}</span>
        </div>

        <div style={{
          fontSize: "0.8125rem",
          fontWeight: 800,
          color: "white",
          background: eligible || isApplied ? "var(--green)" : nearlyEligible ? "#f59e0b" : "var(--text-3)",
          padding: "0.25rem 0.625rem",
          borderRadius: "var(--radius-pill)",
          whiteSpace: "nowrap",
          flexShrink: 0
        }}>
          {discountLabel}
        </div>
      </div>

      {/* Middle: conditions */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem" }}>
        {coupon.min_order_value && (
          <span style={{ fontSize: "0.72rem", color: "var(--text-2)", background: "var(--bg)", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", border: "1px solid var(--border)" }}>
            Min. ₹{coupon.min_order_value}
          </span>
        )}
        {coupon.is_first_order_only && (
          <span style={{ fontSize: "0.72rem", color: "var(--text-2)", background: "var(--bg)", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", border: "1px solid var(--border)" }}>
            First order only
          </span>
        )}
        {coupon.applicable_customer_id && (
          <span style={{ fontSize: "0.72rem", color: "#8b5cf6", background: "rgba(139,92,246,0.08)", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", border: "1px solid rgba(139,92,246,0.2)" }}>
            Exclusive offer
          </span>
        )}
        {coupon.expiry_date && (
          <span style={{ fontSize: "0.72rem", color: "var(--text-3)", display: "flex", alignItems: "center", gap: 3, background: "var(--bg)", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", border: "1px solid var(--border)" }}>
            <Clock size={10} />
            Expires {new Date(coupon.expiry_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
          </span>
        )}
      </div>

      {/* Status + savings */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flex: 1 }}>
          {eligible || isApplied
            ? <CheckCircle size={13} color="var(--green)" />
            : nearlyEligible
            ? <AlertCircle size={13} color="#f59e0b" />
            : <Lock size={13} color="var(--text-3)" />}
          <span style={{ fontSize: "0.75rem", color: nearlyEligible ? "#f59e0b" : eligible || isApplied ? "var(--green)" : "var(--text-3)", lineHeight: 1.4 }}>
            {isApplied ? "Applied" : reason}
          </span>
        </div>

        {eligible && savings > 0 && !isApplied && (
          <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "var(--green)", whiteSpace: "nowrap" }}>
            Save ₹{savings.toFixed(0)}
          </span>
        )}
      </div>

      {/* Action button */}
      {isApplied ? (
        <button
          onClick={onRemove}
          className="btn btn-sm"
          style={{ background: "transparent", border: "1.5px solid var(--green)", color: "var(--green)", borderRadius: "var(--radius-md)", fontSize: "0.8125rem" }}
        >
          Remove Coupon
        </button>
      ) : eligible ? (
        <button
          onClick={() => onApply(coupon.code)}
          className="btn btn-primary btn-sm"
          style={{ borderRadius: "var(--radius-md)", fontSize: "0.8125rem" }}
        >
          Apply Coupon
        </button>
      ) : (
        <button
          disabled
          className="btn btn-sm"
          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-3)", borderRadius: "var(--radius-md)", fontSize: "0.8125rem", cursor: "not-allowed" }}
        >
          {nearlyEligible ? "Almost there..." : <><Lock size={12} style={{ display: "inline", marginRight: 4 }} />Not Eligible</>}
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Catalog Modal
// ─────────────────────────────────────────────────────────────
export default function CouponCatalog({
  open, onClose,
  coupons, cartTotal, cartItemIds, user, orders,
  appliedCoupon, onApply, onRemove
}) {
  const eligibilityMap = useMemo(() => {
    const map = {};
    coupons.forEach(c => {
      map[c.id] = checkCouponEligibility(c, { cartTotal, cartItemIds, user, orders });
    });
    return map;
  }, [coupons, cartTotal, cartItemIds, user, orders]);

  // Sort: applied > eligible (best savings first) > nearlyEligible > locked
  const sorted = useMemo(() => {
    return [...coupons].sort((a, b) => {
      const ea = eligibilityMap[a.id];
      const eb = eligibilityMap[b.id];
      const applied = appliedCoupon?.code;
      if (a.code === applied) return -1;
      if (b.code === applied) return 1;
      if (ea.eligible && !eb.eligible) return -1;
      if (!ea.eligible && eb.eligible) return 1;
      if (ea.eligible && eb.eligible) return eb.savings - ea.savings;
      if (ea.nearlyEligible && !eb.nearlyEligible) return -1;
      if (!ea.nearlyEligible && eb.nearlyEligible) return 1;
      return 0;
    });
  }, [coupons, eligibilityMap, appliedCoupon]);

  const eligible = sorted.filter(c => eligibilityMap[c.id].eligible);
  const nearlyEligible = sorted.filter(c => !eligibilityMap[c.id].eligible && eligibilityMap[c.id].nearlyEligible);
  const locked = sorted.filter(c => !eligibilityMap[c.id].eligible && !eligibilityMap[c.id].nearlyEligible);
  const bestSavings = eligible.reduce((max, c) => Math.max(max, eligibilityMap[c.id].savings), 0);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-overlay"
      onClick={onClose}
      style={{ zIndex: 700, alignItems: "flex-end" }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--bg-card)",
          borderRadius: "var(--radius-2xl) var(--radius-2xl) 0 0",
          width: "100%",
          maxWidth: 560,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.3)",
          animation: "slideUp 0.25s ease-out"
        }}
      >
        {/* Header */}
        <div style={{
          padding: "1.25rem 1.5rem 1rem",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Tag size={20} color="var(--green)" />
              <h2 style={{ fontSize: "1.125rem", fontWeight: 900, color: "var(--text)", margin: 0 }}>
                All Coupons
              </h2>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-2)", marginTop: "0.2rem" }}>
              {coupons.length} coupon{coupons.length !== 1 ? "s" : ""} available
              {bestSavings > 0 && ` · Best saving: ₹${bestSavings.toFixed(0)}`}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: "var(--bg)", border: "none", borderRadius: "50%", width: 36, height: 36, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-2)" }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable content */}
        <div style={{ overflowY: "auto", flex: 1, padding: "1rem 1.5rem 1.5rem" }}>
          {/* Personalized recommendations */}
          {eligible.length > 0 && (
            <section style={{ marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "0.75rem" }}>
                <Sparkles size={15} color="var(--green)" />
                <span style={{ fontSize: "0.8rem", fontWeight: 800, color: "var(--green)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Available for You
                </span>
                <span style={{ marginLeft: "auto", fontSize: "0.72rem", background: "var(--green)", color: "white", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", fontWeight: 700 }}>
                  {eligible.length}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {eligible.map(c => (
                  <CouponCard
                    key={c.id}
                    coupon={c}
                    eligibility={eligibilityMap[c.id]}
                    appliedCoupon={appliedCoupon}
                    onApply={(code) => { onApply(code); onClose(); }}
                    onRemove={() => { onRemove(); onClose(); }}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Nearly eligible */}
          {nearlyEligible.length > 0 && (
            <section style={{ marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "0.75rem" }}>
                <Zap size={15} color="#f59e0b" />
                <span style={{ fontSize: "0.8rem", fontWeight: 800, color: "#f59e0b", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Almost Eligible
                </span>
                <span style={{ marginLeft: "auto", fontSize: "0.72rem", background: "#f59e0b", color: "white", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", fontWeight: 700 }}>
                  {nearlyEligible.length}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {nearlyEligible.map(c => (
                  <CouponCard
                    key={c.id}
                    coupon={c}
                    eligibility={eligibilityMap[c.id]}
                    appliedCoupon={appliedCoupon}
                    onApply={(code) => { onApply(code); onClose(); }}
                    onRemove={() => { onRemove(); onClose(); }}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Locked */}
          {locked.length > 0 && (
            <section>
              <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "0.75rem" }}>
                <Lock size={15} color="var(--text-3)" />
                <span style={{ fontSize: "0.8rem", fontWeight: 800, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Not Eligible
                </span>
                <span style={{ marginLeft: "auto", fontSize: "0.72rem", background: "var(--bg-hover)", color: "var(--text-3)", padding: "0.15rem 0.5rem", borderRadius: "var(--radius-pill)", fontWeight: 700 }}>
                  {locked.length}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {locked.map(c => (
                  <CouponCard
                    key={c.id}
                    coupon={c}
                    eligibility={eligibilityMap[c.id]}
                    appliedCoupon={appliedCoupon}
                    onApply={(code) => { onApply(code); onClose(); }}
                    onRemove={() => { onRemove(); onClose(); }}
                  />
                ))}
              </div>
            </section>
          )}

          {coupons.length === 0 && (
            <div style={{ textAlign: "center", padding: "3rem 0", color: "var(--text-3)" }}>
              <ShoppingBag size={40} style={{ opacity: 0.3, marginBottom: "0.75rem" }} />
              <p style={{ fontSize: "0.9rem" }}>No coupons available right now.</p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
