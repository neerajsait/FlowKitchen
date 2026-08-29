import React, { useState } from "react";
import { Plus, MessageSquare, Paperclip, X, ChevronDown, ChevronUp } from "../ui/Icon";

const ISSUE_TYPES = [
  "Wrong item received",
  "Item damaged",
  "Order not received",
  "Quality issue",
  "Payment issue",
  "Request refund",
  "Other",
];

const STATUS_COLORS = {
  open:        { bg: "#FEF3C7", color: "#854d0e" },
  in_progress: { bg: "var(--info-bg)", color: "#0e4da4" },
  resolved:    { bg: "var(--success-bg)", color: "#0a5c28" },
  closed:      { bg: "var(--bg-hover)", color: "var(--text-2)" },
};

function TicketCard({ ticket, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const sc = STATUS_COLORS[ticket.status] || STATUS_COLORS.open;

  return (
    <div className="card card-padded animate-fade-in">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.9375rem", color: "var(--text)" }}>
            {ticket.issue_type || "Support Request"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-3)", marginTop: "0.2rem" }}>
            Ticket #{ticket.id}
            {ticket.order_id ? ` · Order #${ticket.order_id}` : ""}
            {" · "}{new Date(ticket.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ display: "inline-flex", alignItems: "center", padding: "0.2rem 0.7rem", borderRadius: "var(--radius-pill)", fontSize: "0.75rem", fontWeight: 700, background: sc.bg, color: sc.color }}>
            {ticket.status?.replace("_", " ") || "Open"}
          </span>
          <button onClick={() => setExpanded(e => !e)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-2)", display: "flex", padding: "0.25rem" }}>
            {expanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: "1px solid var(--border)", marginTop: "0.875rem", paddingTop: "0.875rem" }}>
          <p style={{ fontSize: "0.875rem", color: "var(--text-2)", lineHeight: 1.6, marginBottom: "0.875rem" }}>{ticket.description}</p>

          {ticket.attachment_url && (
            <a href={ticket.attachment_url} target="_blank" rel="noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", fontSize: "0.8125rem", color: "var(--green)", textDecoration: "none", marginBottom: "0.875rem" }}>
              <Paperclip size={13} /> View Attachment
            </a>
          )}

          {ticket.admin_reply && (
            <div style={{ background: "var(--green-dim)", border: "1px solid rgba(21,148,71,0.15)", borderRadius: "var(--radius-md)", padding: "0.875rem", marginBottom: "0.875rem" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--green)", marginBottom: "0.375rem" }}>Admin Response</div>
              <p style={{ fontSize: "0.875rem", color: "var(--text)", lineHeight: 1.6 }}>{ticket.admin_reply}</p>
            </div>
          )}

          {ticket.status !== "resolved" && ticket.status !== "closed" && (
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="btn btn-secondary btn-sm" onClick={() => onEdit(ticket)}>Edit Ticket</button>
              <button className="btn btn-danger btn-sm" onClick={() => onDelete(ticket.id)}>Delete</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SupportPage({ tickets, onCreateTicket, onEditTicket, onDeleteTicket, orders }) {
  const [showForm, setShowForm] = useState(false);
  const [ticketForm, setTicketForm] = useState({ issue_type: "", description: "", order_id: "", attachment: null });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("issue_type", ticketForm.issue_type);
      formData.append("description", ticketForm.description);
      if (ticketForm.order_id) formData.append("order_id", ticketForm.order_id);
      if (ticketForm.attachment) formData.append("attachment", ticketForm.attachment);
      await onCreateTicket(formData);
      setTicketForm({ issue_type: "", description: "", order_id: "", attachment: null });
      setShowForm(false);
    } catch (err) {
      alert("Failed: " + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-content">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 900 }}>Support</h1>
        <button className="btn btn-primary btn-sm" onClick={() => setShowForm(v => !v)} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {showForm ? <><X size={15} /> Cancel</> : <><Plus size={15} /> New Ticket</>}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="card card-padded mb-lg animate-slide-up">
          <h2 style={{ fontSize: "1rem", fontWeight: 800, marginBottom: "1.25rem" }}>Create Support Ticket</h2>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <div className="form-group">
              <label className="form-label">Issue Type *</label>
              <select className="form-input" value={ticketForm.issue_type} onChange={e => setTicketForm(f => ({ ...f, issue_type: e.target.value }))} required>
                <option value="">Select issue type…</option>
                {ISSUE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Related Order (optional)</label>
              <select className="form-input" value={ticketForm.order_id} onChange={e => setTicketForm(f => ({ ...f, order_id: e.target.value }))}>
                <option value="">No specific order</option>
                {orders.map(o => <option key={o.id} value={o.id}>Order #{o.id} – {o.status}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Description *</label>
              <textarea className="form-input" placeholder="Describe the issue in detail…" rows={4} value={ticketForm.description} onChange={e => setTicketForm(f => ({ ...f, description: e.target.value }))} required />
            </div>
            <div className="form-group">
              <label className="form-label">Attachment (optional)</label>
              <input type="file" accept="image/*,application/pdf" onChange={e => setTicketForm(f => ({ ...f, attachment: e.target.files[0] || null }))}
                style={{ fontSize: "0.8125rem", color: "var(--text-2)" }} />
            </div>
            <div style={{ display: "flex", gap: "0.625rem" }}>
              <button type="submit" className="btn btn-primary btn-sm" disabled={submitting}>
                {submitting ? <><span className="spinner" /> Submitting…</> : "Submit Ticket"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Ticket list */}
      {tickets.length === 0 && !showForm && (
        <div className="empty-state" style={{ minHeight: "35vh" }}>
          <div className="empty-state-icon"><MessageSquare size={32} /></div>
          <h3>No support tickets yet</h3>
          <p>If you have an issue with your order or product, our team is here to help.</p>
          <button className="btn btn-primary" onClick={() => setShowForm(true)} style={{ marginTop: "0.5rem" }}>
            <Plus size={16} /> Create a Ticket
          </button>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
        {tickets.map(ticket => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            onEdit={(t) => {
              setTicketForm({ issue_type: t.issue_type, description: t.description, order_id: t.order_id || "", attachment: null });
              setShowForm(true);
            }}
            onDelete={onDeleteTicket}
          />
        ))}
      </div>
    </div>
  );
}
