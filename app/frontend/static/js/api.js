const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
const API_PREFIX = LOCAL_HOSTS.has(window.location.hostname)
  ? "/api/v1"
  : "https://librarian-pro-api.onrender.com/api/v1";
const ACCESS_KEY = "librarian_pro_access_token";
const REFRESH_KEY = "librarian_pro_refresh_token";

function getStoredToken(key) {
  return sessionStorage.getItem(key);
}

function storeTokens(tokens) {
  sessionStorage.setItem(ACCESS_KEY, tokens.access_token);
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens() {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

export function hasSession() {
  return Boolean(getStoredToken(ACCESS_KEY) || getStoredToken(REFRESH_KEY));
}

async function parseResponse(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

function extractError(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || "Invalid input").join("; ");
  }
  return fallback;
}

async function refreshSession() {
  const refreshToken = getStoredToken(REFRESH_KEY);
  if (!refreshToken) return false;
  const response = await fetch(`${API_PREFIX}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }
  storeTokens(await response.json());
  return true;
}

export async function login(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_PREFIX}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const payload = await parseResponse(response);
  if (!response.ok) throw new Error(extractError(payload, "Unable to sign in"));
  storeTokens(payload);
  return payload;
}

export async function logout() {
  const refreshToken = getStoredToken(REFRESH_KEY);
  try {
    if (refreshToken) {
      await fetch(`${API_PREFIX}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
  } finally {
    clearTokens();
  }
}

export async function apiRequest(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  const accessToken = getStoredToken(ACCESS_KEY);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_PREFIX}${path}`, { ...options, headers });
  if (response.status === 401 && retry && await refreshSession()) {
    return apiRequest(path, options, false);
  }
  const payload = await parseResponse(response);
  if (!response.ok) {
    const error = new Error(extractError(payload, `Request failed (${response.status})`));
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function jsonBody(data) {
  return JSON.stringify(data);
}
