import React, { useState, useEffect, useRef } from "react";
import { ChevronRight, Leaf, Award, Truck, RotateCcw } from "../ui/Icon";
import ProductCard from "./ProductCard";
import ProductCarousel from "./ProductCarousel";
import { HeroBannerSkeleton, ProductGridSkeleton } from "./SkeletonLoader";
import Rating from "./Rating";

const FALLBACK_IMG = "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=800&q=80";

const CRAVINGS = [
  { id: "Spice Powders", img: "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=200&q=80", label: "Spicy",    desc: "Bold & fiery" },
  { id: "Pickles",       img: "https://images.unsplash.com/photo-1627308595171-d1b5d6722d56?w=200&q=80", label: "Tangy",    desc: "Zesty & sour" },
  { id: "Snacks & Savories", img: "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=200&q=80", label: "Crunchy", desc: "Crisp & light" },
  { id: "Sweets & Treats",   img: "https://images.unsplash.com/photo-1599598425947-3300262b3c43?w=200&q=80", label: "Sweet",   desc: "Rich & indulgent" },
  { id: "Mixes & Instant",   img: "https://images.unsplash.com/photo-1606491956689-2ea866880c84?w=200&q=80", label: "Savoury", desc: "Quick & tasty" },
];

const CATEGORIES = [
  { id: "Pickles",          count: "24 Items", label: "Pickles",       color: "#FFF3E0", img: "https://images.unsplash.com/photo-1627308595171-d1b5d6722d56?w=100&q=80" },
  { id: "Spice Powders",    count: "18 Items", label: "Spice Powders", color: "#FCE4EC", img: "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=100&q=80" },
  { id: "Snacks & Savories",count: "32 Items", label: "Snacks",        color: "#E8F5E9", img: "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=100&q=80" },
  { id: "Sweets & Treats",  count: "15 Items", label: "Sweets",        color: "#F3E5F5", img: "https://images.unsplash.com/photo-1599598425947-3300262b3c43?w=100&q=80" },
  { id: "Mixes & Instant",  count: "12 Items", label: "Mixes",         color: "#E3F2FD", img: "https://images.unsplash.com/photo-1606491956689-2ea866880c84?w=100&q=80" },
  { id: "Special Products", count: "8 Items",  label: "Specials",      color: "#FFFDE7", img: "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=100&q=80" },
];

const TRUST_BADGES = [
  { icon: Leaf,    label: "100% Natural",     desc: "No preservatives" },
  { icon: Award,   label: "Home Made",        desc: "Traditional recipes" },
  { icon: Truck,   label: "Pan India Delivery", desc: "Free over ₹499" },
  { icon: RotateCcw, label: "Easy Returns",   desc: "7-day policy" },
];

