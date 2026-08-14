/** Sidebar icons, traced from the mockup's inline SVGs. */

import type { ReactNode } from 'react';

import type { ToolRoute } from '../routes/routes';

type IconName = ToolRoute['icon'] | 'dashboard' | 'audit';

const PATHS: Record<IconName, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  monitor: (
    <>
      <path d="M9 7l-4 5 4 5" />
      <path d="M15 7l4 5-4 5" />
    </>
  ),
  scope: (
    <>
      <circle cx="12" cy="12" r="3" />
      <circle cx="12" cy="12" r="8.5" />
    </>
  ),
  drift: (
    <>
      <path d="M3 17l5-6 4 3 4-7 5 4" />
      <path d="M3 21h18" />
    </>
  ),
  checklist: (
    <>
      <path d="M4 7l2.5 2.5L11 5" />
      <path d="M4 17l2.5 2.5L11 15" />
      <path d="M14 8h6M14 18h6" />
    </>
  ),
  export: (
    <>
      <path d="M12 15V4" />
      <path d="M8 8l4-4 4 4" />
      <path d="M4 15v4h16v-4" />
    </>
  ),
  audit: (
    <>
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v4h4" />
      <path d="M9 13h6M9 17h4" />
    </>
  ),
};

export function Icon({ name, size = 15 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ position: 'relative', flex: 'none' }}
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

export function ThemeIcon({ dark }: { dark: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      aria-hidden="true"
    >
      {dark ? (
        <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z" />
      ) : (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </>
      )}
    </svg>
  );
}
