import React from "react";
import { ChevronRight } from "../ui/Icon";
import ProductCard from "./ProductCard";

export default function ProductCarousel({ title, subtitle, items, cart, favorites, onAdd, onRemove, onToggleFav, onItemClick, onSeeAll }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="mb-2xl">
      <div className="section-header">
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="section-subtitle">{subtitle}</p>}
        </div>
        {onSeeAll && (
          <button className="section-link" onClick={onSeeAll} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            See all <ChevronRight size={14} />
          </button>
        )}
      </div>

      <div className="carousel-wrap">
        {items.map(item => (
          <div key={item.id} style={{ width: "12.5rem" }}>
            <ProductCard
              item={item}
              cartQty={cart[item.id] || 0}
              isFav={favorites.includes(item.id)}
              onAdd={onAdd}
              onRemove={onRemove}
              onToggleFav={onToggleFav}
              onClick={() => onItemClick?.(item)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
