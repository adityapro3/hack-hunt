import type { Opportunity } from './types'
import { formatType } from './utils'

type DomainGroupRule = {
  label: string
  keywords: string[]
}

const DOMAIN_GROUP_RULES: DomainGroupRule[] = [
  {
    label: 'AI & Machine Learning',
    keywords: [
      'ai',
      'artificial intelligence',
      'machine learning',
      'ml',
      'deep learning',
      'neural',
      'llm',
      'nlp',
      'computer vision',
      'genai',
      'generative ai',
    ],
  },
  {
    label: 'Data & Analytics',
    keywords: ['data science', 'analytics', 'statistics', 'big data', 'data engineering', 'data'],
  },
  {
    label: 'Cloud & DevOps',
    keywords: ['cloud', 'aws', 'azure', 'gcp', 'devops', 'kubernetes', 'docker', 'infrastructure'],
  },
  {
    label: 'Web & App Development',
    keywords: ['web', 'frontend', 'backend', 'full stack', 'fullstack', 'mobile', 'app development'],
  },
  {
    label: 'Security',
    keywords: ['security', 'cybersecurity', 'infosec', 'privacy', 'cryptography'],
  },
  {
    label: 'FinTech & Business',
    keywords: ['fintech', 'finance', 'trading', 'business', 'product', 'marketing', 'startup'],
  },
  {
    label: 'Research & Benchmarking',
    keywords: ['research', 'benchmark', 'evaluation', 'custom metric', 'tabular', 'text'],
  },
  {
    label: 'Core Engineering',
    keywords: ['algorithms', 'reasoning', 'systems', 'open source', 'software engineering', 'engineering'],
  },
]

function normalizeDomain(input: string): string {
  return input
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function hasWholeTerm(haystack: string, term: string): boolean {
  const padded = ` ${haystack} `
  return padded.includes(` ${term} `)
}

function matchesRule(normalizedDomain: string, rule: DomainGroupRule): boolean {
  return rule.keywords.some((keyword) => {
    const normalizedKeyword = normalizeDomain(keyword)
    if (!normalizedKeyword) return false
    if (normalizedKeyword.includes(' ')) {
      return normalizedDomain.includes(normalizedKeyword)
    }
    return hasWholeTerm(normalizedDomain, normalizedKeyword)
  })
}

function uniqueOrdered(items: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const item of items) {
    if (!item || seen.has(item)) continue
    seen.add(item)
    out.push(item)
  }
  return out
}

export function getGroupedDomainLabel(domain: string): string {
  const normalized = normalizeDomain(domain)
  if (!normalized) return 'General'

  const matched = DOMAIN_GROUP_RULES.find((rule) => matchesRule(normalized, rule))
  if (matched) return matched.label

  return formatType(domain)
}

export function groupDomainValues(domains: string[]): string[] {
  return uniqueOrdered(domains.map((domain) => getGroupedDomainLabel(domain)))
}

export function opportunityMatchesDomainGroup(opportunity: Opportunity, selectedDomain?: string): boolean {
  if (!selectedDomain) return true
  const groupedDomains = groupDomainValues(opportunity.domains || [])
  return groupedDomains.includes(selectedDomain)
}
