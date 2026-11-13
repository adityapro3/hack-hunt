import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, isPast, isWithinInterval, addDays } from 'date-fns'
import type { OpportunityType, ApplicationStatus } from './types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'MMM d, yyyy')
  } catch {
    return '—'
  }
}

export function formatDeadline(deadlineStr?: string | null): string {
  if (!deadlineStr) return '—'
  try {
    const date = new Date(deadlineStr)
    if (isPast(date)) return `Closed (${format(date, 'MMM d')})`
    return `${format(date, 'MMM d, yyyy')} · ${formatDistanceToNow(date, { addSuffix: true })}`
  } catch {
    return '—'
  }
}

export function isDeadlineSoon(deadlineStr?: string | null, days = 7): boolean {
  if (!deadlineStr) return false
  try {
    const date = new Date(deadlineStr)
    return isWithinInterval(date, { start: new Date(), end: addDays(new Date(), days) })
  } catch {
    return false
  }
}

export function isDeadlinePast(deadlineStr?: string | null): boolean {
  if (!deadlineStr) return false
  try {
    return isPast(new Date(deadlineStr))
  } catch {
    return false
  }
}

// ─── Color helpers ────────────────────────────────────────────────────────────

export function getTypeColor(type: OpportunityType | string): string {
  const normalized = type.toLowerCase()
  switch (normalized) {
    case 'hackathon':
      return 'bg-violet-500/15 text-violet-400 border-violet-500/30'
    default:
      return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30'
  }
}

export function getTypeAccent(type: OpportunityType | string): string {
  const normalized = type.toLowerCase()
  switch (normalized) {
    case 'hackathon':
      return 'border-l-violet-500'
    default:
      return 'border-l-zinc-500'
  }
}

export function getStatusColor(status: ApplicationStatus | string): string {
  switch (status) {
    case 'interested':
      return 'bg-blue-500/15 text-blue-400 border-blue-500/30'
    case 'applied':
      return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
    case 'in_progress':
      return 'bg-purple-500/15 text-purple-400 border-purple-500/30'
    case 'accepted':
      return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    case 'rejected':
      return 'bg-red-500/15 text-red-400 border-red-500/30'
    default:
      return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30'
  }
}

export function getOpportunityStatusColor(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized === 'active') {
    return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
  }
  if (normalized === 'upcoming') {
    return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
  }
  return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30'
}

// ─── Label helpers ────────────────────────────────────────────────────────────

export function formatApplicationStatus(status: ApplicationStatus | string): string {
  return status.replace('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function formatType(type: string): string {
  return type
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ─── Pagination ───────────────────────────────────────────────────────────────

export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

export function totalPages(total: number, pageSize: number): number {
  return Math.ceil(total / pageSize)
}
