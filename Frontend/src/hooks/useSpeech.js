import { useCallback, useEffect, useState } from "react";

const supported = typeof window !== "undefined" && "speechSynthesis" in window;

// Language of the text from its script: Devanagari → Hindi, Tamil script → Tamil.
// Hinglish / Tanglish are written in English letters, so an Indian-English voice reads them best.
export function speechLang(text) {
  const letters = (text.match(/\p{L}/gu) || []).length || 1;
  const deva = (text.match(/[\u0900-\u097F]/g) || []).length;
  const tamil = (text.match(/[\u0B80-\u0BFF]/g) || []).length;
  if (Math.max(deva, tamil) / letters >= 0.15) return deva >= tamil ? "hi-IN" : "ta-IN";
  return "en-IN";
}

// Pick a natural-sounding voice for the language, if the browser has one
function pickVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  const base = lang.slice(0, 2);
  if (base !== "en") {
    return (
      voices.find((v) => v.lang.replace("_", "-").toLowerCase() === lang.toLowerCase()) ||
      voices.find((v) => v.lang.toLowerCase().startsWith(base)) ||
      null // no voice installed: utterance.lang still lets the browser try
    );
  }
  return (
    voices.find((v) => /en-IN/i.test(v.lang)) ||
    voices.find((v) => /en[-_]/i.test(v.lang) && /natural|google|microsoft/i.test(v.name)) ||
    voices.find((v) => /^en/i.test(v.lang)) ||
    null
  );
}

/**
 * Text-to-speech with the browser's built-in voices (free, no API).
 * speak(text) reads it aloud; stop() cuts it off. Speech stops when the
 * component unmounts.
 */
export default function useSpeech() {
  const [speaking, setSpeaking] = useState(false);

  const stop = useCallback(() => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  const speak = useCallback((text) => {
    if (!supported || !text) return;
    window.speechSynthesis.cancel();
    // strip markdown symbols so they aren't read out
    const utterance = new SpeechSynthesisUtterance(text.replace(/[*_#`>]/g, ""));
    const lang = speechLang(text);
    utterance.lang = lang;
    const voice = pickVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.rate = 0.95;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }, []);

  useEffect(() => () => supported && window.speechSynthesis.cancel(), []);

  return { speak, stop, speaking, supported };
}
