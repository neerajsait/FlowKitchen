import React from 'react';
import { Ghost, Search, MapPin, Package, MessageSquare } from '../ui/Icon';

const icons = {
  ghost: Ghost,
  search: Search,
  mapPin: MapPin,
  package: Package,
  message: MessageSquare
};

export default function EmptyState({ 
  icon = "ghost", 
  title = "No data found", 
  message = "There's nothing to show here right now.",
  action = null
}) {
  const Icon = icons[icon] || Ghost;
  return (
    <div style={{ textAlign: "center", padding: "4rem 2rem", color: "var(--text-muted)" }}>
      <div style={{ width: 64, height: 64, background: "var(--bg-hover)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.5rem" }}>
        <Icon size={28} style={{ opacity: 0.6 }} />
      </div>
      <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
        {title}
      </h3>
      <p style={{ fontSize: "0.85rem", maxWidth: "300px", margin: "0 auto", lineHeight: 1.5 }}>
        {message}
      </p>
      {action && (
        <div style={{ marginTop: "1.5rem" }}>
          {action}
        </div>
      )}
    </div>
  );
}
