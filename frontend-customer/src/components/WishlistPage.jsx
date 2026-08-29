import React from "react";
import ProductCard from "./ProductCard";

export default function WishlistPage({ menu, favorites, cart, onAdd, onRemove, onToggleFav, onItemClick, setActiveTab }) {
  const wishlistItems = menu.filter(m => favorites.includes(m.id));

  if (wishlistItems.length === 0) {
    return (
      <div className="page-content">
        <h1 style={{ fontSize: "1.5rem", fontWeight: 900, marginBottom: "1.5rem" }}>My Wishlist</h1>
        <div className="empty-state" style={{ minHeight: "40vh" }}>
          <div className="empty-state-icon"></div>
          <h3>Nothing saved yet</h3>
          <p>Tap the heart on any product to add it to your wishlist.</p>
          <button className="btn btn-primary" onClick={() => setActiveTab("shop")} style={{ marginTop: "0.5rem" }}>Browse Products</button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-content">
      <div className="section-header" style={{ marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 900 }}>My Wishlist</h1>
          <p className="section-subtitle">{wishlistItems.length} item{wishlistItems.length !== 1 ? "s" : ""} saved</p>
        </div>
      </div>

      <div className="product-grid">
        {wishlistItems.map(item => (
          <ProductCard
            key={item.id}
            item={item}
            cartQty={cart[item.id] || 0}
            isFav
            onAdd={onAdd}
            onRemove={onRemove}
            onToggleFav={onToggleFav}
            onClick={() => onItemClick(item)}
          />
        ))}
      </div>
    </div>
  );
}
