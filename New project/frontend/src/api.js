const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle(resp) {
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${resp.status})`);
  }
  return resp.json();
}

export async function login(email, password) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const resp = await fetch(`${BACKEND_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  const data = await handle(resp);
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
}

export async function getCurrentUser() {
  const resp = await fetch(`${BACKEND_URL}/users/me`, { headers: authHeaders() });
  return handle(resp);
}

export async function listUsers() {
  const resp = await fetch(`${BACKEND_URL}/users`, { headers: authHeaders() });
  return handle(resp);
}

export async function getUser(userId) {
  const resp = await fetch(`${BACKEND_URL}/users/${userId}`, { headers: authHeaders() });
  return handle(resp);
}

export async function createUser(payload) {
  const resp = await fetch(`${BACKEND_URL}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return handle(resp);
}

export async function updateUser(userId, payload) {
  const resp = await fetch(`${BACKEND_URL}/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return handle(resp);
}

export async function listDepartments() {
  const resp = await fetch(`${BACKEND_URL}/departments`, { headers: authHeaders() });
  return handle(resp);
}

export async function createDepartment(name) {
  const resp = await fetch(`${BACKEND_URL}/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  return handle(resp);
}

export async function updateDepartment(departmentId, name) {
  const resp = await fetch(`${BACKEND_URL}/departments/${departmentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  return handle(resp);
}

export async function deleteDepartment(departmentId) {
  const resp = await fetch(`${BACKEND_URL}/departments/${departmentId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${resp.status})`);
  }
}

export async function listTimeEntries(userId, range) {
  const url = new URL(`${BACKEND_URL}/time-entries`);
  if (userId) url.searchParams.set("user_id", userId);
  if (range?.start) url.searchParams.set("start_date", range.start);
  if (range?.end) url.searchParams.set("end_date", range.end);
  const resp = await fetch(url, { headers: authHeaders() });
  return handle(resp);
}

export async function sendHeartbeat(entryId, isIdle) {
  const resp = await fetch(`${BACKEND_URL}/time-entries/${entryId}/heartbeat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ is_idle: isIdle }),
  });
  return handle(resp);
}

export async function listScreenshots(userId, timeEntryId) {
  const url = new URL(`${BACKEND_URL}/screenshots`);
  if (userId) url.searchParams.set("user_id", userId);
  if (timeEntryId) url.searchParams.set("time_entry_id", timeEntryId);
  const resp = await fetch(url, { headers: authHeaders() });
  return handle(resp);
}

export async function getSettings() {
  const resp = await fetch(`${BACKEND_URL}/settings`, { headers: authHeaders() });
  return handle(resp);
}

export async function updateSettings(payload) {
  const resp = await fetch(`${BACKEND_URL}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return handle(resp);
}

export async function screenshotImageUrl(screenshotId) {
  const resp = await fetch(`${BACKEND_URL}/screenshots/${screenshotId}/file`, { headers: authHeaders() });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${resp.status})`);
  }
  return URL.createObjectURL(await resp.blob());
}