import React from "react";
import { User, Lock, MapPin, Star, Trash2, Edit2, LogOut } from "../ui/Icon";

export default function ProfilePage({
  user, isEditingProfile, setIsEditingProfile, profileForm, setProfileForm,
  handleUpdateProfile, profileUpdating,
  isEditingPassword, setIsEditingPassword, passwordForm, setPasswordForm,
  otpRequested, handleRequestOtp, handleChangePassword, passwordUpdating,
  addresses, selectedAddressId, setSelectedAddressId, setCheckoutAddress,
  newAddrVal, setNewAddrVal, newAddrLabel, setNewAddrLabel,
  showAddressManager, setShowAddressManager, handleAddAddress, handleDeleteAddress,
  myReviews, handleDeleteMyReview,
  loyaltyPoints, storeSettings, isLoyaltyEnabled, onDeleteAccount, onLogout
}) {
  if (!user) return null;

  const redeemRate = parseFloat(storeSettings?.loyalty_redeem_rate || "0.01");
  const displayName = user.full_name || user.email?.split("@")[0] || "You";
  const initials = displayName.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.5rem", fontWeight: 900, marginBottom: "1.5rem" }}>My Profile</h1>

      {/* Loyalty Card */}
      {isLoyaltyEnabled && (
        <div className="loyalty-card" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.25rem" }}>
            <div style={{ width: 56, height: 56, background: "rgba(255,255,255,0.15)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.25rem", fontWeight: 900, color: "#fff", flexShrink: 0 }}>
              {initials}
            </div>
            <div>
              <div style={{ color: "#fff", fontWeight: 900, fontSize: "1.1rem" }}>{displayName}</div>
              <div style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.8125rem" }}>{user.email}</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: "2rem" }}>
            <div>
              <div className="loyalty-points-big">{loyaltyPoints || 0}</div>
              <div style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.65)", marginTop: "0.25rem" }}>Loyalty Points</div>
            </div>
            <div>
              <div style={{ fontSize: "1.5rem", fontWeight: 900, color: "var(--accent)" }}>₹{((loyaltyPoints || 0) * redeemRate).toFixed(2)}</div>
              <div style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.65)", marginTop: "0.25rem" }}>Redeemable Value</div>
            </div>
          </div>
        </div>
      )}

      {/* Profile Info */}
      <div className="card card-padded mb-lg">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 800, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <User size={17} color="var(--green)" /> Personal Info
          </h2>
          {!isEditingProfile && (
            <button className="btn btn-ghost btn-sm" onClick={() => {
              setProfileForm({ full_name: user.full_name || "", phone: user.phone || "", address: user.address || "" });
              setIsEditingProfile(true);
            }} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
              <Edit2 size={13} /> Edit
            </button>
          )}
        </div>

        {!isEditingProfile ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {[["Full Name", user.full_name || "—"], ["Email", user.email], ["Phone", user.phone || "—"]].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "0.25rem" }}>{label}</div>
                <div style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--text)" }}>{val}</div>
              </div>
            ))}
          </div>
        ) : (
          <form onSubmit={handleUpdateProfile} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.875rem" }}>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input className="form-input" value={profileForm.full_name} onChange={e => setProfileForm(f => ({ ...f, full_name: e.target.value }))} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Phone</label>
              <input className="form-input" type="tel" value={profileForm.phone} onChange={e => setProfileForm(f => ({ ...f, phone: e.target.value }))} />
            </div>
            <div style={{ display: "flex", gap: "0.625rem" }}>
              <button type="submit" className="btn btn-primary btn-sm" disabled={profileUpdating}>
                {profileUpdating ? <><span className="spinner" /> Saving…</> : "Save Changes"}
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIsEditingProfile(false)}>Cancel</button>
            </div>
          </form>
        )}
      </div>

      {/* Password Change */}
      <div className="card card-padded mb-lg">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 800, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Lock size={17} color="var(--green)" /> Password
          </h2>
          {!isEditingPassword && (
            <button className="btn btn-ghost btn-sm" onClick={() => setIsEditingPassword(true)} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
              <Edit2 size={13} /> Change
            </button>
          )}
        </div>

        {isEditingPassword && (
          !otpRequested ? (
            <form onSubmit={handleRequestOtp} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              <div className="form-group">
                <label className="form-label">Current Password</label>
                <input type="password" className="form-input" value={passwordForm.old_password} onChange={e => setPasswordForm(f => ({ ...f, old_password: e.target.value }))} required />
              </div>
              <div style={{ display: "flex", gap: "0.625rem" }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={passwordUpdating}>
                  {passwordUpdating ? "Sending…" : "Request OTP"}
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setIsEditingPassword(false); setPasswordForm({ old_password: "", otp: "", new_password: "" }); }}>Cancel</button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleChangePassword} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              <div className="form-group">
                <label className="form-label">OTP (sent to email)</label>
                <input className="form-input" placeholder="Enter OTP" value={passwordForm.otp} onChange={e => setPasswordForm(f => ({ ...f, otp: e.target.value }))} required />
              </div>
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input type="password" className="form-input" value={passwordForm.new_password} onChange={e => setPasswordForm(f => ({ ...f, new_password: e.target.value }))} required />
              </div>
              <div style={{ display: "flex", gap: "0.625rem" }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={passwordUpdating}>
                  {passwordUpdating ? "Changing…" : "Change Password"}
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIsEditingPassword(false)}>Cancel</button>
              </div>
            </form>
          )
        )}
        {!isEditingPassword && <p style={{ fontSize: "0.8125rem", color: "var(--text-3)" }}>••••••••••••</p>}
      </div>

      {/* Addresses */}
      <div className="card card-padded mb-lg">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 800, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <MapPin size={17} color="var(--green)" /> Saved Addresses
          </h2>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowAddressManager(v => !v)}>
            {showAddressManager ? "Cancel" : "+ Add"}
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem", marginBottom: showAddressManager ? "1rem" : 0 }}>
          {addresses.map(addr => (
            <div key={addr.id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", background: "var(--bg)", borderRadius: "var(--radius-md)" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: "0.8125rem", marginBottom: "0.2rem" }}>{addr.label || "Address"}</div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>{addr.address_line}</div>
              </div>
              <button onClick={e => handleDeleteAddress(addr.id, e)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: "0.25rem" }}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        {showAddressManager && (
          <form onSubmit={handleAddAddress} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div className="form-group">
              <label className="form-label">Label</label>
              <select className="form-input" value={newAddrLabel} onChange={e => setNewAddrLabel(e.target.value)}>
                <option>Home</option><option>Work</option><option>Other</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Address</label>
              <textarea className="form-input" rows={2} value={newAddrVal} onChange={e => setNewAddrVal(e.target.value)} required />
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button type="submit" className="btn btn-primary btn-sm">Save</button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowAddressManager(false)}>Cancel</button>
            </div>
          </form>
        )}
      </div>

      {/* My Reviews */}
      {myReviews?.length > 0 && (
        <div className="card card-padded mb-lg">
          <h2 style={{ fontSize: "1rem", fontWeight: 800, marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Star size={17} color="var(--green)" /> My Reviews
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {myReviews.map(r => (
              <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.75rem", padding: "0.875rem", background: "var(--bg)", borderRadius: "var(--radius-md)" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.2rem" }}>{r.menu_item_name}</div>
                  <div style={{ display: "flex", gap: "2px", color: "#F59E0B", fontSize: "0.875rem", marginBottom: "0.25rem" }}>{"★".repeat(r.rating)}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>{r.comment}</div>
                </div>
                <button onClick={() => handleDeleteMyReview(r.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: "0.25rem", flexShrink: 0 }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Danger zone */}
      <div className="card card-padded" style={{ border: "1px solid var(--error-bg)" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 800, color: "var(--error)", marginBottom: "0.875rem" }}>Account Settings</h2>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button className="btn btn-ghost btn-sm" onClick={onLogout} style={{ display: "flex", alignItems: "center", gap: "0.375rem", color: "var(--text-2)" }}>
            <LogOut size={14} /> Sign Out
          </button>
          <button className="btn btn-danger btn-sm" onClick={onDeleteAccount} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
            <Trash2 size={14} /> Delete Account
          </button>
        </div>
      </div>
    </div>
  );
}
