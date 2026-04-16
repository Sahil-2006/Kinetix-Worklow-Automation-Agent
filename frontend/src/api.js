const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

/** Get the stored access token. */
function getToken() {
  return localStorage.getItem("kinetix_access_token") || "";
}

/** Build auth headers. */
function authHeaders() {
  const token = getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse(response) {
  if (response.status === 401) {
    // Token expired — try refresh
    const refreshed = await tryRefresh();
    if (!refreshed) {
      // Clear auth and force re-login
      localStorage.removeItem("kinetix_access_token");
      localStorage.removeItem("kinetix_refresh_token");
      localStorage.removeItem("kinetix_user");
      window.dispatchEvent(new Event("kinetix-logout"));
      throw new Error("Session expired. Please log in again.");
    }
    throw new Error("RETRY"); // caller should retry with new token
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Request failed.");
  }
  return response.json();
}

/** Attempt to refresh the access token. Returns true on success. */
async function tryRefresh() {
  const refreshToken = localStorage.getItem("kinetix_refresh_token");
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) return false;

    const data = await res.json();
    localStorage.setItem("kinetix_access_token", data.access_token);
    localStorage.setItem("kinetix_refresh_token", data.refresh_token);
    localStorage.setItem("kinetix_user", JSON.stringify(data.user));
    return true;
  } catch {
    return false;
  }
}

/**
 * Stream a chat message via SSE.
 * Calls `onEvent(eventObj)` for each server-sent event.
 * Returns an AbortController so the caller can cancel.
 */
export function streamChat(message, onEvent) {
  const controller = new AbortController();

  fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ message }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (response.status === 401) {
        const refreshed = await tryRefresh();
        if (refreshed) {
          // Re-try with new token
          const retryRes = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ message }),
            signal: controller.signal,
          });
          return retryRes;
        } else {
          localStorage.removeItem("kinetix_access_token");
          window.dispatchEvent(new Event("kinetix-logout"));
          onEvent({ type: "error", content: "Session expired. Please log in again." });
          onEvent({ type: "done" });
          return null;
        }
      }
      return response;
    })
    .then(async (response) => {
      if (!response) return;

      if (!response.ok) {
        const text = await response.text();
        onEvent({ type: "error", content: text || "Request failed." });
        onEvent({ type: "done" });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data:")) {
            const raw = line.slice(5).trim();
            if (!raw) continue;
            try {
              const parsed = JSON.parse(raw);
              onEvent(parsed);
            } catch {
              // skip malformed
            }
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim()) {
        for (const line of buffer.split("\n")) {
          if (line.startsWith("data:")) {
            const raw = line.slice(5).trim();
            if (!raw) continue;
            try {
              onEvent(JSON.parse(raw));
            } catch {
              // skip
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onEvent({ type: "error", content: err.message });
        onEvent({ type: "done" });
      }
    });

  return controller;
}

// Legacy endpoints
export async function executeCommand(command, context) {
  const response = await fetch(`${API_BASE}/api/command`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ command, context }),
  });
  return handleResponse(response);
}

export async function fetchRuns() {
  const response = await fetch(`${API_BASE}/api/runs`, {
    headers: authHeaders(),
  });
  return handleResponse(response);
}

export async function fetchRun(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`, {
    headers: authHeaders(),
  });
  return handleResponse(response);
}
