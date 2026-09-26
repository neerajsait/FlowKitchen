// API client for communicating with the Flask backend.

export const API_BASE_URL = import.meta.env.VITE_API_URL || (
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? `${window.location.protocol}//${window.location.hostname}:5000/api`
    : `${window.location.protocol}//${window.location.host}/api`
);


const originalFetch = window.fetch;
let isRefreshing = false;
let refreshPromise = null;

let accessToken = null;

export function getAccessToken() {
  return accessToken;
}

function setAccessToken(token) {
  accessToken = token || null;
}

function clearAccessToken() {
  accessToken = null;
}

window.fetch = async (url, options) => {
  const isApiCall = typeof url === 'string' && url.includes(API_BASE_URL);
  if (isApiCall) {
    // Always send credentials so the HttpOnly auth cookies flow.
    options = { credentials: "include", headers: {}, ...(options || {}) };
    const method = (options.method || "GET").toUpperCase();
    if (method === "GET") {
      const sep = url.includes('?') ? '&' : '?';
      url = `${url}${sep}_t=${Date.now()}`;
    } else {
      // Double-submit CSRF for cookie-authenticated mutations: echo the
      // readable csrf_access_token cookie in a custom header.
      const m = document.cookie.match(/(?:^|;\s*)csrf_access_token=([^;]+)/);
      if (m && !options.headers["X-CSRF-TOKEN"]) {
        options.headers["X-CSRF-TOKEN"] = decodeURIComponent(m[1]);
      }
    }
  }
  
  let res = await originalFetch(url, options);
  
  if (res.status === 401 && isApiCall && !url.includes('/api/auth/login') && !url.includes('/api/auth/refresh')) {
    // The refresh token lives in an HttpOnly cookie - just POST /auth/refresh.
    if (!isRefreshing) {
      isRefreshing = true;
      const refreshUrl = API_BASE_URL.replace(/\/?$/, '/auth/refresh');
      refreshPromise = originalFetch(refreshUrl, {
        method: "POST",
        credentials: "include"
      }).then(async refreshRes => {
        isRefreshing = false;
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          setAccessToken(data.access_token);
          return data.access_token;
        } else {
          clearAccessToken();
          sessionStorage.removeItem("token"); // legacy cleanup
          window.location.href = "/login";
          throw new Error("Session expired");
        }
      }).catch(err => {
        isRefreshing = false;
        clearAccessToken();
        sessionStorage.removeItem("token"); // legacy cleanup
        window.location.href = "/login";
        throw err;
      });
    }
    
    const newToken = await refreshPromise;
    if (newToken) {
      // Retry original request
      const newOptions = { ...options };
      newOptions.headers = { ...newOptions.headers, "Authorization": `Bearer ${newToken}` };
      res = await originalFetch(url, newOptions);
    }
  }
  
  return res;
};
// Helper to retrieve auth tokens
function getAuthHeader() {
  return accessToken ? { "Authorization": `Bearer ${accessToken}` } : {};
}

// Safe JSON parser — never crashes on HTML responses (e.g. 502 gateway, Vite fallback)
async function safeJson(res) {
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    // const text = await res.text();
    // Backend returned HTML — means server is down or misconfigured
    throw new Error(
      res.status === 404
        ? "API endpoint not found (404). Please restart the backend."
        : `Server returned non-JSON response (status ${res.status}). Make sure the backend is running on port 5000.`
    );
  }
  return res.json();
}

