import type {
  Category,
  Priority,
  RiskLevel,
  Severity,
} from '../types'

export const severityOrder: Severity[] = [
  'critical',
  'high',
  'medium',
  'low',
  'info',
]

export const categoryOrder: Category[] = [
  'billing',
  'deployment',
  'security',
  'cleanup',
]

export const priorityOrder: Priority[] = ['now', 'before-demo', 'after-demo']

export const severityLabels: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export const categoryLabels: Record<Category, string> = {
  billing: 'Billing',
  deployment: 'Deployment',
  security: 'Security',
  cleanup: 'Cleanup',
}

export const priorityLabels: Record<Priority, string> = {
  now: 'Now',
  'before-demo': 'Before demo',
  'after-demo': 'After demo',
}

export const riskLabels: Record<RiskLevel, string> = {
  clear: 'Clear',
  low: 'Low',
  elevated: 'Elevated',
  high: 'High',
  critical: 'Critical',
}

export interface RiskCopy {
  headline: string
  subline: string
}

export const riskCopy: Record<RiskLevel, RiskCopy> = {
  critical: {
    headline: 'Stop and fix before deploying.',
    subline:
      'Critical exposures are present. Treat credentials and host access as compromised until reviewed.',
  },
  high: {
    headline: 'Fix the high-impact issues first.',
    subline:
      'Billing or security risks need a decision before you share the demo link.',
  },
  elevated: {
    headline: 'Review before you share the link.',
    subline:
      'Several limits or risks deserve a manual check. The score is a heuristic, not a bill estimate.',
  },
  low: {
    headline: 'Mostly clear — verify the checklist.',
    subline:
      'Only low-impact items were flagged. Confirm provider limits and cleanup manually.',
  },
  clear: {
    headline: 'No rule-based red flags found.',
    subline:
      'This is not proof of safety. Only the submitted configuration was checked.',
  },
}

const formatLabels: Record<string, string> = {
  render: 'Render',
  compose: 'Compose',
  dotenv: 'Dotenv',
  unknown: 'Unknown',
}

export function detectFormat(path: string, content: string): string {
  const name = path.replace(/\\/g, '/').split('/').pop()?.toLowerCase() ?? ''
  if (name === 'render.yaml' || name === 'render.yml') return 'render'
  if (
    ['docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'].includes(
      name,
    ) ||
    name.startsWith('docker-compose.')
  ) {
    return 'compose'
  }
  if (name === '.env' || name.startsWith('.env.') || name.endsWith('.env')) {
    return 'dotenv'
  }
  if (/^\s*services\s*:/m.test(content)) {
    if (/^\s*(databases|envVarGroups|previews)\s*:/m.test(content)) return 'render'
    if (/^\s*(?:-\s*)?type\s*:/m.test(content)) return 'render'
    if (/^\s+(image|build)\s*:/m.test(content)) return 'compose'
  }
  if (/^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_.-]*\s*=/m.test(content)) {
    return 'dotenv'
  }
  return 'unknown'
}

export function formatLabel(format: string): string {
  return formatLabels[format] ?? 'Unknown'
}

export function basename(path: string): string {
  return path.replace(/\\/g, '/').split('/').pop() || path
}

export function byteLength(value: string): number {
  return new TextEncoder().encode(value).length
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

export function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function slugify(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48) || 'credpilot'
  )
}

export function plural(count: number, singular: string, pluralForm?: string): string {
  return count === 1 ? singular : (pluralForm ?? `${singular}s`)
}

export function uniquePath(desired: string, existing: string[]): string {
  const lower = new Set(existing.map((path) => path.toLowerCase()))
  if (!lower.has(desired.toLowerCase())) return desired

  // Keep dotfiles recognizable: `.env` -> `.env.2`, not `.env-2`.
  const slash = desired.lastIndexOf('/')
  const directory = slash >= 0 ? desired.slice(0, slash + 1) : ''
  const name = desired.slice(directory.length)
  const dot = name.lastIndexOf('.')
  const isDotfile = dot === 0
  const stem = dot > 0 ? name.slice(0, dot) : name
  const suffix = dot > 0 ? name.slice(dot) : ''

  let index = 2
  while (
    lower.has(
      `${directory}${stem}${isDotfile ? `${suffix}.${index}` : `-${index}${suffix}`}`.toLowerCase(),
    )
  ) {
    index += 1
  }
  return `${directory}${stem}${isDotfile ? `${suffix}.${index}` : `-${index}${suffix}`}`
}

export function scrollToResults(): void {
  if (typeof window === 'undefined' || window.innerWidth >= 1100) return
  window.requestAnimationFrame(() => {
    document.getElementById('results')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  })
}
