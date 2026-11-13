import { useEffect, useRef, useState } from "react";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "./Spinner";

// Must match Services/language.py
const LANGUAGES = [
  { code: "en", label: "English", short: "EN", desc: "Plain English" },
  { code: "hi", label: "Hindi", short: "हिं", desc: "हिन्दी — Devanagari script" },
  { code: "ta", label: "Tamil", short: "த", desc: "தமிழ் — Tamil script" },
  { code: "hinglish", label: "Hinglish", short: "Hng", desc: "Hindi + English in English letters" },
  { code: "tanglish", label: "Tanglish", short: "Tng", desc: "Tamil + English in English letters" },
  { code: "auto", label: "Auto", short: "Auto", desc: "Reply in the language you ask in" },
];

/**
 * Navbar dropdown for the reply language (tutor, lessons, quiz feedback, viva).
 * Saved to the profile (PATCH /me), so it follows the student to any device.
 */
export default function LanguageMenu() {
  const [language, setLanguage] = useState(null); // null until /me loads
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(null);
  const [error, setError] = useState("");
  const rootRef = useRef(null);

  useEffect(() => {
    api
      .get("/me")
      .then((res) => setLanguage(res.data.preferred_language || "en"))
      .catch(() => setLanguage("en"));
  }, []);

  // close on outside click / Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function choose(code) {
    if (code === language) {
      setOpen(false);
      return;
    }
    setSaving(code);
    setError("");
    try {
      const res = await api.patch("/me", { preferred_language: code });
      setLanguage(res.data.preferred_language);
      setOpen(false);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't save. Try again."));
    } finally {
      setSaving(null);
    }
  }

  const current = LANGUAGES.find((l) => l.code === language);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Reply language"
        className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-800/60 hover:bg-blue-800 text-sm"
      >
        <span aria-hidden="true">🌐</span>
        <span>{current ? current.label : "…"}</span>
        <span className="text-[10px] text-blue-200" aria-hidden="true">▾</span>
      </button>

      {open && (
        <div
          role="menu"
          className="fixed inset-x-4 top-16 sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:w-72 bg-white text-gray-800 rounded-2xl shadow-lg border border-gray-100 p-2 z-50"
        >
          <p className="px-3 pt-1.5 pb-2 text-xs text-gray-400">
            Language for the tutor, lessons, quiz explanations and viva
          </p>
          {LANGUAGES.map((l) => {
            const active = l.code === language;
            return (
              <button
                key={l.code}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                onClick={() => choose(l.code)}
                disabled={saving !== null}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left hover:bg-indigo-50 disabled:opacity-60"
                style={{ background: active ? "#EEF2FF" : undefined }}
              >
                <span
                  className="w-9 h-7 rounded-lg flex items-center justify-center text-xs font-semibold flex-shrink-0"
                  style={{ background: active ? "#4F46E5" : "#F3F4F6", color: active ? "#fff" : "#4B5563" }}
                >
                  {l.short}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-medium">{l.label}</span>
                  <span className="block text-xs text-gray-400 truncate">{l.desc}</span>
                </span>
                {saving === l.code ? (
                  <Spinner color="text-indigo-600" />
                ) : (
                  active && <span className="text-indigo-600 text-sm">✓</span>
                )}
              </button>
            );
          })}
          {error && <p className="px-3 py-1.5 text-xs text-red-500">{error}</p>}
          <p className="px-3 pt-2 pb-1 text-[11px] text-gray-400 border-t border-gray-100 mt-1">
            Quiz questions stay in English so answers can be marked reliably.
          </p>
        </div>
      )}
    </div>
  );
}
