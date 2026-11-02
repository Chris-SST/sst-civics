import { BRAND_NAME } from "../brand";

/** The speech-bubble mark: no letters, so a rename only changes the text beside it. */
export function BrandMark({ size = 40 }: { size?: number }) {
  return (
    <span className="wordmark-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={(size * 26) / 40} height={(size * 26) / 40} viewBox="0 0 32 32" focusable="false">
        <path d="M6 8h14a4 4 0 0 1 0 8H12l-4 4V8z" fill="var(--on-primary)" />
        <circle cx="23" cy="21" r="4" fill="var(--accent)" />
      </svg>
    </span>
  );
}

/** Brand name as text beside the mark. The name comes from `brand.ts`. */
export default function Wordmark({ small = false }: { small?: boolean }) {
  return (
    <span className={`wordmark${small ? " wordmark-sm" : ""}`}>
      <BrandMark />
      <span className="wordmark-name">{BRAND_NAME}</span>
    </span>
  );
}
