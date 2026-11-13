import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import MarkdownContent from "../components/MarkdownContent";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

/**
 * A clean, printable copy of one lesson. Opens in a new tab from the lesson card,
 * then the browser's print dialog does the rest ("Save as PDF").
 * No server-side PDF library needed.
 */
export default function LessonPrint() {
  const { noteId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");
  const printed = useRef(false);
  usePageTitle(lesson ? lesson.title : "Print lesson");

  useEffect(() => {
    api
      .get(`/lessons/${noteId}`)
      .then((res) => setLesson(res.data))
      .catch((err) => setError(getErrorMessage(err, "Couldn't load this lesson.")));
  }, [noteId]);

  // open the print dialog once, after the lesson has rendered
  useEffect(() => {
    if (!lesson || printed.current) return;
    // the flag is set when the dialog actually opens — a cancelled timer (React
    // re-running the effect) must not count as "already printed"
    const t = setTimeout(() => {
      printed.current = true;
      window.print();
    }, 400);
    return () => clearTimeout(t);
  }, [lesson]);

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16 text-center">
        <p className="text-sm text-red-600 mb-4">{error}</p>
        <Link to="/lesson" className="text-sm text-indigo-600 hover:underline">← Back to lessons</Link>
      </div>
    );
  }
  if (!lesson) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Spinner size={5} color="text-indigo-600" />
      </div>
    );
  }

  const date = lesson.created_at
    ? new Date(lesson.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })
    : "";

  return (
    <div className="min-h-screen bg-gray-100 print:bg-white py-8 print:py-0">
      {/* toolbar — not printed */}
      <div className="no-print max-w-3xl mx-auto px-6 mb-4 flex items-center justify-between gap-3">
        <Link to="/lesson" className="text-sm text-gray-500 hover:text-indigo-600">← Back to lessons</Link>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 hidden sm:inline">Choose “Save as PDF” as the printer</span>
          <button
            type="button"
            onClick={() => window.print()}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
            style={{ background: "#4F46E5" }}
          >
            🖨 Print / Save as PDF
          </button>
        </div>
      </div>

      <article className="print-flat max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-gray-200 px-10 py-10 print:max-w-none">
        <header className="border-b-2 border-indigo-600 pb-3 mb-6">
          <p className="text-xs uppercase tracking-widest text-indigo-600 font-semibold">Study notes</p>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">{lesson.title}</h1>
          {date && <p className="text-xs text-gray-500 mt-1">{date}</p>}
        </header>

        <div className="text-[15px] leading-relaxed text-gray-800">
          <MarkdownContent content={lesson.content} />
        </div>

        {lesson.youtube_links?.length > 0 && (
          <section className="mt-8 pt-4 border-t border-gray-200">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Watch next</h2>
            <ul className="text-sm space-y-1">
              {lesson.youtube_links.map((url, i) => (
                <li key={url}>
                  <a href={url} className="print-url text-indigo-600 hover:underline" target="_blank" rel="noopener noreferrer">
                    {i === 0 ? "Explainer videos on YouTube" : "Tutorials on YouTube"}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="mt-10 pt-3 border-t border-gray-100 text-[11px] text-gray-400">
          Made with Multimodal AI Study Assistant
        </footer>
      </article>
    </div>
  );
}
