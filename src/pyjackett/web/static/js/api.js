// Thin client for the PyJackett management API.
const BASE = document.documentElement.dataset.base || "";
const ROOT = `${BASE}/api/v2.0`;

export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.config = details.config || null;
    this.status = details.status || 0;
  }
}

function withQuery(path, query) {
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, value);
    }
  });
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

async function readError(response) {
  try {
    const data = await response.json();
    return new ApiError(data.error || response.statusText, {
      config: data.config,
      status: response.status,
    });
  } catch {
    return new ApiError(response.statusText || "Request failed", {
      status: response.status,
    });
  }
}

async function request(path, { method = "GET", body, query } = {}) {
  const response = await fetch(withQuery(`${ROOT}${path}`, query), {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (response.status === 401) {
    window.location.href = `${BASE}/UI/Login`;
    throw new ApiError("Please sign in again", { status: 401 });
  }
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  serverConfig: () => request("/server/config"),
  saveServerConfig: (config) =>
    request("/server/config", { method: "POST", body: config }),
  setAdminPassword: (password) =>
    request("/server/adminpassword", { method: "POST", body: password }),
  logs: () => request("/server/logs"),
  indexers: (configuredOnly = false) =>
    request("/indexers", {
      query: { configured: configuredOnly || undefined },
    }),
  indexerConfig: (id) => request(`/indexers/${id}/config`),
  saveIndexerConfig: (id, items) =>
    request(`/indexers/${id}/config`, { method: "POST", body: items }),
  testIndexer: (id) => request(`/indexers/${id}/test`, { method: "POST" }),
  deleteIndexer: (id) => request(`/indexers/${id}`, { method: "DELETE" }),
  cache: () => request("/indexers/cache"),
  search: (apiKey, params) =>
    request("/indexers/all/results", {
      query: { apikey: apiKey, ...params },
    }),
};

export const paths = {
  base: BASE,
  torznab: (id) => `${location.origin}${ROOT}/indexers/${id}/results/torznab/`,
  potato: (id) => `${location.origin}${ROOT}/indexers/${id}/results/potato/`,
};
