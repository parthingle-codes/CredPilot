import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'alert'
  | 'arrow-right'
  | 'broom'
  | 'check'
  | 'chevron-down'
  | 'clock'
  | 'code'
  | 'copy'
  | 'download'
  | 'edit'
  | 'external'
  | 'file'
  | 'gauge'
  | 'lock'
  | 'plus'
  | 'radar'
  | 'refresh'
  | 'server'
  | 'shield'
  | 'sparkles'
  | 'terminal'
  | 'trash'
  | 'wallet'
  | 'x'

const icons: Record<IconName, ReactNode> = {
  alert: (
    <>
      <path d="M12 3 2.8 19a1.4 1.4 0 0 0 1.2 2h16a1.4 1.4 0 0 0 1.2-2L12 3Z" />
      <path d="M12 9v4.5M12 17h.01" />
    </>
  ),
  'arrow-right': <path d="M4 12h16m-6-6 6 6-6 6" />,
  broom: (
    <>
      <path d="m14 4 6 6M13 5l6 6-7.5 7.5a5 5 0 0 1-7-7L13 5Z" />
      <path d="m4 20 3-3M6 14l4 4" />
    </>
  ),
  check: <path d="m4 12 5 5L20 6" />,
  'chevron-down': <path d="m6 9 6 6 6-6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  code: (
    <>
      <path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />
    </>
  ),
  copy: (
    <>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5" />
      <path d="M4 19h16" />
    </>
  ),
  edit: (
    <>
      <path d="M4 20h4l11-11a2.8 2.8 0 0 0-4-4L4 16v4Z" />
      <path d="m13.5 6.5 4 4" />
    </>
  ),
  external: (
    <>
      <path d="M14 4h6v6M20 4l-9 9" />
      <path d="M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4" />
    </>
  ),
  file: (
    <>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z" />
      <path d="M14 3v6h6" />
    </>
  ),
  gauge: (
    <>
      <path d="M4.5 18a9 9 0 1 1 15 0" />
      <path d="m12 14 4-4" />
      <circle cx="12" cy="15" r="1.5" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  radar: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5.5" opacity=".55" />
      <circle cx="12" cy="12" r="2" opacity=".75" />
      <path d="M12 12 18.5 5.5" />
      <circle cx="16.5" cy="8.5" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7v5h-5" />
      <path d="M19 12a7 7 0 1 0-2 5" />
    </>
  ),
  server: (
    <>
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 7.5h.01M7 16.5h.01" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  sparkles: (
    <>
      <path d="M12 3.5 13.6 9 19 10.5 13.6 12 12 17.5 10.4 12 5 10.5 10.4 9 12 3.5Z" />
      <path d="M19 16v4M17 18h4M5 3v3M3.5 4.5h3" />
    </>
  ),
  terminal: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="m7 9 3 3-3 3M13 15h4" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
      <path d="M10 11v5M14 11v5" />
    </>
  ),
  wallet: (
    <>
      <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H19v16H6.5A2.5 2.5 0 0 1 4 17.5v-11Z" />
      <path d="M4 7h15M15 12h5v4h-5a2 2 0 0 1 0-4Z" />
    </>
  ),
  x: <path d="M6 6l12 12M18 6 6 18" />,
}

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  size?: number
  strokeWidth?: number
}

export function Icon({
  name,
  size = 18,
  strokeWidth = 1.8,
  className,
  ...props
}: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
      {...props}
    >
      {icons[name]}
    </svg>
  )
}

export function BrandMark({ size = 38 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      className="brand-mark"
    >
      <path
        d="M32 5.5 54.5 18.5v27L32 58.5 9.5 45.5v-27L32 5.5Z"
        stroke="currentColor"
        strokeWidth="2"
        opacity=".85"
      />
      <path
        d="M32 15.5 46.5 32 32 48.5 17.5 32 32 15.5Z"
        stroke="var(--cyan)"
        strokeWidth="1.8"
        opacity=".9"
      />
      <circle cx="32" cy="32" r="3.4" fill="currentColor" />
      <path
        d="M32 18v5M32 41v5M19 32h5M40 32h5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        opacity=".8"
      />
    </svg>
  )
}
