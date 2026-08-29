import React from 'react';
import { Archive } from '../ui/Icon';

export default function EmptyState({ title, description, icon: Icon = Archive }) {
  return (
    <div style={{ textAlign: "center", padding: "3rem", background: "var(--bg-card)", borderRadius: "var(--r-lg)", border: "1px dashed var(--border-default)" }}>
      <div style={{ display: "inline-flex", padding: "1rem", background: "var(--bg-secondary)", borderRadius: "50%", color: "var(--text-muted)", marginBottom: "1rem" }}>
        <Icon size={32} />
      </div>
      <h3 style={{ margin: "0 0 0.5rem", color: "var(--text-primary)" }}>{title}</h3>
      <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "0.9rem" }}>{description}</p>
    </div>
  );
}
