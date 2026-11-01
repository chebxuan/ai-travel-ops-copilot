// Original vector placeholders. Destination photography will be selected next round.
export default function ScenicArt({ theme = "mountains", className = "" }) {
  const warm = theme === "city";
  const blue = theme === "river";
  const sky = warm ? "#d8c6a8" : blue ? "#bfd0cc" : "#cdd5bd";
  const back = warm ? "#a69a79" : blue ? "#79968d" : "#8fa485";
  const front = warm ? "#5a6c52" : blue ? "#3c675e" : "#41654d";
  return <svg className={className} viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice" role="img" aria-label="旅行风景示意插画，非目的地实景">
    <rect width="800" height="600" fill={sky} />
    <circle cx="610" cy="128" r="59" fill="#f2e3b9" />
    <path d="M0 320C65 260 100 265 162 185C216 106 253 253 305 246C369 238 401 111 457 167C515 226 552 277 611 261C678 242 744 189 800 222V600H0Z" fill={back} opacity=".6" />
    <path d="M0 392C65 401 74 353 128 311C167 274 193 319 218 349C251 390 282 360 321 288C351 232 377 267 416 326C455 385 481 382 522 343C579 289 612 310 658 337C702 363 742 319 800 342V600H0Z" fill={back} />
    <path d="M0 470C100 420 155 463 251 434C345 407 413 453 486 428C604 387 672 431 800 396V600H0Z" fill={front} />
    <path d="M800 431C586 393 649 456 479 475C339 491 514 533 300 550L178 600H493C585 562 547 531 645 513C743 494 662 471 800 468Z" fill="#d9dfce" opacity=".9" />
    <path d="M0 545C137 479 211 527 334 571L423 600H0Z" fill="#244936" />
    <path d="M535 101q12-12 24 0m24 13q12-12 24 0" fill="none" stroke="#536b50" strokeWidth="3" strokeLinecap="round" />
    {warm && <g fill="#334f3c"><rect x="166" y="359" width="53" height="73" /><path d="m142 361 51-25 52 25Zm-8-18 59-30 60 30Zm18-29 41-23 42 23Z" /><rect x="189" y="279" width="6" height="25" /></g>}
    {blue && <g fill="#2f5046"><path d="M440 503h67l-14 13h-38Z" /><path d="M476 452v49h-25Z" fill="#e9e2ce" /></g>}
  </svg>;
}
