// Tailwind only generates classes it can find written out in full in the source,
// so sizes are listed literally here instead of built like `h-${size}`.
const SIZES = {
  3: "h-3 w-3",
  4: "h-4 w-4",
  5: "h-5 w-5",
};

export default function Spinner({ size = 4, color = "text-white" }) {
  return (
    <svg
      className={`animate-spin ${SIZES[size] ?? SIZES[4]} ${color}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
