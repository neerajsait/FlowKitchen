import React from "react";
import { Shield, FileText, RefreshCcw } from "../ui/Icon";

const policyContainerStyle = {
  maxWidth: "800px",
  margin: "0 auto",
  padding: "2rem",
};

export function TermsOfService() {
  return (
    <div className="page-content" style={policyContainerStyle}>
      <div className="card card-padded animate-fade-in" style={{ padding: "3rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 900, marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <FileText size={28} color="var(--green)" /> Terms of Service
        </h1>
        <p style={{ color: "var(--text-2)", marginBottom: "2rem" }}>Last updated: August 2026</p>
        
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", color: "var(--text)", lineHeight: 1.6 }}>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>1. Acceptance of Terms</h2>
            <p>By accessing and using FoodPilot, you accept and agree to be bound by the terms and provision of this agreement.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>2. Ordering and Payment</h2>
            <p>All orders are subject to acceptance and availability. Prices are subject to change without notice. We accept online payments and cash on delivery where specified.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>3. Delivery</h2>
            <p>We strive to deliver your food hot and fresh within the estimated delivery time. Delays may occur due to unforeseen circumstances such as weather or traffic.</p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function PrivacyPolicy() {
  return (
    <div className="page-content" style={policyContainerStyle}>
      <div className="card card-padded animate-fade-in" style={{ padding: "3rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 900, marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Shield size={28} color="var(--green)" /> Privacy Policy
        </h1>
        <p style={{ color: "var(--text-2)", marginBottom: "2rem" }}>Last updated: August 2026</p>
        
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", color: "var(--text)", lineHeight: 1.6 }}>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>1. Information We Collect</h2>
            <p>We collect information you provide directly to us, such as your name, email address, phone number, and delivery addresses.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>2. How We Use Information</h2>
            <p>We use the information we collect to provide, maintain, and improve our services, process transactions, and send you related information, including confirmations and receipts.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>3. Data Security</h2>
            <p>We implement appropriate security measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction.</p>
          </section>
        </div>
      </div>
    </div>
  );
}

export function RefundPolicy() {
  return (
    <div className="page-content" style={policyContainerStyle}>
      <div className="card card-padded animate-fade-in" style={{ padding: "3rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 900, marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <RefreshCcw size={28} color="var(--green)" /> Refund Policy
        </h1>
        <p style={{ color: "var(--text-2)", marginBottom: "2rem" }}>Last updated: August 2026</p>
        
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", color: "var(--text)", lineHeight: 1.6 }}>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>1. Order Cancellations</h2>
            <p>You may cancel your order within 5 minutes of placing it for a full refund. Once preparation has begun, orders cannot be cancelled.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>2. Defective or Incorrect Items</h2>
            <p>If you receive an incorrect or substandard order, please contact our support team immediately. We will issue a replacement or a full refund depending on the situation.</p>
          </section>
          <section>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "0.5rem" }}>3. Refund Processing</h2>
            <p>Refunds will be processed back to the original method of payment within 3-5 business days.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
