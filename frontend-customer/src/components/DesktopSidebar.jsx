import React from "react";
import { Home, ShoppingBag, Grid, Package, Heart, User, LogOut, ShieldAlert } from "../ui/Icon";

const NAV = [
  { id: "home",     icon: Home,        label: "Home" },
  { id: "shop",     icon: ShoppingBag, label: "Shop" },
  { id: "wishlist", icon: Heart,       label: "Wishlist" },
  { id: "orders",   icon: Package,     label: "Orders" },
  { id: "tickets",  icon: ShieldAlert, label: "Support" },
  { id: "profile",  icon: User,        label: "Profile" },
];

export default function DesktopSidebar({ activeTab, setActiveTab, cartCount, onLogout }) {
  return (
    <aside className="desk-sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-logo-box">S</div>
        <div className="sidebar-brand-text">
          <div className="sidebar-brand-name">FoodPilot</div>
          <div className="sidebar-brand-tagline">Kitchen</div>
        </div>
      </div>

      {/* Nav items */}
      <nav className="sidebar-nav" aria-label="Main navigation">
        {NAV.map(item => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`sidebar-nav-item${activeTab === item.id ? " active" : ""}`}
              onClick={() => setActiveTab(item.id)}
              aria-current={activeTab === item.id ? "page" : undefined}
            >
              <Icon size={18} />
              <span className="sidebar-label">{item.label}</span>
              {item.id === "cart" && cartCount > 0 && (
                <span className="sidebar-badge">{cartCount > 9 ? "9+" : cartCount}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom: logout */}
      <div className="sidebar-bottom">
        <button className="sidebar-nav-item" onClick={onLogout} style={{ color: "var(--error)" }}>
          <LogOut size={18} />
          <span className="sidebar-label">Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
