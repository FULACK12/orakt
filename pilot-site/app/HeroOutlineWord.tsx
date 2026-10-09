/** Closed letter contours avoid overlapping font-component strokes in Safari. */
export default function HeroOutlineWord({ className }: { className?: string }) {
  return <svg className={className} data-hero-word="MOVES" viewBox="0 0 484 108" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
    <path data-letter="M" d="M4 6H26L50 65L74 6H96V102H77V39L59 84H41L23 39V102H4Z" />
    <path data-letter="O" d="M154 4C124 4 108 23 108 54C108 85 124 104 154 104C184 104 200 85 200 54C200 23 184 4 154 4ZM154 23C172 23 179 35 179 54C179 73 172 85 154 85C136 85 129 73 129 54C129 35 136 23 154 23Z" />
    <path data-letter="V" d="M210 6H232L258 79L284 6H306L270 102H246Z" />
    <path data-letter="E" d="M318 6H383V25H339V44H379V63H339V83H383V102H318Z" />
    <path data-letter="S" d="M476 33H456C455 25 449 21 439 21C429 21 423 25 423 31C423 38 430 41 444 44C467 49 480 56 480 74C480 94 464 104 441 104C416 104 399 91 398 70H419C420 81 428 86 441 86C452 86 460 82 460 76C460 69 453 66 438 63C415 58 403 51 403 33C403 15 417 4 439 4C461 4 475 15 476 33Z" />
  </svg>;
}
