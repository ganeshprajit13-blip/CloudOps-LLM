export interface DomainTag {
  /** Short industry label for display in pills/badges (e.g., "Gaming", "Healthcare") */
  label: string
  /** First segment of the full domain string (e.g., "Video Streaming") */
  primary: string
  secondary?: string
  bg: string
  text: string
  dot: string
}

interface DomainEntry { label: string; bg: string; text: string; dot: string }

const DOMAIN_COLORS: Record<string, DomainEntry> = {
  video:       { label: 'Streaming',      bg: 'bg-purple-100',  text: 'text-purple-700',  dot: 'bg-purple-500' },
  media:       { label: 'Streaming',      bg: 'bg-purple-100',  text: 'text-purple-700',  dot: 'bg-purple-500' },
  streaming:   { label: 'Streaming',      bg: 'bg-purple-100',  text: 'text-purple-700',  dot: 'bg-purple-500' },
  gaming:      { label: 'Gaming',         bg: 'bg-green-100',   text: 'text-green-700',   dot: 'bg-green-500' },
  multiplayer: { label: 'Gaming',         bg: 'bg-green-100',   text: 'text-green-700',   dot: 'bg-green-500' },
  esports:     { label: 'Gaming',         bg: 'bg-green-100',   text: 'text-green-700',   dot: 'bg-green-500' },
  pharma:      { label: 'Healthcare',     bg: 'bg-teal-100',    text: 'text-teal-700',    dot: 'bg-teal-500' },
  drug:        { label: 'Healthcare',     bg: 'bg-teal-100',    text: 'text-teal-700',    dot: 'bg-teal-500' },
  health:      { label: 'Healthcare',     bg: 'bg-teal-100',    text: 'text-teal-700',    dot: 'bg-teal-500' },
  emergency:   { label: 'Emergency',      bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500' },
  '911':       { label: 'Emergency',      bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500' },
  restaurant:  { label: 'Hospitality',    bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500' },
  kitchen:     { label: 'Hospitality',    bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500' },
  food:        { label: 'Hospitality',    bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500' },
  coffee:      { label: 'Hospitality',    bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500' },
  retail:      { label: 'Retail',         bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  commerce:    { label: 'Retail',         bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  legal:       { label: 'Legal',          bg: 'bg-slate-100',   text: 'text-slate-700',   dot: 'bg-slate-500' },
  contract:    { label: 'Legal',          bg: 'bg-slate-100',   text: 'text-slate-700',   dot: 'bg-slate-500' },
  document:    { label: 'Legal',          bg: 'bg-slate-100',   text: 'text-slate-700',   dot: 'bg-slate-500' },
  agri:        { label: 'Agriculture',    bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  yield:       { label: 'Agriculture',    bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  farm:        { label: 'Agriculture',    bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  music:       { label: 'Music',          bg: 'bg-pink-100',    text: 'text-pink-700',    dot: 'bg-pink-500' },
  sport:       { label: 'Sports',         bg: 'bg-sky-100',     text: 'text-sky-700',     dot: 'bg-sky-500' },
  broadcast:   { label: 'Sports',         bg: 'bg-sky-100',     text: 'text-sky-700',     dot: 'bg-sky-500' },
  theme:       { label: 'Entertainment',  bg: 'bg-violet-100',  text: 'text-violet-700',  dot: 'bg-violet-500' },
  park:        { label: 'Entertainment',  bg: 'bg-violet-100',  text: 'text-violet-700',  dot: 'bg-violet-500' },
  ticket:      { label: 'Support',        bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500' },
  dns:         { label: 'Infrastructure', bg: 'bg-cyan-100',    text: 'text-cyan-700',    dot: 'bg-cyan-500' },
  mobile:      { label: 'Mobile',         bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500' },
  security:    { label: 'Security',       bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500' },
  cache:       { label: 'Infrastructure', bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  retry:       { label: 'Infrastructure', bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  revenue:     { label: 'Finance',        bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  ml:          { label: 'ML Platform',    bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500' },
  recommendation: { label: 'ML Platform', bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500' },
  airline:     { label: 'Aviation',       bg: 'bg-sky-100',     text: 'text-sky-700',     dot: 'bg-sky-500' },
  degradation: { label: 'Platform',       bg: 'bg-gray-100',    text: 'text-gray-600',    dot: 'bg-gray-400' },
  telecom:     { label: 'Telecom',        bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500' },
  volte:       { label: 'Telecom',        bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500' },
  iot:         { label: 'IoT',            bg: 'bg-cyan-100',    text: 'text-cyan-700',    dot: 'bg-cyan-500' },
  fleet:       { label: 'IoT',            bg: 'bg-cyan-100',    text: 'text-cyan-700',    dot: 'bg-cyan-500' },
  kubernetes:  { label: 'Kubernetes',      bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  k8s:         { label: 'Kubernetes',      bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  canary:      { label: 'Kubernetes',      bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  devops:      { label: 'DevOps',         bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  training:    { label: 'ML Platform',    bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500' },
  supply:      { label: 'Supply Chain',   bg: 'bg-lime-100',    text: 'text-lime-700',    dot: 'bg-lime-500' },
  transcript:  { label: 'Supply Chain',   bg: 'bg-lime-100',    text: 'text-lime-700',    dot: 'bg-lime-500' },
  ops:         { label: 'Operations',     bg: 'bg-lime-100',    text: 'text-lime-700',    dot: 'bg-lime-500' },
}

const FALLBACK: DomainEntry = { label: 'General', bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400' }

function matchDomain(text: string): DomainEntry {
  const lower = text.toLowerCase()
  for (const [keyword, entry] of Object.entries(DOMAIN_COLORS)) {
    if (lower.includes(keyword)) return entry
  }
  return FALLBACK
}

/** Extract domain tags from a domain string like "Video Streaming / OTT Platform / Content Delivery" */
export function extractDomainTag(domain: string | undefined): DomainTag {
  if (!domain) return { primary: 'General', ...FALLBACK }

  const parts = domain.split(/\s*\/\s*/).map((s) => s.trim()).filter(Boolean)
  const primary = parts[0] || domain
  const secondary = parts.length > 1 ? parts[parts.length - 1] : undefined
  const { label, bg, text, dot } = matchDomain(domain)

  return { label, primary, secondary, bg, text, dot }
}

/** Get just the dot color class for a domain string */
export function getDomainDotColor(domain: string | undefined): string {
  return extractDomainTag(domain).dot
}
