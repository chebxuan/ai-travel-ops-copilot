const paths = {
  arrow: <path d="M4 12h15M13 5l7 7-7 7" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  location: <><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18" /></>,
  compass: <><circle cx="12" cy="12" r="9" /><path d="m16 8-2 6-6 2 2-6 6-2Z" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  leaf: <><path d="M20 3c-9-1-16 3-16 10a7 7 0 0 0 7 7c7 0 9-8 9-17ZM5 19 16 8" /></>,
  people: <><circle cx="9" cy="7" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-17a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5v2" /></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
};
export default function Icon({ name = "arrow", size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.arrow}</svg>;
}
