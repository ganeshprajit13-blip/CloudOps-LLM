/** Format an ISO date string to "Mar 15, 2026" */
export function fmtDate(d: string): string {
  try {
    return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return d
  }
}

/** Convert kebab-case scenario names to Title Case (e.g., "volte-call-drop-handover" → "Volte Call Drop Handover") */
export function humanize(name: string): string {
  return name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export const SEV: Record<string, string> = {
  P1: 'bg-red-100 text-red-700',
  P2: 'bg-amber-100 text-amber-700',
  P3: 'bg-blue-100 text-blue-600',
}
