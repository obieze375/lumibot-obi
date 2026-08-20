const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_TOKEN = import.meta.env.VITE_API_TOKEN || "";

async function request(path, options = {}) {
  if (!API_BASE) {
    throw new Error("VITE_API_BASE_URL is not set");
  }
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${API_TOKEN}`,
    "X-Skope-Token": API_TOKEN,
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || `HTTP ${res.status}`);
  }
  return data;
}

export const api = {
  status: () => request("/api/status"),
  candidates: () => request("/api/candidates"),
  trades: () => request("/api/trades"),
  events: () => request("/api/events"),
  screen: () => request("/api/screen", { method: "POST" }),
  approve: (candidateId) =>
    request("/api/trades/approve", {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidateId }),
    }),
  reject: (candidateId) =>
    request(`/api/candidates/${candidateId}/reject`, { method: "POST" }),
};
