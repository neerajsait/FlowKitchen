import React from "react";
import { Star, StarHalf } from "../ui/Icon";

export default function Rating({ value = 0, count = null, size = 14, showValue = true, interactive = false, onRate = null }) {
  if (!interactive && value === 0) {
    return (
      <div className="rating-row" style={{ color: "var(--text-3)", fontSize: "0.8125rem", fontStyle: "italic" }}>
        No ratings yet
      </div>
    );
  }

  const full  = Math.floor(value);
  const half  = value - full >= 0.5;
  const empty = Math.max(0, 5 - full - (half ? 1 : 0));

  if (interactive) {
    return (
      <div className="stars" style={{ gap: 4 }}>
        {[1, 2, 3, 4, 5].map(i => (
          <button
            key={i}
            onClick={() => onRate?.(i)}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 2, color: i <= value ? "#F59E0B" : "var(--border)", transition: "color 0.15s" }}
          >
            <Star size={size + 4} fill={i <= value ? "#F59E0B" : "none"} strokeWidth={1.5} />
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="rating-row">
      <div className="stars">
        {[...Array(full)].map((_, i) => <Star key={`f${i}`} size={size} fill="currentColor" strokeWidth={0} />)}
        {half && <StarHalf size={size} fill="currentColor" strokeWidth={0} />}
        {[...Array(empty)].map((_, i) => <Star key={`e${i}`} size={size} strokeWidth={1.5} className="stars-empty" />)}
      </div>
      {showValue && value > 0 && <span className="rating-val">{value}</span>}
      {count != null && <span className="rating-count">({count})</span>}
    </div>
  );
}
