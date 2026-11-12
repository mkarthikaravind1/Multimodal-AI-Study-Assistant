import { useEffect } from "react";

const APP_NAME = "Multimodal AI Study Assistant";

// Sets the browser tab title, e.g. usePageTitle("Quiz") → "Quiz | Multimodal AI Study Assistant"
export default function usePageTitle(page) {
  useEffect(() => {
    document.title = page ? `${page} | ${APP_NAME}` : APP_NAME;
  }, [page]);
}
