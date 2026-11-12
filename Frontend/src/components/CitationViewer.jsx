import { useEffect, useRef, useState } from "react";
import { getMaterialFileUrl } from "../api/materials";
import Spinner from "./Spinner";

// Blob errors come back as Blob, not JSON — read the FastAPI "detail" out of it.
async function blobErrorMessage(err) {
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      return JSON.parse(await data.text()).detail || "Could not open this source.";
    } catch {
      /* fall through */
    }
  }
  return "Could not open this source.";
}

/**
 * Modal that opens a cited source exactly where the tutor found the answer:
 *  - PDF   → opened at the cited page
 *  - video → plays from the cited timestamp
 *  - image → shown full size
 * (Lesson citations don't use this — they navigate to the Lessons page.)
 */
export default function CitationViewer({ citation, onClose }) {
  const [url, setUrl] = useState(null);
  const [error, setError] = useState("");
  const videoRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getMaterialFileUrl(citation.material_id)
      .then((u) => !cancelled && setUrl(u))
      .catch(async (err) => {
        const message = await blobErrorMessage(err);
        if (!cancelled) setError(message);
      });
    return () => {
      cancelled = true;
    };
  }, [citation.material_id]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function seekVideo() {
    const v = videoRef.current;
    if (v && citation.start_sec != null) {
      v.currentTime = citation.start_sec;
      v.play().catch(() => {}); // autoplay may be blocked; the user can press play
    }
  }

  const isWide = citation.type === "pdf";

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Source: ${citation.label}`}
    >
      <div
        className={`bg-white rounded-2xl shadow-xl w-full ${isWide ? "max-w-4xl h-[85vh]" : "max-w-2xl"} flex flex-col overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-gray-100">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400">
              Source [{citation.id}]
            </p>
            <p className="text-sm font-semibold text-gray-800 truncate">{citation.label}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-xl leading-none px-2"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 min-h-0 bg-gray-50 flex items-center justify-center">
          {error ? (
            <p className="text-sm text-red-500 p-8 text-center">{error}</p>
          ) : !url ? (
            <div className="flex items-center gap-2 p-8 text-sm text-gray-400">
              <Spinner size={4} color="text-indigo-500" /> Loading source…
            </div>
          ) : citation.type === "pdf" ? (
            // #page=N is understood by the browser's built-in PDF viewer
            <iframe
              title={citation.label}
              src={`${url}#page=${citation.page ?? 1}`}
              className="w-full h-full border-0"
            />
          ) : citation.type === "video" ? (
            <video
              ref={videoRef}
              src={url}
              controls
              className="w-full max-h-[70vh] bg-black"
              onLoadedMetadata={seekVideo}
            />
          ) : (
            <img src={url} alt={citation.label} className="max-w-full max-h-[75vh] object-contain" />
          )}
        </div>

        {citation.type === "video" && citation.timestamp && !error && (
          <div className="px-5 py-2 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-500">Starts at {citation.timestamp}</p>
            <button onClick={seekVideo} className="text-xs text-indigo-600 hover:underline">
              ↺ Jump back to {citation.timestamp}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
