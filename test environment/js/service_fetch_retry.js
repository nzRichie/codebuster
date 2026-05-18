/**
 * Retry a GET with exponential backoff; unrelated structure to other fixtures here.
 */

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function fetchWithRetries(url, { attempts = 3, baseDelayMs = 200 } = {}) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return response;
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (err) {
      lastError = err;
    }
    if (i + 1 < attempts) {
      await sleep(baseDelayMs * Math.pow(2, i));
    }
  }
  throw lastError;
}