// ----------------------------------------------------------------
// Exportable API client
// ----------------------------------------------------------------
export const api = {
  getAccessToken,
  // Ping the backend health endpoint; result drives the status banner in the UI
  async getMode() {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      return res.ok ? "Live Backend" : "Server Offline";
    } catch (err) {
      return "Server Offline";
    }
  },

  async register(email, password, role, first_name = "", last_name = "", phone = "", outlet_id = null) {

    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role, first_name, last_name, phone, outlet_id: outlet_id ? parseInt(outlet_id) : null })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Registration failed");
    return data;
  },

  async login(payload) {

    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Login failed");
    setAccessToken(data.access_token);   // memory only - never persisted
    sessionStorage.removeItem("token");  // legacy cleanup
    // Refresh token arrives as an HttpOnly cookie - never stored client-side.
    sessionStorage.setItem("user", JSON.stringify(data.user));
    return data;
  },

  async logout() {
    try {
      const userStr = sessionStorage.getItem("user");
      if (userStr) {
        const user = JSON.parse(userStr);
        if (['staff', 'kitchen', 'outlet_owner'].includes(user.role)) {
          // Fire and forget auto-clockout
          fetch(`${API_BASE_URL}/pos/shift/clock-out`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...getAuthHeader()
            },
            body: JSON.stringify({}) // Backend defaults actual_cash to expected_cash
          }).catch(() => {});
        }
      }
    } catch(e) {}
    
    try {
      const res = await originalFetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({})
      });
      if (!res.ok) {
        console.warn("Backend logout returned non-OK status. Session might remain active on server.");
      }
    } catch (e) {
      console.error("Logout failed:", e);
      console.warn("Warning: Could not reach the server to securely log out. Local session cleared, but remote session may remain active.");
    }

    clearAccessToken();
    sessionStorage.removeItem("token"); // legacy cleanup
    sessionStorage.removeItem("refresh_token");
    sessionStorage.removeItem("user");
    window.location.href = "/login";
  },

  getCurrentUser() {
    const userStr = sessionStorage.getItem("user");
    return userStr ? JSON.parse(userStr) : null;
  },

  async verifyEmail(token) {
    const res = await fetch(`${API_BASE_URL}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to verify email");
    return data;
  },

  // Silently restore an access token into memory after a page reload using
  // the HttpOnly refresh cookie. Returns true when a usable session exists.
  async ensureSession() {
    if (accessToken) return true;
    if (!sessionStorage.getItem("user")) return false; // no known identity
    try {
      const res = await originalFetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include"
      });
      if (!res.ok) return false;
      const data = await safeJson(res);
      setAccessToken(data.access_token);
      return true;
    } catch (err) {
      return false;
    }
  },

  async getMe() {
    if (!accessToken) throw new Error("No token");

    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      method: "GET",
      headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (data.user) {
      sessionStorage.setItem("user", JSON.stringify(data.user));
      return data.user;
    } else if (data.id) {
      sessionStorage.setItem("user", JSON.stringify(data));
      return data;
    }
    return null;
  },

  // -----------------------
  // B2C Customer Endpoints
  // -----------------------
  async getFoodsMenu() {

    const res = await fetch(`${API_BASE_URL}/foods/menu`);
    if (!res.ok) throw new Error("Failed to load menu");
    return safeJson(res);
  },

  async placeOrder(items, deliveryAddress, paymentMethod = "COD", couponCode = null, redeemLoyaltyPoints = 0, deliveryCharge = 0) {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    const res = await fetch(`${API_BASE_URL}/foods/order`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ items, delivery_address: deliveryAddress, payment_method: paymentMethod, coupon_code: couponCode, redeem_loyalty_points: redeemLoyaltyPoints, delivery_charge: deliveryCharge })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to place order");
    return data;
  },

  async getOrderHistory() {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    // FIX: Correct endpoint is /foods/orders (not /foods/orders/history)
    const res = await fetch(`${API_BASE_URL}/foods/orders`, {
      headers: getAuthHeader()
    });
    if (!res.ok) throw new Error("Failed to load order history");
    return safeJson(res);
  },

  async confirmReceipt(orderId, trackingCode) {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    const res = await fetch(`${API_BASE_URL}/foods/orders/${orderId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ tracking_code: trackingCode })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Confirmation failed");
    return data;
  },

  async submitFeedback(orderId, rating, comment) {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    const res = await fetch(`${API_BASE_URL}/foods/orders/${orderId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ rating: parseInt(rating), comment })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Feedback submission failed");
    return data;
  },

  // -----------------------
  // POS Staff Endpoints
  // -----------------------
  async getPOSMenu() {

    // FIX: Correct endpoint is /pos/menu
    const res = await fetch(`${API_BASE_URL}/pos/menu`, { headers: getAuthHeader(), cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load POS menu");
    return safeJson(res);
  },

  async posSell(items, paymentMethod, couponCode = null) {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    // FIX: Correct endpoint is /pos/sell
    const res = await fetch(`${API_BASE_URL}/pos/sell`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ items, payment_method: paymentMethod, coupon_code: couponCode })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "POS transaction failed");
    return data;
  },

  // -----------------------
  // Admin Endpoints
  // -----------------------
  async adminGetOrders() {

    const res = await fetch(`${API_BASE_URL}/admin/orders`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to fetch order queue");
    return safeJson(res);
  },

  async adminShipOrder(orderId, trackingCode, trackingLabel = null, trackingLink = null) {

    // FIX: Correct endpoint is /admin/orders/<id>/ship (PUT)
    const res = await fetch(`${API_BASE_URL}/admin/orders/${orderId}/ship`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ tracking_code: trackingCode, tracking_label: trackingLabel, tracking_link: trackingLink })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to update ship status");
    return data;
  },

  async adminGetOutlets() {

    const res = await fetch(`${API_BASE_URL}/admin/outlets`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load outlets list");
    return safeJson(res);
  },

  async posGetMyOutlet() {

    const res = await fetch(`${API_BASE_URL}/pos/outlet`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load assigned outlet info");
    return safeJson(res);
  },

  async adminUpdateOutlet(outletId, data) {

    const res = await fetch(`${API_BASE_URL}/admin/outlets/${outletId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to update outlet");
    return result;
  },

  async adminDeleteOutlet(outletId) {
    const res = await fetch(`${API_BASE_URL}/admin/outlets/${outletId}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to delete outlet");
    return result;
  },

  async getFoodByCode(code) {
    const res = await fetch(`${API_BASE_URL}/foods/menu/code/${encodeURIComponent(code)}`);
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || "Item not found");
    return result;
  },

  async adminAddMenuItem(data) {

    const res = await fetch(`${API_BASE_URL}/admin/menu`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to add menu item");
    return result;
  },

  async adminUpdateMenuItem(itemId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/menu/${itemId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to update menu item");
    return result;
  },

  async adminDeleteMenuItem(itemId) {
    const res = await fetch(`${API_BASE_URL}/admin/menu/${itemId}`, {
      method: "POST", // POST to bypass 405 Method Not Allowed proxy errors
      headers: getAuthHeader()
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to delete menu item");
    return result;
  },

  async adminGetCategories() {
    const res = await fetch(`${API_BASE_URL}/admin/categories`, { headers: getAuthHeader(), cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load categories");
    return safeJson(res);
  },

  async adminAddCategory(name) {
    const res = await fetch(`${API_BASE_URL}/admin/categories`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ name })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to add category");
    return result;
  },

  async adminDeleteCategory(catId) {
    const res = await fetch(`${API_BASE_URL}/admin/categories/${catId}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to delete category");
    return result;
  },

  async adminGetMenuItems() {

    const res = await fetch(`${API_BASE_URL}/admin/menu`, { headers: getAuthHeader(), cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load admin menu catalog");
    return safeJson(res);
  },

  async adminAssignItemToOutlet(outletId, menuItemId, currentStock, restockLimit) {

    // FIX: Correct endpoint is /admin/outlets/<id>/items (POST)
    const res = await fetch(`${API_BASE_URL}/admin/outlets/${outletId}/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({
        menu_item_id: parseInt(menuItemId),
        current_stock: parseInt(currentStock),
        restock_limit: parseInt(restockLimit)
      })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to assign item");
    return result;
  },

  async adminRemoveItemFromOutlet(outletId, menuItemId) {

    // FIX: Correct endpoint is DELETE /admin/outlets/<id>/items/<mid>
    const res = await fetch(`${API_BASE_URL}/admin/outlets/${outletId}/items/${menuItemId}`, {
      method: "DELETE",
      headers: { ...getAuthHeader() }
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to remove item");
    return result;
  },

  async adminGenerateQR(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/generate-qr`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to generate QR");
    return data;
  },

  async posScanArrival(qrData) {

    let payload;
    try {
      payload = JSON.parse(qrData);
    } catch (err) {
      throw new Error("Invalid QR code Ã¢€â€ not a dispatch label.");
    }

    const res = await fetch(`${API_BASE_URL}/pos/scan-arrival`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({
        qr_data: qrData,
        batch_number: payload.batch_number || null,
        expiry_date: payload.expiry_date || null
      })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Scan failed");
    return data;
  },

  async adminGetRevenueShare() {
    const res = await fetch(`${API_BASE_URL}/admin/revenue-share`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load revenue share");
    return safeJson(res);
  },

  async adminGetAnalytics() {

    const res = await fetch(`${API_BASE_URL}/admin/analytics`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load analytics");
    return safeJson(res);
  },

  async posGetMyShifts() {
    const res = await fetch(`${API_BASE_URL}/pos/my-shifts`, {
      headers: getAuthHeader()
    });
    return safeJson(res);
  },

  async adminGetAuditLogs(page = 1, perPage = 50) {

    const res = await fetch(`${API_BASE_URL}/admin/audit-log?page=${page}&per_page=${perPage}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load audit logs");
    return safeJson(res);
  },

  async posLogDisposal(menuItemId, qty, reason) {
    const user = this.getCurrentUser();

    const res = await fetch(`${API_BASE_URL}/pos/disposal`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ menu_item_id: parseInt(menuItemId), quantity: parseInt(qty), reason })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to log disposal");
    return data;
  },

  async ownerGetDashboard() {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/owner/dashboard`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load owner dashboard");
    return safeJson(res);
  },

  async ownerCreateOutlet(payload) {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/owner/outlets`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to create outlet");
    return data;
  },

  async ownerEditOutlet(outletId, payload) {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/owner/outlets/${outletId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to edit outlet");
    return data;
  },

  async ownerGetStock(outletId) {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/owner/outlets/${outletId}/stock`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load outlet stock");
    return safeJson(res);
  },

  async forgotPassword(email) {
    const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Request failed");
    return result;
  },

  async resetPassword(email, token, newPassword) {
    const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, token, new_password: newPassword })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Reset failed");
    return result;
  },

  async changePassword(newPassword) {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ new_password: newPassword })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Change failed");

    if (user) {
      user.is_first_login = false;
      sessionStorage.setItem("user", JSON.stringify(user));
    }
    return result;
  },

  async updateProfile(data) {
    const currentUser = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/auth/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Profile update failed");
    if (result.user) {
      sessionStorage.setItem("user", JSON.stringify(result.user));
    }
    return result;
  },

  async getLoyaltyHistory() {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/customer/loyalty`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load loyalty data");
    return safeJson(res);
  },

  async adminGetUsers() {
    const res = await fetch(`${API_BASE_URL}/admin/staff`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load users");
    return safeJson(res);
  },

  async adminCreateUser(data) {
    const res = await fetch(`${API_BASE_URL}/admin/staff`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to create user");
    return result;
  },

  async adminUpdateUser(userId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/staff/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to update user");
    return result;
  },

  async adminDeleteUser(userId) {
    const res = await fetch(`${API_BASE_URL}/admin/staff/${userId}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to delete user");
    return result;
  },

  async validateCoupon(code) {
    const res = await fetch(`${API_BASE_URL}/coupons/${code}`);
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Invalid coupon");
    return data;
  },

  async getActiveCoupons() {
    const res = await fetch(`${API_BASE_URL}/coupons/active`);
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to fetch active coupons");
    return data;
  },

  async adminGetCoupons() {
    const res = await fetch(`${API_BASE_URL}/admin/coupons`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load coupons");
    return safeJson(res);
  },

  async adminAddCoupon(data) {
    const res = await fetch(`${API_BASE_URL}/admin/coupons`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || "Failed to create coupon");
    return result;
  },

  async adminUpdateCoupon(couponId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/coupons/${couponId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || "Failed to update coupon");
    return result;
  },

  async adminDeleteCoupon(couponId) {
    const res = await fetch(`${API_BASE_URL}/admin/coupons/${couponId}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || "Failed to delete coupon");
    return result;
  },

  async getOutletCoupons() {
    const res = await fetch(`${API_BASE_URL}/outlet/coupons`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to fetch outlet coupons");
    return safeJson(res);
  },

  async getMenuItemReviews(itemId) {

    const res = await fetch(`${API_BASE_URL}/foods/menu-items/${itemId}/reviews`);
    if (!res.ok) throw new Error("Failed to load reviews");
    return safeJson(res);
  },

  async submitMenuItemReview(itemId, rating, comment) {
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    const res = await fetch(`${API_BASE_URL}/foods/menu-items/${itemId}/reviews`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ rating: parseInt(rating), comment })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Review submission failed");
    return data;
  },

  async adminGetReviews() {

    const res = await fetch(`${API_BASE_URL}/admin/reviews`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load reviews");
    return safeJson(res);
  },

  async adminUpdateReview(reviewId, data) {

    const res = await fetch(`${API_BASE_URL}/admin/reviews/${reviewId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to update review");
    return result;
  },

  async adminDeleteReview(reviewId) {

    const res = await fetch(`${API_BASE_URL}/admin/reviews/${reviewId}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to delete review");
    return data;
  },

  async cancelOrder(orderId, reason = "Cancelled by customer") {
    const res = await fetch(`${API_BASE_URL}/foods/orders/${orderId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ reason })
    });
    const result = await safeJson(res);
    if (!res.ok) throw new Error(result.message || result.error || "Failed to cancel order");
    return result;
  },
  // -------------------------------------------------------
  // Staff Shift Management (Clock-In / Clock-Out)
  // -------------------------------------------------------
  async posClockIn(email, pin) {
    const res = await fetch(`${API_BASE_URL}/pos/shift/clock-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ email, pin })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Clock-in failed");
    return data;
  },

  async posGetActiveShift() {
    const user = this.getCurrentUser();
    const res = await fetch(`${API_BASE_URL}/pos/shift/active`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to check active shift");
    return safeJson(res);
  },

  async posClockOut(actualCash, notes) {
    const user = this.getCurrentUser();
    notes = notes || "";
    const res = await fetch(`${API_BASE_URL}/pos/shift/clock-out`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ actual_cash: parseFloat(actualCash), notes })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Clock-out failed");
    return data;
  },

  async posLookupCustomer(email) {
    const res = await fetch(
      `${API_BASE_URL}/pos/customer/lookup?email=${encodeURIComponent(email)}`,
      { headers: getAuthHeader() }
    );
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Customer lookup failed");
    return data;
  },

  async posSellWithCRM(items, paymentMethod, couponCode, customerEmail, redeemLoyaltyPoints) {
    couponCode = couponCode || null;
    customerEmail = customerEmail || null;
    redeemLoyaltyPoints = redeemLoyaltyPoints || 0;
    const user = this.getCurrentUser();
    if (!user) throw new Error("Unauthorized");

    const res = await fetch(`${API_BASE_URL}/pos/sell`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({
        items, payment_method: paymentMethod, coupon_code: couponCode,
        customer_email: customerEmail, redeem_loyalty_points: redeemLoyaltyPoints
      })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "POS transaction failed");
    return data;
  },

  async adminGetShifts(params = {}) {
    
    const qs = new URLSearchParams();
    if (params.page) qs.append("page", params.page);
    if (params.outlet_id && params.outlet_id !== "all") qs.append("outlet_id", params.outlet_id);
    if (params.start_date) qs.append("start_date", params.start_date);
    if (params.end_date) qs.append("end_date", params.end_date);
    
    const res = await fetch(`${API_BASE_URL}/admin/shifts?${qs.toString()}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load timesheets");
    return safeJson(res);
  },

  async adminGetFinance() {
    const res = await fetch(`${API_BASE_URL}/admin/revenue-share`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load finance data");
    
    // The endpoint returns a list directly, but AdminView expects { revenue_share: [...] }
    const data = await safeJson(res);
    return { revenue_share: Array.isArray(data) ? data : [] };
  },

  async adminDeleteShift(shiftId) {
    const res = await fetch(`${API_BASE_URL}/admin/shifts/${shiftId}`, {
      method: "DELETE", headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to delete shift");
    return data;
  },

  // ----------------------------------------------------------------
  // Address Book API
  // ----------------------------------------------------------------
  async getAddresses() {
    const res = await fetch(`${API_BASE_URL}/auth/addresses`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load addresses");
    return safeJson(res);
  },
  async addAddress(title, address_line, is_default = false) {
    const res = await fetch(`${API_BASE_URL}/auth/addresses`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title, address_line, is_default })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to add address");
    return data;
  },
  async deleteAddress(id) {
    const res = await fetch(`${API_BASE_URL}/auth/addresses/${id}`, { method: "DELETE", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to delete address");
    return data;
  },

  // ----------------------------------------------------------------
  // Favorites API
  // ----------------------------------------------------------------
  async getFavorites() {
    const res = await fetch(`${API_BASE_URL}/foods/favorites`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load favorites");
    return safeJson(res);
  },
  async addFavorite(menu_item_id) {
    const res = await fetch(`${API_BASE_URL}/foods/favorites`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ menu_item_id })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to add favorite");
    return data;
  },
  async removeFavorite(menu_item_id) {
    const res = await fetch(`${API_BASE_URL}/foods/favorites/${menu_item_id}`, { method: "DELETE", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to remove favorite");
    return data;
  },

  // ----------------------------------------------------------------
  // Kitchen API
  // ----------------------------------------------------------------
  async getKitchenOrders() {
    const res = await fetch(`${API_BASE_URL}/kitchen/orders`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load kitchen orders");
    return safeJson(res);
  },
  async updateKitchenOrderStatus(orderId, status) {
    const res = await fetch(`${API_BASE_URL}/kitchen/orders/${orderId}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ status })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to update order status");
    return data;
  },
  async getStockRequests() {
    const res = await fetch(`${API_BASE_URL}/kitchen/stock-requests`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load stock requests");
    return safeJson(res);
  },
  async updateStockRequestStatus(id, status) {
    const res = await fetch(`${API_BASE_URL}/kitchen/stock-requests/${id}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ status })
    });
    return safeJson(res);
  },
  async createStockRequest(payload) {
    const res = await fetch(`${API_BASE_URL}/kitchen/stock-requests`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() }, body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to create stock request");
    return data;
  },
  async fulfillStockRequest(id) {
    const res = await fetch(`${API_BASE_URL}/kitchen/stock-requests/${id}/fulfill`, {
      method: "PUT", headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to fulfill stock request");
    return data;
  },
  async produceBatch(menu_item_id, quantity, expiry_date) {
    const res = await fetch(`${API_BASE_URL}/kitchen/produce`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ menu_item_id, quantity, expiry_date })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to produce batch");
    return data;
  },

  // --- New Admin CRM & Wallet Methods ---
  async adminCreditWallet(userId, amount, description) {
    const res = await fetch(`${API_BASE_URL}/admin/wallet/credit`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ user_id: userId, amount, description })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to credit wallet");
    return data;
  },
  async adminDebitWallet(userId, amount, description) {
    const res = await fetch(`${API_BASE_URL}/admin/wallet/debit`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ user_id: userId, amount, description })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to debit wallet");
    return data;
  },
  async adminGetWalletTransactions(userId) {
    const res = await fetch(`${API_BASE_URL}/admin/wallet/transactions/${userId}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load wallet transactions");
    return safeJson(res);
  },
  async adminGetCustomerSegments() {
    const res = await fetch(`${API_BASE_URL}/admin/customers/segments`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load customer segments");
    return safeJson(res);
  },
  async adminSendBroadcast(segment, message, medium) {
    const res = await fetch(`${API_BASE_URL}/admin/broadcast`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ segment, message, medium })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to send broadcast");
    return data;
  },

  // --- Banners & Store Settings ---
  async getPublicBanners() {
    const res = await fetch(`${API_BASE_URL}/public/banners`);
    if (!res.ok) throw new Error("Failed to load banners");
    return safeJson(res);
  },
  async adminGetBanners() {
    const res = await fetch(`${API_BASE_URL}/admin/banners`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load banners");
    return safeJson(res);
  },
  async adminCreateBanner(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/banners`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to create banner");
    return data;
  },
  async adminUpdateBanner(id, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/banners/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update banner");
    return data;
  },
  async adminDeleteBanner(id) {
    const res = await fetch(`${API_BASE_URL}/admin/banners/${id}`, {
      method: "DELETE", headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to delete banner");
    return data;
  },
  async adminUploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/admin/upload_image`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${sessionStorage.getItem("token")}`
      },
      body: formData
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to upload image");
    return data;
  },
  async adminGetSystemAuditLogs(params={}) {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`${API_BASE_URL}/admin/audit_logs?${query}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load audit logs");
    return safeJson(res);
  },
  async getPublicStoreSettings() {
    const res = await fetch(`${API_BASE_URL}/public/store-settings`);
    if (!res.ok) throw new Error("Failed to load store settings");
    return safeJson(res);
  },
  async adminGetMarketPurchases() {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load market purchases");
    return safeJson(res);
  },
  
  async adminAddMarketPurchase(payload) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to add market purchase");
    return data;
  },

  async adminEditMarketPurchase(id, payload) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to update market purchase");
    return data;
  },

  async adminDeleteMarketPurchase(id) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases/${id}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to delete market purchase");
    return data;
  },

  async adminGetStoreSettings() {
    const res = await fetch(`${API_BASE_URL}/admin/store-settings`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load store settings");
    return safeJson(res);
  },
  async adminUpdateStoreSettings(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/store-settings`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update store settings");
    return data;
  },

  // --- Ticketing ---
  async getCustomerTickets() {
    const res = await fetch(`${API_BASE_URL}/customer/tickets`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load tickets");
    return safeJson(res);
  },
  async createTicket(payload) {
    const res = await fetch(`${API_BASE_URL}/customer/tickets`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to create ticket");
    return data;
  },
  async getForecast() {
    return _fetch('/api/admin/forecast');
  },

  async adminGetTickets() {
    const res = await fetch(`${API_BASE_URL}/admin/tickets`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load tickets");
    return safeJson(res);
  },
  async adminReplyTicket(id, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/tickets/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update ticket");
    return data;
  },

  // --- Audit Logs ---
  async adminGetAuditLogs(page = 1, limit = 100) {
    const res = await fetch(`${API_BASE_URL}/admin/audit-logs?limit=${limit}`, { headers: getAuthHeader() });
    if (!res.ok) return { logs: [] };
    const data = await safeJson(res);
    return { logs: Array.isArray(data) ? data : (data.logs || []) };
  },

  // --- Revenue History & Reset ---
  async adminGetRevenueHistory() {
    const res = await fetch(`${API_BASE_URL}/admin/revenue/history`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load revenue history");
    return safeJson(res);
  },
  async adminResetRevenue(outlet_id) {
    const res = await fetch(`${API_BASE_URL}/admin/revenue/reset`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ outlet_id })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to reset revenue");
    return data;
  },

  // --- Refunds ---
  async adminRefundOrder(orderId, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/orders/${orderId}/refund`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to process refund");
    return data;
  },

  // --- Admin Profile ---
  async patchAdminProfile(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/profile`, {
      method: "PATCH", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update admin profile");
},

  // --- Banners & Store Settings ---
  async getPublicBanners() {
    const res = await fetch(`${API_BASE_URL}/public/banners`);
    if (!res.ok) throw new Error("Failed to load banners");
    return safeJson(res);
  },
  async adminGetBanners() {
    const res = await fetch(`${API_BASE_URL}/admin/banners`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load banners");
    return safeJson(res);
  },
  async adminCreateBanner(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/banners`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to create banner");
    return data;
  },
  async adminUpdateBanner(id, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/banners/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update banner");
    return data;
  },
  async adminDeleteBanner(id) {
    const res = await fetch(`${API_BASE_URL}/admin/banners/${id}`, {
      method: "DELETE", headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to delete banner");
    return data;
  },
  async adminUploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/admin/upload_image`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${sessionStorage.getItem("token")}`
      },
      body: formData
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to upload image");
    return data;
  },
  async adminGetSystemAuditLogs(params={}) {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`${API_BASE_URL}/admin/audit_logs?${query}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load audit logs");
    return safeJson(res);
  },
  async getPublicStoreSettings() {
    const res = await fetch(`${API_BASE_URL}/public/store-settings`);
    if (!res.ok) throw new Error("Failed to load store settings");
    return safeJson(res);
  },
  async adminGetMarketPurchases() {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load market purchases");
    return safeJson(res);
  },
  
  async adminAddMarketPurchase(payload) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to add market purchase");
    return data;
  },

  async adminEditMarketPurchase(id, payload) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to update market purchase");
    return data;
  },

  async adminDeleteMarketPurchase(id) {

    const res = await fetch(`${API_BASE_URL}/admin/market-purchases/${id}`, {
      method: "DELETE",
      headers: getAuthHeader()
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to delete market purchase");
    return data;
  },

  async adminGetStoreSettings() {
    const res = await fetch(`${API_BASE_URL}/admin/store-settings`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load store settings");
    return safeJson(res);
  },
  async adminUpdateStoreSettings(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/store-settings`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update store settings");
    return data;
  },


  async adminGetPaymentSettings() {
    const res = await fetch(`${API_BASE_URL}/admin/settings/payment`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load payment settings");
    return safeJson(res);
  },

  async adminUpdatePaymentSettings(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/settings/payment`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || data.error || "Failed to save payment settings");
    return data;
  },
  // --- Ticketing ---
  async getCustomerTickets() {
    const res = await fetch(`${API_BASE_URL}/customer/tickets`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load tickets");
    return safeJson(res);
  },
  async createTicket(payload) {
    const res = await fetch(`${API_BASE_URL}/customer/tickets`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to create ticket");
    return data;
  },
  async getForecast() {
    return _fetch('/api/admin/forecast');
  },

  async adminGetTickets() {
    const res = await fetch(`${API_BASE_URL}/admin/tickets`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load tickets");
    return safeJson(res);
  },
  async adminReplyTicket(id, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/tickets/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update ticket");
    return data;
  },

  // --- Audit Logs ---
  async adminGetAuditLogs(page = 1, limit = 100) {
    const res = await fetch(`${API_BASE_URL}/admin/audit-logs?limit=${limit}`, { headers: getAuthHeader() });
    if (!res.ok) return { logs: [] };
    const data = await safeJson(res);
    return { logs: Array.isArray(data) ? data : (data.logs || []) };
  },

  // --- Revenue History & Reset ---
  async adminGetRevenueHistory() {
    const res = await fetch(`${API_BASE_URL}/admin/revenue/history`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load revenue history");
    return safeJson(res);
  },
  async adminResetRevenue(outlet_id) {
    const res = await fetch(`${API_BASE_URL}/admin/revenue/reset`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ outlet_id })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to reset revenue");
    return data;
  },

  // --- Refunds ---
  async adminRefundOrder(orderId, payload) {
    const res = await fetch(`${API_BASE_URL}/admin/orders/${orderId}/refund`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to process refund");
    return data;
  },

  // --- Admin Profile ---
  async patchAdminProfile(payload) {
    const res = await fetch(`${API_BASE_URL}/admin/profile`, {
      method: "PATCH", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update admin profile");
    return data;
  },

  // --- POS Fast-Switch ---
  async posUnlock(payload) {
    const res = await fetch(`${API_BASE_URL}/auth/pos/unlock`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Unlock failed");
    return data;
  },

  // --- Kitchen Active Orders ---
  async kitchenGetActiveOrders() {
    const res = await fetch(`${API_BASE_URL}/kitchen/active-orders`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load kitchen orders");
    return safeJson(res);
  },
  async kitchenUpdateOrderStatus(orderId, status) {
    const res = await fetch(`${API_BASE_URL}/kitchen/orders/${orderId}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ status })
    });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to update status");
    return data;
  },

  // --- System Data Reset ---
  async resetTestOrders() {
    const res = await fetch(`${API_BASE_URL}/admin/reset/orders`, { method: "POST", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to reset test orders");
    return data;
  },
  async resetReviews() {
    const res = await fetch(`${API_BASE_URL}/admin/reset/reviews`, { method: "POST", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to clear reviews");
    return data;
  },
  async resetStockLevels() {
    const res = await fetch(`${API_BASE_URL}/admin/reset/stock`, { method: "POST", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to reset stock levels");
    return data;
  },
  async resetTestCustomers() {
    const res = await fetch(`${API_BASE_URL}/admin/reset/customers`, { method: "POST", headers: getAuthHeader() });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.message || "Failed to clear test customers");
    return data;
  }
};
