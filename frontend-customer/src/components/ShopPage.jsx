import React, { useState, useMemo } from "react";
import { SlidersHorizontal, X, Star } from "../ui/Icon";
import ProductCard from "./ProductCard";
import { ProductGridSkeleton } from "./SkeletonLoader";

const CATEGORIES = [
  { id: "all",               label: "All" },
  { id: "favs",              label: "My Faves " },
  { id: "Pickles",           label: "Pickles " },
  { id: "Spice Powders",     label: "Spice Powders " },
  { id: "Snacks & Savories", label: "Snacks " },
  { id: "Sweets & Treats",   label: "Sweets " },
  { id: "Mixes & Instant",   label: "Mixes " },
  { id: "Special Products",  label: "Specials " },
];

const SORT_OPTIONS = [
  { value: "default",    label: "Default" },
  { value: "price_asc",  label: "Price: Low → High" },
  { value: "price_desc", label: "Price: High → Low" },
  { value: "rating",     label: "Best Rated" },
  { value: "discount",   label: "Biggest Discount" },
];

function FilterSidebar({ className = "", activeCategory, setActiveCategory, sortBy, setSortBy, priceMax, setPriceMax, showOnlyVeg, setShowOnlyVeg, spiceFilter, setSpiceFilter, ratingFilter, setRatingFilter, onReset, count, total }) {
  return (
    <div className={`filter-sidebar ${className}`.trim()}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <h3 style={{ fontSize: "1.25rem", fontWeight: 900, color: "var(--text)", margin: 0, letterSpacing: "-0.5px" }}>Filters</h3>
        <button onClick={onReset} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.8125rem", color: "var(--text-3)", textDecoration: "underline", fontWeight: 500, padding: 0 }}>Clear all</button>
      </div>

      <div className="filter-group">
        <div className="filter-group-title">Categories</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              className={`category-item${activeCategory === cat.id ? " active" : ""}`}
              onClick={() => setActiveCategory(cat.id)}
            >
              <span style={{ flex: 1 }}>{cat.label}</span>
              {activeCategory === cat.id && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />}
            </button>
          ))}
        </div>
      </div>

      

      <div className="filter-group">
        <div className="filter-group-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Max Price</span>
          <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
            <span style={{ color: "var(--text)", fontWeight: 700 }}>₹</span>
            <input
              type="number"
              className="price-input"
              value={priceMax}
              min={0}
              max={1000}
              onChange={e => {
                let val = parseInt(e.target.value) || 0;
                if (val > 1000) val = 1000;
                if (val < 0) val = 0;
                setPriceMax(val);
              }}
              style={{
                width: "60px",
                padding: "2px 6px",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                background: "var(--bg-card)",
                color: "var(--text)",
                fontWeight: 700,
                fontSize: "0.875rem",
                outline: "none"
              }}
            />
          </div>
        </div>
        <input 
          type="range" min={0} max={1000} step={50} value={priceMax}
          onChange={e => setPriceMax(Number(e.target.value))}
          className="price-slider"
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-3)", marginTop: "0.5rem" }}>
          <span>₹0</span><span>₹1000</span>
        </div>
      </div>


      <div className="filter-group">
        <div className="filter-group-title">Minimum Rating</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          {[4, 3, 2, 1].map(stars => (
            <button
              key={stars}
              className={`category-item${ratingFilter === stars ? " active" : ""}`}
              onClick={() => setRatingFilter(stars)}
              style={{ justifyContent: "flex-start", gap: "0.5rem" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "2px", flex: 1 }}>
                {stars} <Star size={14} fill="var(--warning)" color="var(--warning)" /> & Up
              </div>
              {ratingFilter === stars && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />}
            </button>
          ))}
          <button
            className={`category-item${ratingFilter === 0 ? " active" : ""}`}
            onClick={() => setRatingFilter(0)}
            style={{ justifyContent: "flex-start" }}
          >
            <span style={{ flex: 1 }}>Any Rating</span>
            {ratingFilter === 0 && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ShopPage({ menu, cart, favorites, loading, activeCategory, setActiveCategory, searchQuery, onAdd, onRemove, onToggleFav, onItemClick }) {
  const [sortBy, setSortBy] = useState("default");
  const [priceMax, setPriceMax] = useState(1000);
  const [showOnlyVeg, setShowOnlyVeg] = useState(false);
  const [spiceFilter, setSpiceFilter] = useState("all");
  const [ratingFilter, setRatingFilter] = useState(0);
  const [showMobileFilter, setShowMobileFilter] = useState(false);

  const handleReset = () => {
    setSortBy("default");
    setPriceMax(1000);
    setShowOnlyVeg(false);
    setSpiceFilter("all");
    setRatingFilter(0);
    setActiveCategory("all");
  };

  const filtered = useMemo(() => {
    let result = menu.filter(item => {
      if (activeCategory === "favs") return favorites.includes(item.id);
      if (activeCategory !== "all" && item.category !== activeCategory) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!item.name.toLowerCase().includes(q) && !(item.description || "").toLowerCase().includes(q)) return false;
      }
      if (item.price > priceMax) return false;
      if (showOnlyVeg && !item.is_veg) return false;
      if (spiceFilter !== "all" && item.spice_level !== spiceFilter) return false;
      if (ratingFilter > 0 && (parseFloat(item.average_rating) || 0) < ratingFilter) return false;
      return true;
    });

    switch (sortBy) {
      case "price_asc":  result = [...result].sort((a, b) => a.price - b.price); break;
      case "price_desc": result = [...result].sort((a, b) => b.price - a.price); break;
      case "rating":     result = [...result].sort((a, b) => (parseFloat(b.average_rating) || 0) - (parseFloat(a.average_rating) || 0)); break;
      case "discount":   result = [...result].sort((a, b) => {
        const da = a.original_price ? ((a.original_price - a.price) / a.original_price) : 0;
        const db = b.original_price ? ((b.original_price - b.price) / b.original_price) : 0;
        return db - da;
      }); break;
    }
    return result;
  }, [menu, activeCategory, favorites, searchQuery, priceMax, showOnlyVeg, spiceFilter, ratingFilter, sortBy]);

  return (
    <div className="page-content">
      {/* Mobile filter toggle */}
      <div className="mobile-only" style={{ marginBottom: "1rem" }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setShowMobileFilter(true)}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
        >
          <SlidersHorizontal size={15} /> Filters & Sort
        </button>
      </div>

      {/* Mobile filter drawer */}
      {showMobileFilter && (
        <div className="modal-overlay" onClick={() => setShowMobileFilter(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <span style={{ fontWeight: 800, fontSize: "1rem" }}>Filters</span>
              <button onClick={() => setShowMobileFilter(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-2)" }}><X size={20} /></button>
            </div>
            <FilterSidebar
              activeCategory={activeCategory} setActiveCategory={cat => { setActiveCategory(cat); setShowMobileFilter(false); }}
              sortBy={sortBy} setSortBy={setSortBy}
              priceMax={priceMax} setPriceMax={setPriceMax}
              showOnlyVeg={showOnlyVeg} setShowOnlyVeg={setShowOnlyVeg}
              spiceFilter={spiceFilter} setSpiceFilter={setSpiceFilter}
              ratingFilter={ratingFilter} setRatingFilter={setRatingFilter}
              onReset={handleReset}
              count={filtered.length} total={menu.length}
            />
          </div>
        </div>
      )}

      <div className="shop-layout">
        <div className="desktop-only" style={{ width: "240px", flexShrink: 0, position: "sticky", top: "20px", height: "calc(100vh - 120px)", overflowY: "auto", paddingRight: "1rem" }}>
          <FilterSidebar
            activeCategory={activeCategory} setActiveCategory={setActiveCategory}
            sortBy={sortBy} setSortBy={setSortBy}
            priceMax={priceMax} setPriceMax={setPriceMax}
            showOnlyVeg={showOnlyVeg} setShowOnlyVeg={setShowOnlyVeg}
            spiceFilter={spiceFilter} setSpiceFilter={setSpiceFilter}
            ratingFilter={ratingFilter} setRatingFilter={setRatingFilter}
            onReset={handleReset}
            count={filtered.length} total={menu.length}
          />
        </div>

        {/* Product grid */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <div>
              <h1 style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--text)" }}>
                {activeCategory === "all" ? "All Products" : activeCategory}
              </h1>
              {searchQuery && <p style={{ fontSize: "0.8125rem", color: "var(--text-2)", marginTop: "0.25rem" }}>Results for "{searchQuery}"</p>}
            </div>
            {/* Desktop sort */}
            <select className="form-input desktop-only" value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ width: "auto", fontSize: "0.8125rem", padding: "0.4rem 2rem 0.4rem 0.75rem", minHeight: 36 }}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>

          {loading && menu.length === 0 && <ProductGridSkeleton count={8} />}

          {!loading && filtered.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon"></div>
              <h3>No products found</h3>
              <p>Try adjusting your filters or search query</p>
              <button className="btn btn-outline" onClick={handleReset} style={{ marginTop: "0.5rem" }}>Reset Filters</button>
            </div>
          )}

          <div className="product-grid">
            {filtered.map(item => (
              <ProductCard
                key={item.id}
                item={item}
                cartQty={cart[item.id] || 0}
                isFav={favorites.includes(item.id)}
                onAdd={onAdd}
                onRemove={onRemove}
                onToggleFav={onToggleFav}
                onClick={() => onItemClick(item)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
