import React from "react";

export function ProductCardSkeleton() {
  return (
    <div className="product-card" style={{ cursor: "default" }}>
      <div className="skeleton skeleton-img" />
      <div style={{ padding: "0.875rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-text" style={{ width: "50%" }} />
        <div className="skeleton skeleton-text" style={{ width: "60%" }} />
        <div className="skeleton skeleton-btn" style={{ marginTop: "0.25rem" }} />
      </div>
    </div>
  );
}

export function ProductGridSkeleton({ count = 8 }) {
  return (
    <div className="product-grid">
      {Array.from({ length: count }).map((_, i) => <ProductCardSkeleton key={i} />)}
    </div>
  );
}

export function CategoryRowSkeleton({ count = 6 }) {
  return (
    <div className="carousel-wrap">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ width: 100, flexShrink: 0 }}>
          <div className="skeleton" style={{ width: 100, height: 100, borderRadius: "var(--radius-xl)" }} />
          <div className="skeleton skeleton-text" style={{ width: 80, marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}

export function HeroBannerSkeleton() {
  return <div className="skeleton" style={{ width: "100%", height: 320, borderRadius: "var(--radius-2xl)" }} />;
}

export function InlineLoader({ text = "Loading…" }) {
  return (
    <div className="page-loading">
      <div className="spinner spinner-green" style={{ width: 32, height: 32, borderWidth: 3 }} />
      <span style={{ fontSize: "0.875rem", color: "var(--text-2)" }}>{text}</span>
    </div>
  );
}

export function OrderCardSkeleton() {
  return (
    <div className="order-card" style={{ cursor: "default" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="skeleton skeleton-title" style={{ width: 120 }} />
        <div className="skeleton skeleton-text" style={{ width: 70 }} />
      </div>
      <div className="skeleton skeleton-text" style={{ width: "55%", marginTop: "0.9rem" }} />
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton skeleton-btn" style={{ width: 92, height: 34 }} />
        ))}
      </div>
    </div>
  );
}

export function OrderListSkeleton({ count = 3 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {Array.from({ length: count }).map((_, i) => <OrderCardSkeleton key={i} />)}
    </div>
  );
}
