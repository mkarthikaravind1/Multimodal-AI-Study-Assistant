import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

// ── helpers ───────────────────────────────────────────────────────────────────

const MAX_SIDE = 2000;          // px — enough to read handwriting, small enough for the vision model
const MAX_UPLOAD = 4 * 1024 * 1024;

const VERDICTS = {
  correct: { label: "All correct", icon: "✅", fg: "#16A34A", bg: "#DCFCE7" },
  incorrect: { label: "Mistake found", icon: "🔍", fg: "#DC2626", bg: "#FEE2E2" },
  incomplete: { label: "Not finished", icon: "⏳", fg: "#CA8A04", bg: "#FEF9C3" },
  unreadable: { label: "Unreadable", icon: "❓", fg: "#6B7280", bg: "#F3F4F6" },
};

const STEP_STYLES = {
  correct: { label: "✓", title: "Correct", fg: "#16A34A", bg: "#F0FDF4", border: "#BBF7D0" },
  error: { label: "✗", title: "Mistake", fg: "#DC2626", bg: "#FEF2F2", border: "#FCA5A5" },
  follows_error: { label: "↳", title: "Carries the earlier mistake", fg: "#CA8A04", bg: "#FFFBEB", border: "#FDE68A" },
  unclear: { label: "?", title: "Couldn't judge this step", fg: "#6B7280", bg: "#F9FAFB", border: "#E5E7EB" },
};

const ERROR_TYPES = {
  arithmetic: "Arithmetic slip",
  algebra: "Algebra error",
  sign: "Sign error",
  concept: "Concept mix-up",
  formula: "Wrong formula",
  units: "Units error",
  copying: "Copying error",
  logic: "Logic gap",
  notation: "Notation",
  other: "Mistake",
};

/**
 * Phone photos are often 4000px+ and several MB. Shrink to MAX_SIDE and
 * re-encode as JPEG — keeps uploads fast and under the 4 MB vision limit.
 * createImageBitmap applies the EXIF rotation, so sideways photos come out upright.
 */
async function prepareImage(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new Error("This image format isn't supported here. Please use a JPEG, PNG or WebP photo.");
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff"; // transparent PNGs → white page, not black
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close?.();

  for (const quality of [0.88, 0.75, 0.6]) {
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
    if (blob && blob.size <= MAX_UPLOAD) {
      const name = (file.name || "solution").replace(/\.[^.]+$/, "") + ".jpg";
      return new File([blob], name, { type: "image/jpeg" });
    }
  }
  throw new Error("This photo is too large even after compressing. Try cropping it.");
}

function scoreColors(score) {
  if (score == null) return { fg: "#6B7280", bg: "#F3F4F6" };
  if (score >= 7) return { fg: "#16A34A", bg: "#DCFCE7" };
  if (score >= 4) return { fg: "#CA8A04", bg: "#FEF9C3" };
  return { fg: "#DC2626", bg: "#FEE2E2" };
}

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "";
}

function CameraIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
      <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  );
}

// The stored photo needs the auth header, so it's fetched as a blob
function useSolutionImage(checkId) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;
    api
      .get(`/solutions/${checkId}/image`, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [checkId]);
  return { url, failed };
}

// ── upload ────────────────────────────────────────────────────────────────────

