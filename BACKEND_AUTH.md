# Backend Authentication Contract

This document outlines the authentication contract between the frontend and the Flask backend for the food-ordering app.

## JWT Implementation

The backend uses JWT (JSON Web Tokens) with a short-lived access token and a long-lived refresh token.
- **Access Token TTL**: 15 minutes
- **Refresh Token TTL**: 7 days

Tokens now contain a `token_version` claim to invalidate existing sessions instantly when critical security events occur (e.g., password change, PIN change, account deactivation).

## 1. Login

**Endpoint**: `POST /api/auth/login`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Success Response (200 OK)**:
```json
{
  "message": "Login successful",
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG...",
  "user": { ... }
}
```

**Frontend Action**:
- Store both `access_token` and `refresh_token` securely (e.g., in `localStorage`, `sessionStorage`, or secure cookies, depending on your existing architecture).

## 2. Authenticated Requests & Refreshing Tokens

When making requests to protected endpoints (e.g., `/api/auth/me`), include the access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

If the `access_token` expires or becomes invalid, the backend will return a `401 Unauthorized` or `422 Unprocessable Entity` response.

**Frontend Action on 401/422**:
1. Detect the 401/422 status code on an authenticated request.
2. Attempt to refresh the access token by calling the refresh endpoint.

**Refresh Endpoint**: `POST /api/auth/refresh`
- Include the **refresh token** in the `Authorization` header.

```http
Authorization: Bearer <refresh_token>
```

**Refresh Success Response (200 OK)**:
```json
{
  "access_token": "eyJhbG... (new token)"
}
```
3. Update your stored `access_token` with the new one.
4. Retry the original failed request with the new `access_token`.
5. If the refresh request *also* fails (e.g., returns 401 because the refresh token is expired or revoked), force the user to log out and redirect them to the login page.

## 3. Logout

**Endpoint**: `POST /api/auth/logout`

**Request Headers**:
```http
Authorization: Bearer <access_token>
```

**Request Body** (Optional but recommended to revoke the refresh token in Redis):
```json
{
  "refresh_token": "<refresh_token>"
}
```

**Frontend Action**:
- Make the request to the logout endpoint.
- Clear the stored `access_token` and `refresh_token` from storage on the client side.
- Redirect to the login page.
