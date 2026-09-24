import React, { useState } from "react";
import { ArrowLeft, Heart, Share2, Plus, Minus, ShoppingCart, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from "../ui/Icon";
import Rating from "./Rating";
import PriceDisplay from "./PriceDisplay";
import ProductCard from "./ProductCard";
import { api } from "../utils/api";

const FALLBACK = "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=800&q=80";



export default function ProductDetailPage({ item, cartQty, isFav, onAdd, onRemove, onToggleFav, onBack, menu, cart, favorites, onItemClick, onGoToCart }) {
  const [activeTab, setActiveTab] = useState("ingredients");
  const carouselRef = React.useRef(null);
  const [descExpanded, setDescExpanded] = useState(false);
  const [reviews, setReviews] = useState([]);
  const [reviewsLoaded, setReviewsLoaded] = useState(false);


  React.useEffect(() => {
    const scrollContainer = document.getElementById('main-scroll-container');
    if (scrollContainer) {
      scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    if (!reviewsLoaded && item?.id) {
      api.getMenuItemReviews(item.id)
        .then(data => { setReviews(data); setReviewsLoaded(true); })
        .catch(() => setReviewsLoaded(true));
    }
  }, [item?.id]);

  if (!item) return null;

  const discount = item.original_price && item.original_price > item.price
    ? Math.round(((item.original_price - item.price) / item.original_price) * 100) : 0;

  const avgRating = reviews.length
    ? parseFloat((reviews.reduce((s, r) => s + r.rating, 0) / reviews.length).toFixed(1))
    : parseFloat(item.average_rating || 0);

  const related = React.useMemo(() => {
    if (!menu || !item) return [];
    let rel = menu.filter(m => m.category === item.category && m.id !== item.id);
    if (rel.length === 0) {
      rel = menu.filter(m => m.id !== item.id);
    }
    return [...rel].sort(() => 0.5 - Math.random()).slice(0, 8);
  }, [item?.id, menu]);

  const scrollCarousel = (dir) => {
    if (carouselRef.current) {
      carouselRef.current.scrollBy({ left: dir * 300, behavior: 'smooth' });
    }
  };
  return (
    <div>
      {/* Back button */}
      <div className="page-content" style={{ paddingBottom: 0, paddingTop: "1rem" }}>
        <button className="btn btn-ghost btn-sm" onClick={onBack} style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "1rem" }}>
          <ArrowLeft size={16} /> Back
        </button>
      </div>

      {/* Main detail */}
      <div className="page-content" style={{ paddingTop: 0 }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 300px) 1fr", gap: "2.5rem", alignItems: "start", marginBottom: "2rem", justifyContent: "center" }}>

          {/* Left: Image */}
          <div style={{ position: "relative", borderRadius: "var(--radius-2xl)", overflow: "hidden", background: "var(--bg-hover)", aspectRatio: "1", maxWidth: "300px", width: "100%", margin: "0 auto" }}>
            <img
              src={item.image_url || FALLBACK}
              alt={item.name}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
              onError={e => { e.target.src = FALLBACK; }}
            />
            {discount > 0 && <span className="discount-badge" style={{ fontSize: "0.875rem", padding: "0.375rem 0.875rem" }}>{discount}% OFF</span>}
          </div>

          {/* Right: Info */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <div>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--green)", textTransform: "uppercase", letterSpacing: "1px" }}>
                {item.category?.replace(/&amp;/g, '&')}
              </span>
              <h1 style={{ fontSize: "clamp(1.5rem, 3vw, 2rem)", fontWeight: 900, color: "var(--text)", marginTop: "0.375rem", lineHeight: 1.15, letterSpacing: "-0.3px" }}>
                {item.name}
              </h1>
            </div>

            <Rating value={avgRating} count={reviews.length || item.reviews_count} size={16} />

            <PriceDisplay price={item.price} originalPrice={item.original_price} size="lg" />

            <div>
              <p style={{
                fontSize: "0.9375rem", color: "var(--text-2)", lineHeight: 1.7,
                display: descExpanded ? "block" : "-webkit-box",
                WebkitLineClamp: descExpanded ? "unset" : 3,
                WebkitBoxOrient: "vertical",
                overflow: "hidden"
              }}>
                {item.description}
              </p>
              {item.description && item.description.length > 120 && (
                <button 
                  onClick={() => setDescExpanded(!descExpanded)} 
                  style={{ background: 'none', border: 'none', color: 'var(--green)', fontSize: '0.875rem', fontWeight: 600, padding: 0, marginTop: '0.25rem', cursor: 'pointer', transition: 'color var(--t-fast)' }}
                >
                  {descExpanded ? "Show less" : "Read more"}
                </button>
              )}
            </div>

            {/* Quantity + Add */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                {cartQty > 0 ? (
                  <>
                    <div className="qty-selector">
                      <button className="qty-btn" onClick={() => onRemove(item.id)}><Minus size={15} /></button>
                      <span className="qty-val">{cartQty}</span>
                      <button className="qty-btn" onClick={() => onAdd(item.id)}><Plus size={15} /></button>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={onGoToCart}
                    >
                      <ShoppingCart size={18} />
                      Go to Cart
                    </button>
                  </>
                ) : (
                  <button
                    className="btn btn-primary"
                    onClick={() => onAdd(item.id)}
                  >
                    <ShoppingCart size={18} />
                    Add to Cart
                  </button>
                )}
                <button
                  className={`btn btn-secondary btn-icon${isFav ? " active" : ""}`}
                  onClick={e => onToggleFav(item.id, e)}
                  aria-label="Wishlist"
                >
                  <Heart size={18} fill={isFav ? "#E91E63" : "none"} color={isFav ? "#E91E63" : "currentColor"} />
                </button>
              </div>
            </div>


          </div>
        </div>

        {/* Mobile: stack vertically (CSS handles this via media queries for the grid) */}

        {/* Horizontal Detail Tabs */}
        <div className="card mb-lg" style={{ overflow: "hidden" }}>
          <div style={{ display: "flex", borderBottom: "1px solid var(--border)", background: "var(--bg-hover)", overflowX: "auto", gap: "0.5rem" }}>
            {[
              { id: "ingredients", label: "Ingredients" },
              { id: "nutrition", label: "Nutritional Info" },
              { id: "dietary", label: "Dietary Guidelines" },
              { id: "storage", label: "Storage & Shelf Life" },
              { id: "shipping", label: "Shipping Info" }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  flex: "1 0 auto",
                  padding: "1rem 1.5rem",
                  background: activeTab === tab.id ? "var(--bg-card)" : "transparent",
                  border: "none",
                  borderBottom: activeTab === tab.id ? "2px solid var(--green)" : "2px solid transparent",
                  color: activeTab === tab.id ? "var(--green)" : "var(--text-2)",
                  fontWeight: activeTab === tab.id ? 700 : 600,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all var(--t-fast)"
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div style={{ padding: "1.5rem", fontSize: "0.875rem", color: "var(--text-2)", lineHeight: 1.7 }}>
            {activeTab === "ingredients" && <p>{item.ingredients || "Premium quality ingredients sourced from the best farms."}</p>}
            {activeTab === "nutrition" && <p>{item.nutritional_info || "Energy: 250 kcal, Protein: 5g, Carbs: 30g, Fat: 10g per 100g."}</p>}
            {activeTab === "dietary" && <p>{item.dietary_guidelines || "Suitable for vegetarians. May contain traces of nuts and dairy."}</p>}
            {activeTab === "storage" && <p>Store in a cool, dry place. Best consumed within 3 months of opening. Refrigerate after opening.</p>}
            {activeTab === "shipping" && <p>Orders ship within 1-2 business days. Free delivery on orders above ₹499. Pan-India delivery available.</p>}
          </div>
        </div>

        {/* Reviews */}
        <div className="card card-padded mb-2xl">
          <h2 className="section-title" style={{ marginBottom: "1.25rem" }}>Customer Reviews</h2>

          {reviews.length === 0 && reviewsLoaded && (
            <p style={{ color: "var(--text-2)", fontSize: "0.875rem" }}>No reviews yet. Be our first customer to give a review.</p>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: reviews.length ? "1.5rem" : "0" }}>
            {reviews.map(r => (
              <div key={r.id} className="review-card">
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <div className="review-avatar">{(r.customer_name || "C")[0]}</div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.875rem" }}>{r.customer_name || "Customer"}</div>
                    <Rating value={r.rating} size={12} showValue={false} />
                  </div>
                  <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--text-3)" }}>
                    {new Date(r.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                  </span>
                </div>
                <p style={{ fontSize: "0.875rem", color: "var(--text-2)", lineHeight: 1.6 }}>{r.comment}</p>
              </div>
            ))}
          </div>


        </div>

        {/* You may also like */}
        {related.length > 0 && (
          <div className="mb-2xl">
            <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="section-title">You May Also Like</h2>
            </div>
            <div className="carousel-wrap" ref={carouselRef}>
              {related.map(rel => (
                <div key={rel.id} style={{ width: 200, flexShrink: 0 }}>
                  <ProductCard
                    item={rel}
                    cartQty={cart[rel.id] || 0}
                    isFav={favorites.includes(rel.id)}
                    onAdd={onAdd}
                    onRemove={onRemove}
                    onToggleFav={onToggleFav}
                    onClick={() => onItemClick(rel)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Mobile sticky bottom bar */}
      <div className="mobile-only" style={{ position: "fixed", bottom: "var(--bottom-nav-h)", left: 0, right: 0, background: "var(--bg-card)", borderTop: "1px solid var(--border)", padding: "0.875rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", zIndex: 150 }}>
        <div>
          <div style={{ fontSize: "1.25rem", fontWeight: 900, color: "var(--text)" }}>₹{item.price}</div>
          {item.original_price && item.original_price > item.price && (
            <div style={{ fontSize: "0.75rem", color: "var(--text-3)", textDecoration: "line-through" }}>₹{item.original_price}</div>
          )}
        </div>
        {cartQty > 0 ? (
          <button
            className="btn btn-primary"
            style={{ flex: 1, maxWidth: 220 }}
            onClick={onGoToCart}
          >
            <ShoppingCart size={18} />
            Go to Cart ({cartQty})
          </button>
        ) : (
          <button
            className="btn btn-primary"
            style={{ flex: 1, maxWidth: 220 }}
            onClick={() => onAdd(item.id)}
          >
            <ShoppingCart size={18} />
            Add to Cart
          </button>
        )}
      </div>

      {/* Responsive styles */}
      <style>{`
        @media (max-width: 768px) {
          [style*="grid-template-columns: minmax(0, 300px) 1fr"][style*="alignItems: start"] {
            display: flex !important;
            flex-direction: column !important;
            gap: 1.5rem !important;
          }
        }
      `}</style>
    </div>
  );
}