function UploadPhase({ onChecked, onOpen }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [problem, setProblem] = useState("");
  const [expected, setExpected] = useState("");
  const [topic, setTopic] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const pickRef = useRef(null);
  const cameraRef = useRef(null);

  useEffect(() => {
    api
      .get("/solutions/history")
      .then((res) => setHistory(res.data))
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, []);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  async function choose(picked) {
    if (!picked) return;
    if (!picked.type.startsWith("image/")) {
      setError("Please choose a photo (JPEG, PNG or WebP).");
      return;
    }
    setError("");
    setPreparing(true);
    try {
      const ready = await prepareImage(picked);
      setFile(ready);
      setPreview(URL.createObjectURL(ready));
    } catch (err) {
      setError(err.message);
    } finally {
      setPreparing(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (!file) return;
    setChecking(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("problem", problem.trim());
    form.append("expected_answer", expected.trim());
    form.append("topic", topic.trim());
    try {
      const res = await api.post("/solutions/check", form);
      onChecked(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Could not check this solution. Please try again."));
      setChecking(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <form onSubmit={submit} className="lg:col-span-3 bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style={{ background: "#EEF2FF" }}>📝</span>
          <div>
            <h2 className="text-base font-semibold text-gray-800">Check a worked solution</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Photograph your handwritten working — every step is checked and the first mistake is pointed out.
            </p>
          </div>
        </div>

        {error && <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

        {/* drop zone / preview */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!checking) choose(e.dataTransfer.files?.[0]);
          }}
          className="rounded-2xl border-2 border-dashed flex flex-col items-center justify-center text-center p-4 transition-colors"
          style={{
            borderColor: dragging ? "#4F46E5" : "#E5E7EB",
            background: dragging ? "#EEF2FF" : "#FAFAFF",
            minHeight: 220,
          }}
        >
          {preparing ? (
            <div className="flex items-center gap-2 text-sm text-gray-500"><Spinner color="text-indigo-600" /> Preparing photo…</div>
          ) : preview ? (
            <div className="w-full flex flex-col items-center gap-3">
              <img src={preview} alt="Your solution" className="max-h-80 rounded-xl border border-gray-100 object-contain" />
              {!checking && (
                <button
                  type="button"
                  onClick={() => {
                    setFile(null);
                    setPreview(null);
                  }}
                  className="text-xs text-gray-500 hover:text-red-600"
                >
                  ✕ Choose a different photo
                </button>
              )}
            </div>
          ) : (
            <>
              <span className="text-indigo-500 mb-2"><CameraIcon /></span>
              <p className="text-sm font-medium text-gray-700">Drop a photo of your working here</p>
              <p className="text-xs text-gray-400 mt-1 mb-4">Good light, camera straight above the page, working fills the frame</p>
              <div className="flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  onClick={() => cameraRef.current?.click()}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 sm:hidden"
                  style={{ background: "#4F46E5" }}
                >
                  📷 Take photo
                </button>
                <button
                  type="button"
                  onClick={() => pickRef.current?.click()}
                  className="px-4 py-2 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50"
                >
                  Choose image
                </button>
              </div>
            </>
          )}
          <input ref={pickRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
          <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            Problem <span className="text-gray-300">(optional — if it isn't written on the page)</span>
          </label>
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            rows={2}
            maxLength={2000}
            disabled={checking}
            placeholder="e.g. Solve 2x² − 5x − 3 = 0"
            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-300
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Answer key <span className="text-gray-300">(optional)</span>
            </label>
            <input
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              maxLength={255}
              disabled={checking}
              placeholder="e.g. x = 3 or x = −½"
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-300
                         focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Topic <span className="text-gray-300">(optional)</span>
            </label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              maxLength={200}
              disabled={checking}
              placeholder="e.g. Quadratic equations"
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-300
                         focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!file || checking || preparing}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white
                     hover:opacity-90 disabled:opacity-60"
          style={{ background: "#4F46E5" }}
        >
          {checking ? <><Spinner /> Reading and checking every step…</> : "Check my working"}
        </button>
      </form>

      <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Past checks</h3>
        {loadingHistory ? (
          <div className="flex flex-col gap-2 animate-pulse">
            {[0, 1, 2].map((i) => <div key={i} className="h-12 bg-gray-100 rounded-xl" />)}
          </div>
        ) : history.length === 0 ? (
          <p className="text-xs text-gray-400">Your checked solutions will appear here.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {history.map((h) => {
              const v = VERDICTS[h.verdict] ?? VERDICTS.incorrect;
              return (
                <li key={h.check_id}>
                  <button
                    type="button"
                    onClick={() => onOpen(h.check_id)}
                    className="w-full text-left px-3 py-2.5 rounded-xl border border-gray-100 hover:border-indigo-200
                               hover:bg-indigo-50/40 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{h.title}</p>
                      <p className="text-xs text-gray-400">
                        {formatDate(h.created_at)}
                        {h.topic ? ` · ${h.topic}` : ""}
                      </p>
                    </div>
                    <span
                      className="text-xs font-semibold px-2 py-1 rounded-lg flex-shrink-0"
                      style={{ background: v.bg, color: v.fg }}
                      title={v.label}
                    >
                      {v.icon} {h.score != null ? `${h.score}/10` : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── result ────────────────────────────────────────────────────────────────────

function StepRow({ step, index, isFirstError }) {
  const [showFix, setShowFix] = useState(false);
  const s = STEP_STYLES[step.status] ?? STEP_STYLES.unclear;
  return (
    <li
      className="rounded-xl border px-4 py-3"
      style={{
        background: s.bg,
        borderColor: s.border,
        boxShadow: isFirstError ? "0 0 0 2px #FCA5A5" : "none",
      }}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 bg-white"
          style={{ color: s.fg, border: `1px solid ${s.border}` }}
          title={s.title}
        >
          {s.label}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-[11px] font-medium text-gray-400">Step {index + 1}</span>
            {isFirstError && (
              <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded bg-red-600 text-white">First mistake</span>
            )}
            {step.status === "follows_error" && (
              <span className="text-[11px] text-amber-700">carries the earlier mistake</span>
            )}
          </div>
          <p className="text-sm text-gray-800 font-mono break-words whitespace-pre-wrap">{step.text}</p>
          {step.comment && <p className="text-xs mt-1.5" style={{ color: step.status === "correct" ? "#4B5563" : s.fg }}>{step.comment}</p>}
          {step.status === "error" && step.correction && (
            showFix ? (
              <div className="mt-2 rounded-lg bg-white border border-green-200 px-3 py-2">
                <p className="text-[11px] font-medium text-green-700 mb-0.5">Corrected step</p>
                <p className="text-sm text-gray-800 font-mono break-words">{step.correction}</p>
              </div>
            ) : (
              <button type="button" onClick={() => setShowFix(true)} className="mt-2 text-xs text-indigo-600 hover:underline">
                Show the fix →
              </button>
            )
          )}
        </div>
      </div>
    </li>
  );
}

function EditTranscription({ check, onRechecked, onCancel }) {
  const [problem, setProblem] = useState(check.problem || "");
  const [steps, setSteps] = useState(check.steps.map((s) => s.text));
  const [finalAnswer, setFinalAnswer] = useState(check.final_answer || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const cleaned = steps.map((s) => s.trim()).filter(Boolean);

  async function recheck() {
    setSaving(true);
    setError("");
    try {
      const res = await api.post(`/solutions/${check.check_id}/recheck`, {
        steps: cleaned,
        problem: problem.trim(),
        final_answer: finalAnswer.trim(),
      });
      onRechecked(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Re-check failed. Your edits are still here — try again."));
      setSaving(false);
    }
  }

  const inputCls =
    "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500";

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-gray-500">
        Fix anything the AI misread so it matches what you actually wrote, then re-check. Don't correct your own mistakes here — that's cheating yourself 🙂
      </p>
      <div>
        <label className="block text-[11px] font-medium text-gray-400 mb-1">Problem</label>
        <textarea value={problem} onChange={(e) => setProblem(e.target.value)} rows={2} maxLength={2000} className={inputCls} />
      </div>
      <ol className="flex flex-col gap-2">
        {steps.map((text, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="text-[11px] text-gray-400 w-6 pt-2.5 text-right flex-shrink-0">{i + 1}.</span>
            <textarea
              value={text}
              onChange={(e) => setSteps((prev) => prev.map((s, j) => (j === i ? e.target.value : s)))}
              rows={1}
              maxLength={500}
              className={`${inputCls} resize-y`}
            />
            <button
              type="button"
              onClick={() => setSteps((prev) => prev.filter((_, j) => j !== i))}
              disabled={steps.length <= 1}
              aria-label={`Remove step ${i + 1}`}
              className="text-gray-300 hover:text-red-500 pt-2 disabled:opacity-30"
            >
              ✕
            </button>
          </li>
        ))}
      </ol>
      {steps.length < 40 && (
        <button type="button" onClick={() => setSteps((prev) => [...prev, ""])} className="self-start text-xs text-indigo-600 hover:underline">
          + Add a step
        </button>
      )}
      <div>
        <label className="block text-[11px] font-medium text-gray-400 mb-1">Your final answer</label>
        <input value={finalAnswer} onChange={(e) => setFinalAnswer(e.target.value)} maxLength={255} className={inputCls} />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="flex-1 py-2 rounded-xl text-sm font-medium border border-gray-200 text-gray-600 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={recheck}
          disabled={saving || cleaned.length === 0}
          className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
          style={{ background: "#4F46E5" }}
        >
          {saving ? <><Spinner /> Re-checking…</> : "Re-check"}
        </button>
      </div>
    </div>
  );
}

function ResultPhase({ check, setCheck, onNew, onDeleted }) {
  const navigate = useNavigate();
  const { url: imageUrl, failed: imageFailed } = useSolutionImage(check.check_id);
  const [editing, setEditing] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [cardMsg, setCardMsg] = useState("");
  const [savingCard, setSavingCard] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState("");

  const v = VERDICTS[check.verdict] ?? VERDICTS.incorrect;
  const sc = scoreColors(check.score);
  const firstError = check.first_error_step;

  async function saveCard() {
    setSavingCard(true);
    setActionError("");
    try {
      const res = await api.post(`/solutions/${check.check_id}/flashcard`);
      setCardMsg(res.data.flashcard_added ? "🃏 Saved to your flashcards." : "Already in your flashcards.");
    } catch (err) {
      setActionError(getErrorMessage(err, "Could not save the flashcard."));
    } finally {
      setSavingCard(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this check and its photo?")) return;
    setDeleting(true);
    setActionError("");
    try {
      await api.delete(`/solutions/${check.check_id}`);
      onDeleted();
    } catch (err) {
      setActionError(getErrorMessage(err, "Could not delete it."));
      setDeleting(false);
    }
  }

  function askTutor() {
    const step = firstError != null ? check.steps[firstError] : null;
    const q = step
      ? `I'm solving: ${check.problem || "a problem"}. In my working I wrote "${step.text}" and was told: ${step.comment} Can you explain why this is wrong and how to do it properly?`
      : `Can you explain how to solve: ${check.problem}`;
    navigate("/tutor", { state: { prefill: q } });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* verdict bar */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col sm:flex-row sm:items-center gap-4">
        <div
          className="w-16 h-16 rounded-full flex flex-col items-center justify-center flex-shrink-0"
          style={{ background: sc.bg, color: sc.fg }}
        >
          <span className="text-xl font-bold leading-none">{check.score ?? "–"}</span>
          <span className="text-[10px] font-medium">/ 10</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs font-semibold px-2 py-0.5 rounded-lg" style={{ background: v.bg, color: v.fg }}>
              {v.icon} {v.label}
            </span>
            {check.error_type && (
              <span className="text-xs px-2 py-0.5 rounded-lg bg-gray-100 text-gray-600">
                {ERROR_TYPES[check.error_type] ?? "Mistake"}
                {firstError != null ? ` · step ${firstError + 1}` : ""}
              </span>
            )}
            {check.topic && <span className="text-xs text-gray-400">{check.topic}</span>}
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{check.summary}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* photo */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 lg:sticky lg:top-6">
          <p className="text-xs font-medium text-gray-400 mb-2">Your photo</p>
          {imageUrl ? (
            <a href={imageUrl} target="_blank" rel="noreferrer" title="Open full size">
              <img src={imageUrl} alt="Your handwritten solution" className="w-full rounded-xl border border-gray-100 object-contain max-h-[70vh]" />
            </a>
          ) : imageFailed ? (
            <p className="text-xs text-gray-400 italic py-10 text-center">The photo is no longer available.</p>
          ) : (
            <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
          )}
        </div>

        {/* marking */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-gray-800">{editing ? "Fix the transcription" : "Step-by-step marking"}</h3>
            {!editing && check.rechecks < 5 && (
              <button type="button" onClick={() => setEditing(true)} className="text-xs text-indigo-600 hover:underline">
                ✎ Misread something?
              </button>
            )}
          </div>

          {editing ? (
            <EditTranscription
              check={check}
              onCancel={() => setEditing(false)}
              onRechecked={(data) => {
                setCheck(data);
                setEditing(false);
                setShowHint(false);
                setCardMsg("");
              }}
            />
          ) : (
            <>
              {check.problem && (
                <div className="rounded-xl bg-gray-50 px-4 py-3">
                  <p className="text-[11px] font-medium text-gray-400 mb-0.5">Problem</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{check.problem}</p>
                </div>
              )}

              {firstError != null && check.hint && (
                showHint ? (
                  <div className="rounded-xl px-4 py-3 border border-indigo-100" style={{ background: "#EEF2FF" }}>
                    <p className="text-[11px] font-medium text-indigo-700 mb-0.5">💡 Hint</p>
                    <p className="text-sm text-gray-700">{check.hint}</p>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowHint(true)}
                    className="text-left rounded-xl px-4 py-2.5 border border-dashed border-indigo-200 text-sm text-indigo-700 hover:bg-indigo-50"
                  >
                    💡 Want to find it yourself first? Show a hint
                  </button>
                )
              )}

              <ol className="flex flex-col gap-2">
                {check.steps.map((step, i) => (
                  <StepRow key={`${check.updated_at}-${i}`} step={step} index={i} isFirstError={i === firstError} />
                ))}
              </ol>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-gray-50 px-4 py-3">
                  <p className="text-[11px] font-medium text-gray-400 mb-0.5">Your answer</p>
                  <p className="text-sm text-gray-800 font-mono break-words">{check.final_answer || "—"}</p>
                </div>
                <div className="rounded-xl px-4 py-3" style={{ background: "#F0FDF4" }}>
                  <p className="text-[11px] font-medium text-green-700 mb-0.5">
                    Correct answer{check.expected_answer ? " (your key)" : ""}
                  </p>
                  <p className="text-sm text-gray-800 font-mono break-words">{check.correct_answer || "—"}</p>
                </div>
              </div>
              {check.answer_matches_expected === false && (
                <p className="text-xs text-red-600">Your final answer doesn't match the answer key.</p>
              )}
              {check.rechecks > 0 && (
                <p className="text-[11px] text-gray-400">Re-checked with your corrected transcription ({check.rechecks}×).</p>
              )}
            </>
          )}
        </div>
      </div>

      {!editing && (
        <div className="flex flex-col gap-3">
          {actionError && <p className="text-xs text-red-500">{actionError}</p>}
          {cardMsg && <p className="text-xs text-indigo-600 bg-indigo-50 rounded-lg px-3 py-2">{cardMsg}</p>}
          <div className="flex flex-col sm:flex-row gap-3">
            {firstError != null && (
              <>
                <button
                  type="button"
                  onClick={saveCard}
                  disabled={savingCard || !!cardMsg}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-medium border border-indigo-200
                             text-indigo-700 bg-white hover:bg-indigo-50 disabled:opacity-60"
                >
                  {savingCard ? <Spinner color="text-indigo-600" /> : "🃏"} Save mistake as flashcard
                </button>
                <button
                  type="button"
                  onClick={askTutor}
                  className="flex-1 py-3 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50"
                >
                  💬 Ask the tutor why
                </button>
              </>
            )}
            <button
              type="button"
              onClick={onNew}
              className="flex-1 py-3 rounded-xl text-sm font-medium text-white hover:opacity-90"
              style={{ background: "#4F46E5" }}
            >
              Check another solution
            </button>
          </div>
          <button
            type="button"
            onClick={remove}
            disabled={deleting}
            className="self-end text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete this check"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function CheckWork() {
  usePageTitle("Check my work");
  const [check, setCheck] = useState(null);
  const [openError, setOpenError] = useState("");

  async function open(checkId) {
    setOpenError("");
    try {
      const res = await api.get(`/solutions/${checkId}`);
      setCheck(res.data);
    } catch (err) {
      setOpenError(getErrorMessage(err, "Could not open that check."));
    }
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
            <h1 className="text-3xl font-bold text-gray-900">Check my work</h1>
            <p className="text-sm text-gray-500 mt-1">
              Snap your handwritten working — find out exactly where it went wrong.
            </p>
          </div>
          {check && (
            <button
              type="button"
              onClick={() => setCheck(null)}
              className="text-xs px-3 py-1.5 rounded-xl border border-gray-200 text-gray-500 hover:bg-white"
            >
              ← All checks
            </button>
          )}
        </div>

        {openError && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{openError}</div>
        )}

        {check ? (
          <ResultPhase
            key={check.check_id}
            check={check}
            setCheck={setCheck}
            onNew={() => setCheck(null)}
            onDeleted={() => setCheck(null)}
          />
        ) : (
          <UploadPhase onChecked={setCheck} onOpen={open} />
        )}
      </div>
    </div>
  );
}
