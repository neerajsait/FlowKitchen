import React from "react";

function LegalShell({ title, updated, children }) {
  return (
    <div className="page-content" style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 900, marginBottom: "0.35rem" }}>{title}</h1>
      <p style={{ fontSize: "0.8rem", color: "var(--text-3)", marginBottom: "1.75rem" }}>Last updated: {updated}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "1.4rem", lineHeight: 1.7, fontSize: "0.925rem", color: "var(--text-2)" }}>
        {children}
      </div>
    </div>
  );
}

function Sec({ h, children }) {
  return (
    <section>
      <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "1.05rem", fontWeight: 600, color: "var(--text)", margin: 0, marginBottom: "0.5rem" }}>{h}</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>{children}</div>
    </section>
  );
}

export function TermsPage({ setActiveTab }) {
  return (
    <LegalShell title="Terms of Service" updated="August 2026">
      <p>
        These terms govern your use of this food ordering platform and the related point of sale
        services operated by the store. By creating an account or placing an order, you accept them.
      </p>
      <Sec h="1. Orders and payment">
        <p>
          Prices are shown in Indian Rupees and include applicable taxes where indicated. An order is
          an offer to purchase; it becomes a binding contract when we confirm it. Online payments are
          processed by Razorpay. We never see or store your full card or UPI credentials.
        </p>
        <p>
          Cash on delivery orders are payable in full at handover. If an online payment succeeds but
          the order cannot be fulfilled, the payment is refunded to the original method within five to
          seven working days.
        </p>
      </Sec>
      <Sec h="2. Cancellation and refunds">
        <p>
          You may cancel pending or processing orders from My Orders. Prepaid amounts for cancelled
          orders are refunded to the original payment method; cash orders simply stop being prepared.
          Prepared or dispatched orders cannot be cancelled but may be reported through Support.
        </p>
      </Sec>
      <Sec h="3. Accounts">
        <p>
          Provide accurate details and keep your credentials private. You are responsible for activity
          under your account. We may suspend accounts used for fraud, abuse of promotions, or
          repeated non payment of cash orders.
        </p>
      </Sec>
      <Sec h="4. Loyalty points and coupons">
        <p>
          Loyalty points and coupons have no cash value, are per account unless stated otherwise, and
          expire according to the terms shown at issue. Points credited for delivered orders are
          reversed if an order is refunded.
        </p>
      </Sec>
      <Sec h="5. Liability">
        <p>
          The service is provided with reasonable care but without warranties beyond those required by
          law. To the extent permitted by law our liability for any claim is limited to the amount you
          paid for the affected order.
        </p>
      </Sec>
      <Sec h="6. Contact">
        <p>
          Questions about these terms can be raised through the Support section of this app, where
          tickets are reviewed by our team.
        </p>
        {setActiveTab && (
          <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab("tickets")}>Open Support</button>
        )}
      </Sec>
    </LegalShell>
  );
}

export function PrivacyPage({ setActiveTab }) {
  return (
    <LegalShell title="Privacy Policy" updated="August 2026">
      <p>
        This policy explains what personal data the platform collects, why, and the choices available
        to you.
      </p>
      <Sec h="What we collect">
        <p>
          Account data such as name, email address, phone number and delivery addresses. Order data
          including items, amounts, delivery details and payment status. Technical data such as device
          identifiers needed for sign in security and rate limiting.
        </p>
      </Sec>
      <Sec h="How we use it">
        <p>
          To prepare and deliver orders, provide support, prevent fraudulent transactions, maintain
          loyalty balances, and send transactional messages such as confirmations and delivery
          updates. Marketing messages are only sent if you opt in and can be stopped at any time.
        </p>
      </Sec>
      <Sec h="Payments">
        <p>
          Card and UPI payments are handled by Razorpay. Payment credentials go directly to Razorpay
          over encrypted connections. We retain only a payment reference, amount and status so that
          refunds and audits are possible.
        </p>
      </Sec>
      <Sec h="Sharing">
        <p>
          Data is shared only with processors that help operate the service: payment processing,
          email delivery, and infrastructure providers. It is never sold.
        </p>
      </Sec>
      <Sec h="Retention and your rights">
        <p>
          Order records are kept as long as required for tax and dispute purposes. You can access,
          correct or delete your account data from the profile screen or by raising a support ticket.
          Deletion removes personal data except records we must keep by law.
        </p>
      </Sec>
      <Sec h="Security">
        <p>
          Sessions use short lived signed tokens with server side revocation, passwords are stored
          using strong hashing, and sensitive configuration is encrypted at rest.
        </p>
      </Sec>
    </LegalShell>
  );
}

export default { TermsPage, PrivacyPage };
