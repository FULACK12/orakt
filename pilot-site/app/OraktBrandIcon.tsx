/** Original orbital line mark, with heavier strokes for small displays. */
export default function OraktBrandIcon({ className, size = 44 }: { className?: string; size?: number }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 44 44" fill="none" aria-hidden="true" focusable="false">
    <circle cx="22" cy="22" r="16.5" style={{stroke:"currentColor",strokeWidth:2.6,fill:"none"}} />
    <circle cx="22" cy="22" r="8" style={{stroke:"var(--orakt-cyan, #00c9e0)",strokeWidth:2.6,fill:"none"}} />
    <path d="M31.5 10.5 17.8 24.2 31.8 38.2" strokeLinecap="round" strokeLinejoin="round" style={{stroke:"var(--orakt-lime, #a3ff12)",strokeWidth:3.1,fill:"none"}} />
    <circle cx="32" cy="10" r="2.8" style={{fill:"var(--orakt-lime, #a3ff12)",stroke:"none"}} />
  </svg>;
}
