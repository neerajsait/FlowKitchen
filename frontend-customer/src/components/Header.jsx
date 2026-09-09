import React from "react";
import { ShoppingCart, Heart, User, Search, Home, ShoppingBag, Package, ShieldAlert, LogOut, LogIn } from "../ui/Icon";

const NAV = [
  { id: "home",     icon: Home,        label: "Home" },
  { id: "shop",     icon: ShoppingBag, label: "Shop" },
  { id: "wishlist", icon: Heart,       label: "Wishlist" },
  { id: "orders",   icon: Package,     label: "Orders" },
  { id: "tickets",  icon: ShieldAlert, label: "Support" },
  { id: "profile",  icon: User,        label: "Profile" },
];

export default function Header({ activeTab, setActiveTab, cartCount, searchQuery, setSearchQuery, onOpenCart, onLogout, currentUser }) {
  const isGuest = !currentUser;
  const filteredNav = NAV.filter(item => {
    if (isGuest && ["wishlist", "orders", "tickets", "profile"].includes(item.id)) return false;
    return true;
  });

  return (
    <header className="site-header">
      {/* Brand */}
      <div className="header-brand" style={{ cursor: "pointer" }} onClick={() => setActiveTab("home")}>
        <div className="header-brand-logo">S</div>
        <div className="desktop-only">
          <div className="header-brand-name">Suggula's</div>
          <div className="header-brand-tagline">Kitchen</div>
        </div>
      </div>

      {/* Top Nav (Desktop only) */}
      <nav className="header-nav desktop-only" aria-label="Main navigation">
        {filteredNav.map(item => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`header-nav-link${activeTab === item.id ? " active" : ""}`}
              onClick={() => setActiveTab(item.id)}
              aria-current={activeTab === item.id ? "page" : undefined}
            >
              <Icon size={20} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Search */}
      <div className="header-search">
        <Search size={16} className="header-search-icon" />
        <input
          type="text"
          placeholder="Search pickles, snacks, biscuits…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onFocus={() => setActiveTab("shop")}
        />
      </div>

      {/* Actions */}
      <div className="header-actions">
        <button
          className={`header-nav-link${activeTab === "checkout" || activeTab === "cart" ? " active" : ""}`}
          onClick={onOpenCart}
          title="Cart"
          aria-label={`Cart – ${cartCount} items`}
          style={{ position: "relative" }}
        >
          Cart
          <ShoppingCart size={20} />
          {cartCount > 0 && <span className="action-badge" style={{ top: "-6px", right: "-12px" }}>{cartCount > 9 ? "9+" : cartCount}</span>}
        </button>
        <button className="header-nav-link logout" onClick={onLogout} title={isGuest ? "Login" : "Sign Out"}>
          {isGuest ? <LogIn size={20} /> : <LogOut size={20} />}
          {isGuest ? "Login" : "Logout"}
        </button>
      </div>
    </header>
  );
}

export function MobileHeader({ searchQuery, setSearchQuery, cartCount, setActiveTab, onOpenCart }) {
  return (
    <div className="mobile-header">
      <div className="mobile-header-top">
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div className="header-brand-logo">S</div>
          <div>
            <div className="header-brand-name" style={{ fontSize: "0.9rem" }}>Suggula's Kitchen</div>
          </div>
        </div>

        {/* Right icons */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          <button
            className="header-action-btn"
            onClick={onOpenCart}
            aria-label={`Cart – ${cartCount} items`}
          >
            <ShoppingCart size={20} />
            {cartCount > 0 && <span className="action-badge">{cartCount > 9 ? "9+" : cartCount}</span>}
          </button>
        </div>
      </div>

      <div className="mobile-header-search">
        <Search size={15} className="header-search-icon" />
        <input
          type="text"
          placeholder="Search pickles, snacks, biscuits…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onFocus={() => setActiveTab("shop")}
        />
      </div>
    </div>
  );
}
