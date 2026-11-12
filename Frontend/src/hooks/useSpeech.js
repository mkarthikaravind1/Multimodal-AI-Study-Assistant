import { useCallback, useEffect, useState } from "react";

const supported = typeof window !== "undefined" && "speechSynthesis" in window;

// Pick a natural-sounding English voice if the browser has one
function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
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
    const voice = pickVoice();
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
