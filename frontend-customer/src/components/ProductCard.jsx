import React from "react";
import { Heart, Plus, Minus } from "../ui/Icon";
import Rating from "./Rating";
import PriceDisplay from "./PriceDisplay";

const FALLBACK = "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&q=80";

function getDiscount(price, orig) {
  if (!orig || orig <= price) return 0;
  return Math.round(((orig - price) / orig) * 100);
}

export default function ProductCard({ item, cartQty = 0, isFav = false, onAdd, onRemove, onToggleFav, onClick }) {
  const discount = getDiscount(item.price, item.original_price);
  const inCart = cartQty > 0;

  return (
    <div className="product-card animate-fade-in" onClick={onClick} role="button" tabIndex={0}
      onKeyDown={e => e.key === "Enter" && onClick?.()}>
      <div className="product-card-img-wrap">
        <img
          className="product-card-img"
          src={item.image_url || FALLBACK}
          alt={item.name}
          loading="lazy"
          onError={e => { e.target.src = FALLBACK; }}
        />
        {discount > 0 && <span className="discount-badge">{discount}% OFF</span>}
        <button
          className={`wish-btn${isFav ? " active" : ""}`}
          onClick={e => { e.stopPropagation(); onToggleFav?.(item.id, e); }}
          aria-label={isFav ? "Remove from wishlist" : "Add to wishlist"}
        >
          <Heart size={15} fill={isFav ? "currentColor" : "none"} />
        </button>
      </div>

      <div className="product-card-body">
        <div className="product-card-name">{item.name ? item.name.replace(/&amp;/g, '&') : ''}</div>
        {item.category && <div className="product-card-weight">{item.category.replace(/&amp;/g, '&')}</div>}

        <div className="rating-row" style={{ marginTop: 2 }}>
          <Rating value={parseFloat(item.average_rating || 0)} count={item.reviews_count} size={12} />
        </div>

        <div className="product-card-price-row">
          <PriceDisplay price={item.price} originalPrice={item.original_price} size="sm" showBadge={false} />
        </div>

        <div className="product-card-actions" onClick={e => e.stopPropagation()}>
          {!inCart ? (
            <button
              className="product-card-add"
              onClick={e => { e.stopPropagation(); onAdd?.(item.id); }}
              aria-label={`Add ${item.name} to cart`}
            >
              <Plus size={14} />
              Add
            </button>
          ) : (
            <div className="product-card-qty">
              <button className="product-card-qty-btn" onClick={() => onRemove?.(item.id)} aria-label="Decrease">
                <Minus size={13} />
              </button>
              <span className="product-card-qty-val">{cartQty}</span>
              <button className="product-card-qty-btn" onClick={() => onAdd?.(item.id)} aria-label="Increase">
                <Plus size={13} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