// ── Hero Banner ──────────────────────────────────────────────
function HeroBanner({ banners, loading, onShopNow }) {
  const [idx, setIdx] = useState(0);
  const timerRef = useRef(null);

  const items = banners.length > 0 ? banners : [null];

  useEffect(() => {
    timerRef.current = setInterval(() => setIdx(p => (p + 1) % items.length), 4500);
    return () => clearInterval(timerRef.current);
  }, [items.length]);

  if (loading) return <HeroBannerSkeleton />;

  const current = items[idx];

  return (
    <div className="hero-banner mb-2xl">
      <div className="hero-banner-inner">
        <div className="hero-banner-content animate-slide-up">
          <span className="hero-banner-eyebrow">Fresh from the Kitchen</span>
          <h1 className="hero-banner-title">
            {current?.title || <>TRADITIONAL TASTE.<br />MADE FOR TODAY.</>}
          </h1>
          <p className="hero-banner-sub">
            {current?.description || "Pickles, snacks, biscuits and sweets made for every craving. Crafted with love, delivered to your door."}
          </p>
          <button className="btn btn-accent btn-lg" style={{ alignSelf: "flex-start" }} onClick={onShopNow}>
            Shop Now <ChevronRight size={18} />
          </button>
        </div>
        
        <div className="hero-banner-image-wrapper">
          {current?.image_url ? (
            <img src={current.image_url} alt={current.title || ""} className="hero-banner-bg" />
          ) : (
            <div style={{ position: "absolute", inset: 0, background: "url('https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=1200&q=60') center/cover", opacity: 0.8, zIndex: 1, width: "100%", height: "100%" }} />
          )}
        </div>
      </div>

      {items.length > 1 && (
        <div className="hero-dots">
          {items.map((_, i) => (
            <button key={i} className={`hero-dot${i === idx ? " active" : ""}`} onClick={() => setIdx(i)} aria-label={`Banner ${i + 1}`} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Craving Cards ────────────────────────────────────────────
function CravingSection({ onFilterCategory, cravingBanners = [] }) {
  const items = cravingBanners.length > 0 ? cravingBanners.map(b => ({
    id: b.target_url || "Snacks & Savories",
    img: b.image_url,
    label: b.title,
    desc: b.description
  })) : CRAVINGS;
  return (
    <div className="mb-2xl">
      <div className="section-header">
        <div>
          <h2 className="section-title">What are you craving?</h2>
          <p className="section-subtitle">Tap to find your perfect snack</p>
        </div>
      </div>
      <div className="craving-grid">
        {items.map(c => (
          <button
            key={c.id}
            onClick={() => onFilterCategory(c.id)}
            className="craving-card"
            style={{
              background: "var(--bg-card)", border: "1px solid var(--border)",
              borderRadius: "var(--radius-xl)",
              padding: "1.25rem 1rem",
              cursor: "pointer", display: "flex", flexDirection: "column",
              alignItems: "center", gap: "0.375rem", transition: "all var(--t-fast)"
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--green)"; e.currentTarget.style.boxShadow = "var(--shadow-hover)"; e.currentTarget.style.transform = "translateY(-4px)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
          >
            <img src={c.img} alt={c.label} style={{ width: 56, height: 56, borderRadius: "50%", objectFit: "cover", marginBottom: "0.375rem", boxShadow: "0 4px 10px rgba(0,0,0,0.06)" }} loading="lazy" onError={e => { e.target.src = FALLBACK_IMG; }} />
            <span style={{ fontWeight: 800, fontSize: "0.875rem", color: "var(--text)" }}>{c.label}</span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-3)", fontWeight: 500 }}>{c.desc}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Category Row ─────────────────────────────────────────────
function CategoryRow({ onSelectCategory, menu = [] }) {
  return (
    <div className="mb-2xl">
      <div className="section-header">
        <div>
          <h2 className="section-title">Browse Categories</h2>
        </div>
      </div>
      <div className="category-grid">
        {CATEGORIES.map(cat => {
          const actualCount = menu.filter(item => item.category === cat.id).length;
          return (
          <button
            key={cat.id}
            onClick={() => onSelectCategory(cat.id)}
            className="category-card"
            style={{
              background: cat.color,
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-xl)",
              padding: "1rem 0.5rem",
              cursor: "pointer", display: "flex", flexDirection: "column",
              alignItems: "center", gap: "0.25rem", transition: "transform var(--t-fast)"
            }}
            onMouseEnter={e => e.currentTarget.style.transform = "translateY(-4px)"}
            onMouseLeave={e => e.currentTarget.style.transform = "none"}
          >
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#fff", padding: 2, marginBottom: "0.375rem", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
              <img src={cat.img} alt={cat.label} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} loading="lazy" onError={e => { e.target.src = FALLBACK_IMG; }} />
            </div>
            <span style={{ fontWeight: 800, fontSize: "0.875rem", color: "var(--text)" }}>{cat.label}</span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-3)", fontWeight: 600, marginTop: "0.1rem" }}>{actualCount} Items</span>
          </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Best Seller Highlight ────────────────────────────────────
function BestSellerHighlight({ item, cartQty, isFav, onAdd, onRemove, onToggleFav, onView }) {
  if (!item) return null;
  const discount = item.original_price && item.original_price > item.price
    ? Math.round(((item.original_price - item.price) / item.original_price) * 100) : 0;

  return (
    <div className="mb-2xl">
      <div className="section-header">
        <div>
          <h2 className="section-title">Best Seller</h2>
          <p className="section-subtitle">Our most loved product this week</p>
        </div>
      </div>

      <div className="card" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden", minHeight: "17.5rem" }}>
        {/* Image */}
        <div style={{ position: "relative", overflow: "hidden", background: "var(--bg)", minHeight: "17.5rem" }}>
          <img
            src={item.image_url || FALLBACK_IMG}
            alt={item.name}
            style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            onError={e => { e.target.src = FALLBACK_IMG; }}
          />
          {discount > 0 && <span className="discount-badge" style={{ position: "absolute", top: "1rem", left: "1rem", fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}>{discount}% OFF</span>}
        </div>

        {/* Details */}
        <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "1rem", justifyContent: "center" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--green)", textTransform: "uppercase", letterSpacing: "1px" }}>
            {item.category}
          </span>
          <h3 style={{ fontSize: "1.4rem", fontWeight: 900, color: "var(--text)", lineHeight: 1.2, letterSpacing: "-0.3px" }}>
            {item.name}
          </h3>
          <Rating value={parseFloat(item.average_rating || 0)} count={item.reviews_count} size={15} />
          <p style={{ fontSize: "0.875rem", color: "var(--text-2)", lineHeight: 1.6 }}>
            {item.description?.slice(0, 120) || ""}
            {item.description?.length > 120 ? "…" : ""}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.75rem", fontWeight: 900, color: "var(--text)" }}>₹{item.price}</span>
            {item.original_price && item.original_price > item.price && (
              <span style={{ fontSize: "1rem", color: "var(--text-3)", textDecoration: "line-through" }}>₹{item.original_price}</span>
            )}
          </div>

          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            {cartQty === 0 ? (
              <button className="btn btn-primary" onClick={() => onAdd(item.id)}>Add to Cart</button>
            ) : (
              <div className="qty-selector">
                <button className="qty-btn" onClick={() => onRemove(item.id)}>−</button>
                <span className="qty-val">{cartQty}</span>
                <button className="qty-btn" onClick={() => onAdd(item.id)}>+</button>
              </div>
            )}
            <button className="btn btn-secondary" onClick={() => onView(item)}>View Details</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Brand Story (dynamic from admin) ────────────────────────
function BrandStory({ storyBanners = [] }) {
  const b = storyBanners[0]; // Use first active brand_story banner

  const title       = b?.title       || "THE TASTE OF HOME";
  const description = b?.description || "Every jar, every packet, every bite — crafted with the same love your grandmother put into her cooking. Traditional Andhra recipes, modern convenience. No shortcuts, no compromises.";
  const eyebrow     = b?.eyebrow_text || "Our Story";
  const bgColor     = b?.bg_color || null; // optional custom bg from admin
  const stats = b?.stats_json
    ? (() => { try { return JSON.parse(b.stats_json); } catch { return null; } })()
    : null;
  const defaultStats = [["35+", "Products"], ["100%", "Natural"], ["Pan India", "Delivery"]];
  const statRows = Array.isArray(stats) ? stats : defaultStats;

  return (
    <div className="mb-2xl" style={{
      background: bgColor || "linear-gradient(135deg, var(--green-dark) 0%, var(--green) 100%)",
      borderRadius: "var(--radius-2xl)",
      padding: "3rem",
      color: "#fff",
      position: "relative",
      overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: -60, right: -60, width: 240, height: 240, borderRadius: "50%", background: "rgba(199,240,0,0.08)" }} />
      <div style={{ position: "absolute", bottom: -40, left: -40, width: 180, height: 180, borderRadius: "50%", background: "rgba(255,255,255,0.04)" }} />
      {/* Optional background image overlay */}
      {b?.image_url && (
        <div style={{ position: "absolute", inset: 0, background: `url('${b.image_url}') center/cover`, opacity: 0.12, borderRadius: "var(--radius-2xl)" }} />
      )}
      <div style={{ position: "relative", zIndex: 1, maxWidth: 600 }}>
        <span style={{ display: "inline-block", background: "rgba(199,240,0,0.15)", border: "1px solid rgba(199,240,0,0.3)", color: "var(--accent)", fontSize: "0.7rem", fontWeight: 800, letterSpacing: "1.5px", textTransform: "uppercase", padding: "0.3rem 0.875rem", borderRadius: "var(--radius-pill)", marginBottom: "1.25rem" }}>
          {eyebrow}
        </span>
        <h2 style={{ fontSize: "clamp(1.75rem, 3vw, 2.5rem)", fontWeight: 900, lineHeight: 1.1, letterSpacing: "-0.5px", marginBottom: "1rem" }}>
          {title}
        </h2>
        <p style={{ fontSize: "1rem", lineHeight: 1.7, color: "rgba(255,255,255,0.8)", marginBottom: "1.75rem" }}>
          {description}
        </p>
        <div style={{ display: "flex", gap: "2.5rem", flexWrap: "wrap" }}>
          {statRows.map(([v, l]) => (
            <div key={l}>
              <div style={{ fontSize: "1.75rem", fontWeight: 900, color: "var(--accent)", lineHeight: 1 }}>{v}</div>
              <div style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.7)", marginTop: "0.25rem" }}>{l}</div>
            </div>
          ))}
        </div>
        {b?.button_text && b?.target_url && (
          <a href={b.target_url} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", marginTop: "1.5rem", background: "var(--accent)", color: "var(--green-dark)", fontWeight: 800, fontSize: "0.875rem", padding: "0.6rem 1.25rem", borderRadius: "var(--radius-pill)", textDecoration: "none" }}>
            {b.button_text} →
          </a>
        )}
      </div>
    </div>
  );
}

// ── Trust Badges ─────────────────────────────────────────────
function TrustBadges() {
  return (
    <div className="mb-2xl" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem" }}>
      {TRUST_BADGES.map(b => {
        const Icon = b.icon;
        return (
          <div key={b.label} style={{
            background: "var(--bg-card)", border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)", padding: "1.25rem",
            display: "flex", flexDirection: "column", alignItems: "center",
            gap: "0.625rem", textAlign: "center",
          }}>
            <div style={{ width: 44, height: 44, background: "var(--green-dim)", borderRadius: "var(--radius-md)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--green)" }}>
              <Icon size={20} />
            </div>
            <div style={{ fontWeight: 800, fontSize: "0.875rem", color: "var(--text)" }}>{b.label}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-2)" }}>{b.desc}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Customer Reviews ─────────────────────────────────────────
function ReviewsSection({ items }) {
  // Use the first few items' reviews if available
  const reviews = [
    { id: 1, name: "Priya R.", text: "The Kobbari Karam is absolutely authentic! Reminds me of home. ", rating: 5 },
    { id: 2, name: "Ravi K.", text: "Classic Avakaya is the best pickle I've ordered online. Fresh and perfectly spiced.", rating: 5 },
    { id: 3, name: "Ananya S.", text: "Bellam Gavvalu are so crunchy and not too sweet. My kids love them!", rating: 4 },
    { id: 4, name: "Suresh M.", text: "Quick delivery and the packaging was excellent. Will definitely order again.", rating: 5 },
  ];

  return (
    <div className="mb-2xl">
      <div className="section-header">
        <div>
          <h2 className="section-title">What Our Customers Say</h2>
          <p className="section-subtitle">Loved by families across India</p>
        </div>
      </div>
      <div className="carousel-wrap">
        {reviews.map(r => (
          <div key={r.id} className="review-card" style={{ width: "17.5rem", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <div className="review-avatar">{r.name[0]}</div>
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.875rem" }}>{r.name}</div>
                <Rating value={r.rating} size={12} showValue={false} />
              </div>
            </div>
            <p style={{ fontSize: "0.875rem", color: "var(--text-2)", lineHeight: 1.6 }}>{r.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}



// ── Main HomePage Component ───────────────────────────────────
export default function HomePage({ menu, banners, storyBanners = [], cravingBanners = [], cart, favorites, loading, onAdd, onRemove, onToggleFav, onItemClick, setActiveTab, setActiveCategory }) {

  const popularItems = [...menu]
    .sort((a, b) => (parseFloat(b.average_rating) || 0) - (parseFloat(a.average_rating) || 0))
    .slice(0, 10);

  const bestSeller = menu.find(m => m.is_best_seller) || popularItems[0] || null;

  const handleFilterCategory = (catId) => {
    setActiveCategory(catId);
    setActiveTab("shop");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div className="page-content">
        <HeroBanner banners={banners} loading={loading && menu.length === 0} onShopNow={() => setActiveTab("shop")} />
        <CravingSection onFilterCategory={handleFilterCategory} cravingBanners={cravingBanners} />
        <CategoryRow onSelectCategory={handleFilterCategory} menu={menu} />

        <ProductCarousel
          title="Popular Items"
          subtitle="Our bestselling homemade favourites"
          items={popularItems}
          cart={cart}
          favorites={favorites}
          onAdd={onAdd}
          onRemove={onRemove}
          onToggleFav={onToggleFav}
          onItemClick={onItemClick}
          onSeeAll={() => setActiveTab("shop")}
        />

        <BestSellerHighlight
          item={bestSeller}
          cartQty={bestSeller ? (cart[bestSeller.id] || 0) : 0}
          isFav={bestSeller ? favorites.includes(bestSeller.id) : false}
          onAdd={onAdd}
          onRemove={onRemove}
          onToggleFav={onToggleFav}
          onView={onItemClick}
        />

        <TrustBadges />
        <BrandStory storyBanners={storyBanners} />
        <ReviewsSection />
      </div>
    </div>
  );
}
