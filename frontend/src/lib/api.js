const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getApiUrl(path) {
  return `${API_BASE}${path}`;
}

export async function fetchHistory() {
  const resp = await fetch(getApiUrl("/api/history"));
  if (!resp.ok) throw new Error("Failed to fetch history");
  return resp.json();
}

export async function fetchReport(filename) {
  const resp = await fetch(getApiUrl(`/api/report/${filename}`));
  if (!resp.ok) throw new Error("Failed to fetch report");
  return resp.json();
}

export async function deleteReport(filename) {
  const resp = await fetch(getApiUrl(`/api/report/${filename}`), { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to delete report");
  return resp.json();
}
