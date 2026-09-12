/**
 * Shared hypothesis / worker color palette.
 *
 * Each index corresponds to a hypothesis priority (0-indexed).
 * Components pick the sub-properties they need.
 */
export const HYPOTHESIS_COLORS = [
  { border300: 'border-red-300', border400: 'border-red-400', bg50: 'bg-red-50', text: 'text-red-700', accent: 'bg-red-200' },
  { border300: 'border-orange-300', border400: 'border-orange-400', bg50: 'bg-orange-50', text: 'text-orange-700', accent: 'bg-orange-200' },
  { border300: 'border-yellow-300', border400: 'border-yellow-400', bg50: 'bg-yellow-50', text: 'text-yellow-700', accent: 'bg-yellow-200' },
  { border300: 'border-blue-300', border400: 'border-blue-400', bg50: 'bg-blue-50', text: 'text-blue-700', accent: 'bg-blue-200' },
  { border300: 'border-gray-300', border400: 'border-gray-400', bg50: 'bg-gray-50', text: 'text-gray-600', accent: 'bg-gray-200' },
] as const
