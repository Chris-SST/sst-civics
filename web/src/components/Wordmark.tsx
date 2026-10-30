import { BRAND_NAME } from "../brand";

/** The speech-bubble mark: no letters, so a rename only changes the text beside it. */
export function BrandMark({ size = 38 }: { size?: number }) {
  return (
    <span className="wordmark-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={(size * 24) / 38} height={(size * 20) / 38} viewBox="0 0 24 20" focusable="false">
        <path d="M2 3h14a4 4 0 0 1 0 8H8l-4 4V3z" fill="var(--on-accent)" />
        <circle cx="19" cy="14" r="4" fill="var(--primary)" />
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
