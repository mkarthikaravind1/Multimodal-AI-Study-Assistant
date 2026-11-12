import { useEffect, useRef, useState } from "react";
import api, { getErrorMessage } from "../api/axios";

const EXTENSIONS = { "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "video/webm": "webm" };

/**
 * Records from the microphone and transcribes with Whisper (/upload/audio).
 * start() asks for the mic and starts recording; stop() ends it, uploads the
 * audio and calls onTranscript(text). The mic is released when the
 * component unmounts.
 */
export default function useVoiceRecorder(onTranscript) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState("");

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const unmountedRef = useRef(false);
  const onTranscriptRef = useRef(onTranscript);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function start() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (unmountedRef.current) return;
        setTranscribing(true);
        try {
          // Label the file with the format actually recorded (Chrome webm, Firefox ogg, Safari mp4)
          const mimeType = (recorder.mimeType || "audio/webm").split(";")[0];
          const blob = new Blob(chunksRef.current, { type: mimeType });
          const form = new FormData();
          form.append("file", blob, `answer.${EXTENSIONS[mimeType] || "webm"}`);
          const res = await api.post("/upload/audio", form, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          onTranscriptRef.current?.(String(res.data.transcript || "").trim());
        } catch (err) {
          setError(getErrorMessage(err, "Transcription failed. Please try again or type your answer."));
        } finally {
          setTranscribing(false);
        }
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("Microphone access denied. Allow it in your browser, or type your answer.");
    }
  }

  function stop() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    setRecording(false);
  }

  return { recording, transcribing, error, start, stop };
}
