import React, { useState } from "react";
import { Package, Truck, Check, ChevronDown, ChevronUp, RotateCcw, MessageSquare, Download, Star } from "../ui/Icon";
import { OrderListSkeleton } from "./SkeletonLoader";

function StatusPill({ status }) {
  const cls = `status-${status}`;
  const labels = { pending: "Pending", processing: "Processing", ready: "Ready", shipped: "Shipped", delivered: "Delivered", completed: "Completed", cancelled: "Cancelled" };
  return <span className={`status-pill ${cls}`}>{labels[status] || status}</span>;
}

function OrderProgress({ status }) {
  const stages = ["pending", "processing", "shipped", "delivered"];
  const icons = [Package, Package, Truck, Check];
  const current = { pending: 0, processing: 1, ready: 1, shipped: 2, delivered: 3, completed: 3 }[status] ?? 0;

  if (status === "cancelled") return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, margin: "0.75rem 0" }}>
      {stages.map((s, i) => {
        const Icon = icons[i];
        const done = i <= current;
        return (
          <React.Fragment key={s}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: done ? "var(--green)" : "var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: done ? "#fff" : "var(--text-3)",
                transition: "all 0.3s",
              }}>
                <Icon size={15} />
              </div>
            </div>
            {i < stages.length - 1 && (
              <div style={{ flex: 1, height: 2, background: i < current ? "var(--green)" : "var(--border)", transition: "background 0.3s" }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function OrderCard({ order, trackingCode, setTrackingCode, onConfirmReceipt, onCancel, onFeedback, feedbackRating, feedbackComment, setFeedbackRating, setFeedbackComment, onReport, onDownload, onSetReview, onPayNow }) {
  const [expanded, setExpanded] = useState(false);

  const subtotal = order.items?.reduce((s, i) => s + i.price * i.quantity, 0) || 0;

  return (
    <div className="order-card animate-fade-in">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: "1rem", color: "var(--text)" }}>Order #{order.id}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-3)", marginTop: "0.2rem" }}>
            {new Date(order.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <StatusPill status={order.status} />
          <button onClick={() => setExpanded(e => !e)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-2)", padding: "0.25rem", display: "flex" }}>
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <OrderProgress status={order.status} />

      {/* Items preview */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {order.items?.slice(0, 4).map(i => (
          <span key={i.menu_item_id} style={{ fontSize: "0.8rem", background: "var(--bg)", borderRadius: "var(--radius-pill)", padding: "0.2rem 0.625rem", color: "var(--text-2)" }}>
            {i.menu_item_name} ×{i.quantity}
          </span>
        ))}
        {(order.items?.length > 4) && (
          <span style={{ fontSize: "0.8rem", background: "var(--bg)", borderRadius: "var(--radius-pill)", padding: "0.2rem 0.625rem", color: "var(--text-2)" }}>
            +{order.items.length - 4} more
          </span>
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--text)" }}>₹{parseFloat(order.total_price).toFixed(2)}</span>
        <span style={{ fontSize: "0.8rem", color: "var(--text-3)" }}>
          {order.payment_method || "COD"}
          {order.payment_status === "paid" && (
            <span style={{ color: "var(--green)", fontWeight: 700 }}> • Paid </span>
          )}
        </span>
      </div>

      {/* Expand: full details */}
      {expanded && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1rem" }}>
          {/* Detailed items */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1rem" }}>
            {order.items?.map(i => (
              <div key={i.menu_item_id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                <span>{i.menu_item_name} ×{i.quantity}</span>
                <span style={{ fontWeight: 600 }}>₹{(i.price * i.quantity).toFixed(2)}</span>
              </div>
            ))}
            {order.delivery_charge > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem", color: "var(--text-2)" }}>
                <span>Delivery charge</span>
                <span>₹{parseFloat(order.delivery_charge).toFixed(2)}</span>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 800, borderTop: "1px solid var(--border)", paddingTop: "0.5rem" }}>
              <span>Total</span>
              <span>₹{parseFloat(order.total_price).toFixed(2)}</span>
            </div>
          </div>

          {order.delivery_address && (
            <div style={{ fontSize: "0.8rem", color: "var(--text-2)", marginBottom: "0.875rem" }}>
               {order.delivery_address}
            </div>
          )}

          {/* Tracking info */}
          {order.tracking_code && (
            <div style={{ background: "var(--bg)", padding: "0.875rem", borderRadius: "var(--radius-md)", marginBottom: "0.875rem", fontSize: "0.8rem" }}>
              <span style={{ fontWeight: 700 }}>Tracking: </span>{order.tracking_label || order.tracking_code}
              {order.tracking_link && <a href={order.tracking_link} target="_blank" rel="noreferrer" style={{ marginLeft: "0.5rem", color: "var(--green)", fontWeight: 600 }}>Track</a>}
            </div>
          )}

          {/* Confirm receipt */}
          {order.status === "shipped" && (
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.875rem", flexWrap: "wrap" }}>
              <input
                className="form-input"
                placeholder="Enter tracking code to confirm"
                value={trackingCode || ""}
                onChange={e => setTrackingCode(e.target.value)}
                style={{ flex: 1, fontSize: "0.875rem", padding: "0.5rem 0.75rem", minHeight: 40, minWidth: 180 }}
              />
              <button className="btn btn-primary btn-sm" onClick={() => onConfirmReceipt(order.id)}>Confirm Receipt</button>
            </div>
          )}

          {/* Feedback */}
          {(order.status === "delivered" || order.status === "completed") && !order.feedback_rating && (
            <div style={{ background: "var(--bg)", padding: "1rem", borderRadius: "var(--radius-lg)", marginBottom: "0.875rem" }}>
              <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.625rem" }}>Rate your order</div>
              <div style={{ display: "flex", gap: "0.25rem", marginBottom: "0.625rem" }}>
                {[1,2,3,4,5].map(s => (
                  <button key={s} onClick={() => setFeedbackRating(s)}
                    style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.4rem", color: s <= (feedbackRating || 0) ? "#F59E0B" : "var(--border)", transition: "color 0.1s", padding: "0 2px" }}>★</button>
                ))}
              </div>
              <textarea className="form-input" placeholder="How was your experience?" rows={2} value={feedbackComment || ""} onChange={e => setFeedbackComment(e.target.value)} style={{ fontSize: "0.8125rem" }} />
              <button className="btn btn-primary btn-sm" style={{ marginTop: "0.625rem" }} onClick={() => onFeedback(order.id)}>Submit Feedback</button>
            </div>
          )}
          {order.feedback_rating && (
            <div style={{ fontSize: "0.8125rem", color: "var(--text-2)", marginBottom: "0.875rem" }}>
               You rated this {order.feedback_rating}/5
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {order.status === "pending" && order.payment_status !== "paid" && onPayNow && (
              <button className="btn btn-primary btn-sm" onClick={() => onPayNow(order.id)}>
                Pay Now
              </button>
            )}
            {(order.status === "pending" || order.status === "processing") && (
              <button className="btn btn-danger btn-sm" onClick={() => onCancel(order.id)}>Cancel Order</button>
            )}
            <button className="btn btn-secondary btn-sm" style={{ display: "flex", alignItems: "center", gap: "0.375rem" }} onClick={() => onReport(order.id)}>
              <MessageSquare size={13} /> Report Issue
            </button>
            <button className="btn btn-secondary btn-sm" style={{ display: "flex", alignItems: "center", gap: "0.375rem" }} onClick={() => onDownload(order)}>
              <Download size={13} /> Invoice
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function OrdersPage({ orders, loading, trackingCodes, setTrackingCodes, onConfirmReceipt, onCancel, onFeedback, feedbackRatings, feedbackComments, setFeedbackRatings, setFeedbackComments, onReport, onDownload, onPayNow, setActiveTab }) {
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? orders : orders.filter(o => o.status === filter);

  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.5rem", fontWeight: 900, marginBottom: "1.25rem" }}>My Orders</h1>

      <div className="tab-bar" style={{ marginBottom: "1.5rem" }}>
        {[["all", "All"], ["pending", "Pending"], ["processing", "Processing"], ["shipped", "Shipped"], ["delivered", "Delivered"], ["cancelled", "Cancelled"]].map(([v, l]) => (
          <button key={v} className={`tab-item${filter === v ? " active" : ""}`} onClick={() => setFilter(v)}>{l}</button>
        ))}
      </div>

      {loading && (!orders || orders.length === 0) ? (
        <OrderListSkeleton />
      ) : (
        <>
          {filtered.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon"><Package size={34} strokeWidth={1.5} /></div>
              <h3>{filter === "all" ? "No orders yet" : `No ${filter} orders`}</h3>
              <p>{filter === "all" ? "Start shopping to place your first order!" : "Nothing here yet."}</p>
              {filter === "all" && <button className="btn btn-primary" onClick={() => setActiveTab("shop")}>Shop Now</button>}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {filtered.map(order => (
              <OrderCard
                key={order.id}
                order={order}
                trackingCode={trackingCodes[order.id] || ""}
                setTrackingCode={val => setTrackingCodes(prev => ({ ...prev, [order.id]: val }))}
                onConfirmReceipt={onConfirmReceipt}
                onCancel={onCancel}
                onFeedback={onFeedback}
                feedbackRating={feedbackRatings[order.id]}
                feedbackComment={feedbackComments[order.id]}
                setFeedbackRating={val => setFeedbackRatings(prev => ({ ...prev, [order.id]: val }))}
                setFeedbackComment={val => setFeedbackComments(prev => ({ ...prev, [order.id]: val }))}
                onReport={onReport}
                onDownload={onDownload}
                onPayNow={onPayNow}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
