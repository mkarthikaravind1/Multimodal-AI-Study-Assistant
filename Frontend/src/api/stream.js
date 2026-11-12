import { API_BASE } from "./axios";

/**
 * POSTs JSON and reads the Server-Sent Events stream the backend sends back.
 *
 *   await streamPost("/chat/stream", body, {
 *     onToken: (text) => …,        // each piece of generated text
 *     onDone:  (data) => …,        // final, saved result
 *     signal:  abortController.signal,
 *   });
 *
 * Rejects with an Error whose .message is user-readable:
 *  - HTTP errors before streaming starts (404, 422 …) use the API's "detail"
 *  - an "error" event mid-stream uses its "detail"
 *  - an aborted request rejects with error.name === "AbortError"
 * axios can't read a response body as a stream in the browser, hence fetch.
 */
export async function streamPost(path, body, { onToken, onDone, signal } = {}) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    // Same behaviour as the axios interceptor: expired session → login page
    if (res.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    let message = `Request failed (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join(" · ");
    } catch {
      /* not JSON */
    }
    throw new Error(message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  function handle(rawEvent) {
    let event = "message";
    const dataLines = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const data = JSON.parse(dataLines.join("\n"));
    if (event === "token") onToken?.(data.text);
    else if (event === "done") {
      finished = true;
      onDone?.(data);
    } else if (event === "error") {
      finished = true;
      throw new Error(data.detail || "Generation failed.");
    }
  }

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      handle(rawEvent);
    }
  }
  if (buffer.trim()) handle(buffer);
  if (!finished) throw new Error("The connection closed before the answer finished. Please try again.");
}
