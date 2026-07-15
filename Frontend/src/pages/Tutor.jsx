import { useEffect, useRef, useState } from "react";
import api from "../api/axios";
import MarkdownContent from "../components/MarkdownContent";

// ── icons ─────────────────────────────────────────────────────────────────────

function SendIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
      <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
    </svg>
  );
}

function PaperclipIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className="w-5 h-5">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66L9.41 17.41a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function MicIcon({ active }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className="w-5 h-5">
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

// ── FIX 2: Spinner with actual SVG content ────────────────────────────────────
function Spinner({ size = 4, color = "text-white" }) {
  return (
    <svg className={`animate-spin h-${size} w-${size} ${color}`}
      xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
      className="w-3.5 h-3.5 text-white">
      <path fillRule="evenodd"
        d="M19.916 4.626a.75.75 0 01.208 1.04l-9 13.5a.75.75 0 01-1.154.114l-6-6a.75.75 0 011.06-1.06l5.353 5.353 8.493-12.739a.75.75 0 011.04-.208z"
        clipRule="evenodd" />
    </svg>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────

function detectType(file) {
  if (file.type === "application/pdf") return "pdf";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  return null;
}

// ── attachment preview ────────────────────────────────────────────────────────

function AttachmentPreview({ attachment, onRemove }) {
  const { file, type, previewUrl, status } = attachment;

  return (
    <div className="relative inline-flex flex-col items-center gap-1 mr-2">
      <div
        className="relative rounded-xl overflow-hidden border border-gray-200 bg-gray-50
                   flex items-center justify-center"
        style={{ width: 72, height: 72 }}
      >
        {type === "image" && previewUrl && (
          <img src={previewUrl} alt={file.name} className="w-full h-full object-cover" />
        )}
        {type === "video" && previewUrl && (
          <video src={previewUrl} className="w-full h-full object-cover" muted />
        )}
        {type === "pdf" && (
          <div className="flex flex-col items-center gap-1 px-2 text-center">
            <span className="text-2xl">📄</span>
            <p className="text-xs text-gray-500 truncate w-full">{file.name}</p>
          </div>
        )}

        {status === "uploading" && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <Spinner size={5} color="text-white" />
          </div>
        )}

        {status === "done" && (
          <div className="absolute bottom-1 right-1 w-5 h-5 rounded-full bg-green-500
                          flex items-center justify-center shadow">
            <CheckIcon />
          </div>
        )}

        {status === "error" && (
          <div className="absolute inset-0 bg-red-400/30 flex items-center justify-center">
            <span className="text-red-600 font-bold text-sm">!</span>
          </div>
        )}

        {status !== "uploading" && (
          <button
            onClick={onRemove}
            className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/50
                       text-white flex items-center justify-center text-xs leading-none
                       hover:bg-black/70 transition-colors"
          >×</button>
        )}
      </div>
      <p className="text-xs text-gray-400 truncate max-w-[72px]">{file.name}</p>
    </div>
  );
}

// ── message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} gap-2`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm
                        flex-shrink-0 mt-0.5" style={{ background: "#EEF2FF" }}>
          🤖
        </div>
      )}

      <div className="max-w-[75%] flex flex-col gap-2 items-end">
        {message.attachment && (
          <div className="rounded-2xl overflow-hidden border border-gray-100 shadow-sm self-end"
            style={{ maxWidth: 220 }}>
            {message.attachment.type === "image" && (
              <img src={message.attachment.previewUrl} alt="attachment"
                className="w-full object-cover" />
            )}
            {message.attachment.type === "video" && (
              <video src={message.attachment.previewUrl} controls
                className="w-full" style={{ maxHeight: 160 }} />
            )}
            {message.attachment.type === "pdf" && (
              <div className="flex items-center gap-2 px-3 py-2 bg-indigo-50">
                <span className="text-lg">📄</span>
                <p className="text-xs font-medium text-indigo-700 truncate">
                  {message.attachment.filename}
                </p>
              </div>
            )}
          </div>
        )}

        {message.content && (
          <div
            className="px-4 py-3 rounded-2xl text-sm leading-relaxed"
            style={
              isUser
                ? { background: "#4F46E5", color: "#fff", borderBottomRightRadius: 4 }
                : { background: "#fff", color: "#1F2937", border: "1px solid #E5E7EB", borderBottomLeftRadius: 4 }
            }
          >
            {isUser
              ? <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
              : <MarkdownContent content={message.content} />
            }
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm
                        flex-shrink-0 mt-0.5" style={{ background: "#EEF2FF" }}>
          🧑
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start gap-2">
      <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm
                      flex-shrink-0" style={{ background: "#EEF2FF" }}>🤖</div>
      <div className="px-4 py-3 rounded-2xl flex items-center gap-1.5"
        style={{ background: "#fff", border: "1px solid #E5E7EB", borderBottomLeftRadius: 4 }}>
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-400"
            style={{ animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function Tutor() {
  const [messages, setMessages]       = useState([]);
  const [sessionId, setSessionId]     = useState(null);
  const [input, setInput]             = useState("");
  const [sending, setSending]         = useState(false);
  const [chatError, setChatError]     = useState("");

  const [attachment, setAttachment] = useState(null);
  const fileInputRef = useRef(null);

  const [micActive, setMicActive]       = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [micError, setMicError]         = useState("");
  const mediaRecorderRef = useRef(null);
  const audioChunksRef   = useRef([]);

  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  // ── auto scroll ──────────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // ── file selection ───────────────────────────────────────────────────────────
  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const type = detectType(file);
    if (!type) {
      setChatError("Unsupported file. Attach a PDF, image (JPEG/PNG/WebP), or video (MP4/WebM/MOV).");
      return;
    }
    const previewUrl = (type === "image" || type === "video")
      ? URL.createObjectURL(file)
      : null;
    setAttachment({ file, type, previewUrl, status: "pending", result: null });
    setChatError("");
  }

  // ── FIX 1: removeAttachment is a proper function, no floating code ────────────
  function removeAttachment() {
    if (attachment?.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    setAttachment(null);
  }

  // ── upload file ───────────────────────────────────────────────────────────────
  async function uploadFile(file, type, question) {
    const form = new FormData();
    form.append("file", file);
    if (type === "image") form.append("question", question || "Explain this image in detail.");
    const endpoint = { pdf: "/upload/pdf", image: "/upload/image", video: "/upload/video" }[type];
    try {
      const res = await api.post(endpoint, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return { ok: true, result: res.data };
    } catch (err) {
      return { ok: false, error: err.response?.data?.detail || "Upload failed." };
    }
  }

  // ── send ──────────────────────────────────────────────────────────────────────
  async function handleSend(e) {
    e?.preventDefault();
    const text = input.trim();
    if ((!text && !attachment) || sending) return;
    if (attachment?.status === "uploading") {
      setChatError("Please wait — file is still uploading.");
      return;
    }
    if (attachment?.status === "error") {
      setChatError("Attachment failed. Remove it and try again.");
      return;
    }

    setSending(true);
    setChatError("");
    const currentAttachment = attachment;

    // upload if pending
    let uploadResult = null;
    if (currentAttachment?.status === "pending") {
      setAttachment((a) => ({ ...a, status: "uploading" }));
      const { ok, result, error } = await uploadFile(
        currentAttachment.file,
        currentAttachment.type,
        text
      );
      if (!ok) {
        setAttachment((a) => ({ ...a, status: "error" }));
        setChatError(error);
        setSending(false);
        return;
      }
      uploadResult = result;
      setAttachment((a) => ({ ...a, status: "done", result }));
    }

    // add user message
    const userMessage = {
      role: "user",
      content: text,
      attachment: currentAttachment
        ? { type: currentAttachment.type, previewUrl: currentAttachment.previewUrl, filename: currentAttachment.file.name }
        : null,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // image: answer comes directly from upload response
    if (currentAttachment?.type === "image" && uploadResult?.answer) {
      setMessages((prev) => [...prev, { role: "assistant", content: uploadResult.answer, attachment: null }]);
      setAttachment(null);
      setSending(false);
      return;
    }

    if (currentAttachment) setAttachment(null);

    // build chat message — always include filename for pdf/video so RAG hits correctly
    let chatMessage = text;
    if (currentAttachment?.type === "pdf") {
      const userIntent = text || "Please summarise what this PDF covers.";
      chatMessage = `Regarding the PDF I just uploaded (filename: ${currentAttachment.file.name}): ${userIntent}`;
    }
    if (currentAttachment?.type === "video") {
      const userIntent = text || "Please summarise what this video covers.";
      chatMessage = `Regarding the video I just uploaded (filename: ${currentAttachment.file.name}): ${userIntent}`;
    }

    // call /chat
    try {
      const res = await api.post("/chat", {
        message: chatMessage,
        session_id: sessionId ?? null,
      });
      const assistantReply = res.data.messages[res.data.messages.length - 1];
      setMessages((prev) => [...prev, { ...assistantReply, attachment: null }]);
      setSessionId(res.data.session_id);
    } catch (err) {
      setChatError(err.response?.data?.detail || "Message failed. Try again.");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // ── microphone ────────────────────────────────────────────────────────────────
  async function handleMicToggle() {
    setMicError("");
    if (micActive) {
      mediaRecorderRef.current?.stop();
      setMicActive(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setTranscribing(true);
        try {
          const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          const form = new FormData();
          form.append("file", blob, "recording.webm");
          const res = await api.post("/upload/audio", form, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          setInput((prev) => prev ? prev + " " + res.data.transcript : res.data.transcript);
          inputRef.current?.focus();
        } catch {
          setMicError("Transcription failed. Please try again.");
        } finally {
          setTranscribing(false);
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setMicActive(true);
    } catch {
      setMicError("Microphone access denied. Please allow it in your browser.");
    }
  }

  function handleNewSession() {
    setMessages([]);
    setSessionId(null);
    setChatError("");
    removeAttachment();
    inputRef.current?.focus();
  }

  const canSend = (input.trim() || attachment) && !sending && (!attachment || attachment.status !== "uploading");

  // ── render ────────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-5px); }
        }
        @keyframes pulse-ring {
          0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
          70%  { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
          100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
        }
      `}</style>

      <div className="flex flex-col" style={{ height: "calc(100vh - 52px)", background: "#F8F7FF" }}>

        {/* ── top bar ── */}
        <div className="flex-shrink-0 bg-white border-b border-gray-100 px-6 py-3
                        flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xl">💬</span>
            <div>
              <h1 className="text-sm font-semibold text-gray-800">AI Tutor</h1>
              {sessionId && <p className="text-xs text-gray-400">Session #{sessionId}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {messages.length > 0 && (
              <button onClick={handleNewSession}
                className="text-xs px-3 py-1.5 rounded-xl border border-gray-200 text-gray-500
                           hover:bg-gray-50 transition-colors">
                New session
              </button>
            )}
          </div>
        </div>

        {/* ── messages ── */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6">
          <div className="max-w-3xl mx-auto flex flex-col gap-4">

            {messages.length === 0 && !sending && (
              <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl"
                  style={{ background: "#EEF2FF" }}>🤖</div>
                <div>
                  <p className="text-base font-semibold text-gray-800">Ask me anything</p>
                  <p className="text-sm text-gray-400 mt-1 max-w-sm">
                    Type a question, attach a PDF / image / video using the paperclip,
                    or press the mic to speak.
                  </p>
                </div>
                <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
                  {["Explain this topic in simple terms", "Give me a real-world example", "What are common mistakes to avoid?"].map((s) => (
                    <button key={s}
                      onClick={() => { setInput(s); inputRef.current?.focus(); }}
                      className="text-left px-4 py-2.5 rounded-xl text-sm text-gray-600
                                 border border-gray-200 bg-white hover:border-indigo-300
                                 hover:text-indigo-600 transition-colors">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => <MessageBubble key={idx} message={msg} />)}
            {sending && <TypingIndicator />}

            {chatError && (
              <div className="text-center">
                <p className="text-xs text-red-500 bg-red-50 px-4 py-2 rounded-xl
                               inline-block border border-red-100">{chatError}</p>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* ── input area ── */}
        <div className="flex-shrink-0 bg-white border-t border-gray-100 px-4 sm:px-8 py-4">
          <div className="max-w-3xl mx-auto">

            {attachment && (
              <div className="flex items-end mb-3 ml-1">
                <AttachmentPreview attachment={attachment} onRemove={removeAttachment} />
              </div>
            )}

            {micError && <p className="text-xs text-red-500 mb-2 ml-1">{micError}</p>}
            {transcribing && (
              <div className="flex items-center gap-2 mb-2 ml-1">
                <Spinner size={3} color="text-indigo-500" />
                <p className="text-xs text-indigo-500">Transcribing…</p>
              </div>
            )}

            <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl
                            px-3 py-2 shadow-sm focus-within:ring-2 focus-within:ring-indigo-500
                            focus-within:border-transparent transition-all">

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={!!attachment || sending}
                title="Attach PDF, image, or video"
                className="flex-shrink-0 mb-1 p-1 rounded-lg text-gray-400
                           hover:text-indigo-500 hover:bg-indigo-50 disabled:opacity-30
                           transition-colors"
              >
                <PaperclipIcon />
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/jpg,image/webp,video/mp4,video/mpeg,video/webm,video/quicktime"
                className="hidden"
                onChange={handleFileChange}
              />

              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  micActive ? "Listening…"
                  : attachment?.type === "image" ? "Ask a question about this image…"
                  : "Ask a question… (Enter to send, Shift+Enter for newline)"
                }
                rows={1}
                disabled={sending || micActive}
                className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-300
                           focus:outline-none resize-none leading-relaxed py-1 disabled:opacity-60"
                style={{ maxHeight: 140, overflowY: "auto" }}
                onInput={(e) => {
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
                }}
              />

              <button
                type="button"
                onClick={handleMicToggle}
                disabled={sending || transcribing || !!attachment}
                title={micActive ? "Stop recording" : "Start voice input"}
                className="flex-shrink-0 mb-1 p-1 rounded-lg disabled:opacity-30 transition-colors"
                style={{
                  color: micActive ? "#EF4444" : "#9CA3AF",
                  animation: micActive ? "pulse-ring 1.2s ease-out infinite" : "none",
                }}
              >
                <MicIcon active={micActive} />
              </button>

              <button
                type="button"
                onClick={handleSend}
                disabled={!canSend}
                className="flex-shrink-0 mb-1 w-8 h-8 rounded-xl flex items-center justify-center
                           text-white transition-opacity hover:opacity-90 disabled:opacity-30"
                style={{ background: "#4F46E5" }}
              >
                {sending ? <Spinner size={4} /> : <SendIcon />}
              </button>
            </div>

            <p className="text-xs text-gray-300 mt-2 text-center">
              Paperclip → attach PDF / image / video · Mic → speak your question · Enter to send
            </p>
          </div>
        </div>
      </div>
    </>
  );
}