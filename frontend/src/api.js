/**
 * api.js — thin wrapper around the FastAPI backend.
 *
 * All functions throw an Error with a human-readable message on failure.
 * The base URL is empty so the Vite dev-server proxy forwards /api/* to
 * http://localhost:8000.  In production builds the same origin is used.
 */

const BASE = ''   // proxy handles /api/* → http://localhost:8000

/**
 * Upload a PDF file and start a new session.
 *
 * NOTE: This can be slow — Ollama cold-start can take up to ~235 seconds.
 * The caller must not impose a short timeout.
 *
 * @param {File} file
 * @returns {Promise<{ session_id: string, summary: object }>}
 */
export async function uploadStatement(file) {
  const form = new FormData()
  form.append('file', file)

  const res = await fetch(`${BASE}/api/upload`, {
    method: 'POST',
    body: form,
    // No explicit timeout — let the browser / OS decide.
    // The backend can legitimately take several minutes.
  })

  if (!res.ok) {
    let detail = `Upload failed (HTTP ${res.status})`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch (_) { /* ignore JSON parse errors */ }
    throw new Error(detail)
  }

  return res.json()
}

/**
 * Send a chat message and receive an answer.
 *
 * @param {string} sessionId
 * @param {string} message
 * @returns {Promise<{ answer: string }>}
 */
export async function sendMessage(sessionId, message) {
  const res = await fetch(`${BASE}/api/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ session_id: sessionId, message }),
  })

  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status})`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch (_) { /* ignore */ }
    throw new Error(detail)
  }

  return res.json()
}

/**
 * Health check — returns true when the backend is reachable.
 *
 * @returns {Promise<boolean>}
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/api/health`)
    return res.ok
  } catch (_) {
    return false
  }
}
