import React from "react";

export default function PriceDisplay({ price, originalPrice, size = "md", showBadge = true }) {
  const discount = originalPrice && originalPrice > price
    ? Math.round(((originalPrice - price) / originalPrice) * 100)
    : 0;

  const sizes = {
    sm: { price: "0.875rem", orig: "0.75rem" },
    md: { price: "1rem",     orig: "0.8125rem" },
    lg: { price: "1.5rem",   orig: "1rem" },
    xl: { price: "2rem",     orig: "1.125rem" },
  };

  const s = sizes[size] || sizes.md;

  return (
    <div className="flex items-center gap-sm flex-wrap">
      <span className="price-current" style={{ fontSize: s.price }}>₹{price}</span>
      {originalPrice && originalPrice > price && (
        <span className="price-original" style={{ fontSize: s.orig }}>₹{originalPrice}</span>
      )}
      {discount > 0 && showBadge && (
        <span className="price-badge">{discount}% off</span>
      )}
    </div>
  );
}
