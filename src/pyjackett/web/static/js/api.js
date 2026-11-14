// Thin client for the Jackett management API.
const BASE = document.documentElement.dataset.base || "";
const ROOT = `${BASE}/api/v2.0`;

export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.config = details.config || null;
    this.status = details.status || 0;
    this.latencyMs = details.latencyMs ?? null;
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
      latencyMs: data.latency_ms,
    });
  } catch {
    return new ApiError(response.statusText || "Request failed", {
      status: response.status,
    });
  }
}

async function readLines(body, onLine) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += value || "";
    const lines = buffer.split("\n");
    buffer = done ? "" : lines.pop();
    lines.filter(Boolean).forEach(onLine);
    if (done) return;
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

/** Runs one operation over many indexers; resolves to one outcome each. */
const bulk = (operation, ids) =>
  request(`/indexers/bulk/${operation}`, { method: "POST", body: { ids } });

export const api = {
  serverConfig: () => request("/server/config"),
  saveServerConfig: (config) =>
    request("/server/config", { method: "POST", body: config }),
  setAdminPassword: (password) =>
    request("/server/adminpassword", { method: "POST", body: password }),
  setAdminUsername: (username) =>
    request("/server/adminusername", { method: "POST", body: username }),
  rotateApiKey: (password) =>
    request("/server/apikey/rotate", { method: "POST", body: { password } }),
  logs: () => request("/server/logs"),
  clearLogs: () => request("/server/logs", { method: "DELETE" }),
  indexers: (configuredOnly = false) =>
    request("/indexers", {
      query: { configured: configuredOnly || undefined },
    }),
  indexerConfig: (id) => request(`/indexers/${id}/config`),
  saveIndexerConfig: (id, items) =>
    request(`/indexers/${id}/config`, { method: "POST", body: items }),
  addIndexer: (id) => request(`/indexers/${id}/add`, { method: "POST" }),
  testIndexer: (id) => request(`/indexers/${id}/test`, { method: "POST" }),
  deleteIndexer: (id) => request(`/indexers/${id}`, { method: "DELETE" }),
  bulkAdd: (ids) => bulk("add", ids),
  bulkDelete: (ids) => bulk("delete", ids),
  search: (apiKey, params) =>
    request("/indexers/all/results", {
      query: { apikey: apiKey, ...params },
    }),
  /** Calls `onChunk({indexer, results})` as each tracker finishes. */
  searchStream: async (apiKey, params, onChunk, signal) => {
    const response = await fetch(
      withQuery(`${ROOT}/indexers/all/results/stream`, {
        apikey: apiKey,
        ...params,
      }),
      { credentials: "same-origin", signal },
    );
    if (response.status === 401) {
      window.location.href = `${BASE}/UI/Login`;
      throw new ApiError("Please sign in again", { status: 401 });
    }
    if (!response.ok) throw await readError(response);
    await readLines(response.body, (line) => onChunk(JSON.parse(line)));
  },
};

export const paths = {
  base: BASE,
  torznab: (id) => `${location.origin}${ROOT}/indexers/${id}/results/torznab/`,
  potato: (id) => `${location.origin}${ROOT}/indexers/${id}/results/potato/`,
};
