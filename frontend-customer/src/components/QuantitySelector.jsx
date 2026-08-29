import React from "react";
import { Minus, Plus } from "../ui/Icon";

export default function QuantitySelector({ value = 1, min = 0, max = 99, onChange, size = "md" }) {
  const btnSize = size === "sm" ? 32 : 40;
  return (
    <div className="qty-selector" style={size === "sm" ? { borderRadius: "var(--radius-pill)" } : {}}>
      <button
        className="qty-btn"
        style={{ width: btnSize, height: btnSize }}
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        aria-label="Decrease quantity"
      >
        <Minus size={size === "sm" ? 12 : 16} />
      </button>
      <span className="qty-val" style={{ lineHeight: `${btnSize}px`, minWidth: size === "sm" ? 28 : 36, fontSize: size === "sm" ? "0.8125rem" : "0.9375rem" }}>
        {value}
      </span>
      <button
        className="qty-btn"
        style={{ width: btnSize, height: btnSize }}
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={value >= max}
        aria-label="Increase quantity"
      >
        <Plus size={size === "sm" ? 12 : 16} />
      </button>
    </div>
  );
}
