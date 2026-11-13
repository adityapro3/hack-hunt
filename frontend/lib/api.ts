import axios from 'axios'
import type {
  Application,
  AuthResponse,
  Bookmark,
  ChatProvider,
  ChatRequest,
  ChatResponse,
  ChatStreamDoneEvent,
  ChatStreamErrorEvent,
  ChatStreamEvent,
  ChatStreamMetaEvent,
  ChatMessage,
  ChatThreadSummary,
  ColdEmailDraft,
  ColdEmailGeneratePayload,
  ColdEmailListResponse,
  ColdEmailProfileResponse,
  ColdEmailProfileUpsertPayload,
  ColdEmailResumeParsePayload,
  ColdEmailResumeParseResult,
  ColdEmailSendPayload,
  ColdEmailSkillExtractPayload,
  ColdEmailSkillExtractResult,
  ColdEmailApprovePayload,
  ColdEmailStreamDoneEvent,
  ColdEmailStreamErrorEvent,
  ColdEmailStreamEvent,
  ColdEmailStreamMetaEvent,
  ColdEmailStreamProgressEvent,
  CreateChatThreadPayload,
  CreateApplicationPayload,
  CreateBookmarkPayload,
  NewsFiltersResponse,
  NewsChatPayload,
  NewsChatResponse,
  NewsChatStreamEvent,
  NewsChatStreamMetaEvent,
  NewsListResponse,
  NewsQueryParams,
  NewsScrapeRunPayload,
  NewsScrapeRunResponse,
  NewsTopicBackfillPayload,
  NewsTopicBackfillResult,
  Opportunity,
  OpportunityStatus,
  OpportunityType,
  SavedModelPayload,
  OpportunityFilters,
  OpportunityQueryParams,
  EmbeddingBackfillResult,
  EmbeddingTargetBackfillPayload,
  ExpiredCleanupPayload,
  ExpiredCleanupResult,
  ScraperSourcesResponse,
  ScraperRunResponse,
  SignInPayload,
  SignUpPayload,
  UpdateApplicationPayload,
  UpdateSettingsPayload,
  UserSettings,
} from './types'
import { clearAuthSessionStorage, getAuthSession } from './auth'

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
  (process.env.NODE_ENV === 'production'
    ? (typeof window !== 'undefined' ? window.location.origin : '')
    : 'http://localhost:8000')
const LONG_RUNNING_TIMEOUT_MS = 15 * 60 * 1000
const XLONG_RUNNING_TIMEOUT_MS = 30 * 60 * 1000

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

function normalizeType(raw: string): OpportunityType {
  void raw
  return 'hackathon'
}

function normalizeStatus(raw: string): OpportunityStatus {
  const v = raw.toLowerCase()
  if (v === 'upcoming') return 'upcoming'
  return 'active'
}

function sanitizeDescription(raw: unknown): string | undefined {
  if (typeof raw !== 'string') {
    return undefined
  }
  const cleaned = raw
    .replace(/[#*_`]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || undefined
}

function normalizeOpportunity(item: any): Opportunity {
  return {
    ...item,
    opportunity_type: normalizeType(String(item.opportunity_type || 'hackathon')),
    status: normalizeStatus(String(item.status || 'active')),
    description: sanitizeDescription(item.description),
  }
}

function normalizeNewsArticle(item: any) {
  return {
    ...item,
    source: String(item.source || '').trim().toLowerCase(),
    topic: String(item.topic || '').trim().toLowerCase(),
    title: String(item.title || '').trim(),
    content: String(item.content || '').replace(/\s+/g, ' ').trim(),
  }
}

client.interceptors.request.use((config) => {
  const session = getAuthSession()
  if (session?.access_token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearAuthSessionStorage()
    }
    return Promise.reject(error)
  }
)

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function signIn(payload: SignInPayload): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/api/auth/signin', payload)
  return data
}

export async function signUp(payload: SignUpPayload): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/api/auth/signup', payload)
  return data
}

export async function getMe() {
  const { data } = await client.get('/api/auth/me')
  return data
}

// ─── Opportunities ────────────────────────────────────────────────────────────

export async function getOpportunities(params: OpportunityQueryParams = {}): Promise<Opportunity[]> {
  const { data } = await client.get<Opportunity[]>('/api/opportunities', { params })
  return data.map(normalizeOpportunity)
}

export async function getOpportunityFilters(type?: string): Promise<OpportunityFilters> {
  const { data } = await client.get<OpportunityFilters>('/api/opportunities/filters', {
    params: type ? { type } : {},
  })
  return {
    ...data,
    types: data.types.map((x) => normalizeType(String(x))),
    statuses: data.statuses.map((x) => normalizeStatus(String(x))),
  }
}

export async function getOpportunity(id: string): Promise<Opportunity> {
  const { data } = await client.get<Opportunity>(`/api/opportunities/${id}`)
  return normalizeOpportunity(data)
}

// ─── News ─────────────────────────────────────────────────────────────────────

export async function getNewsArticles(params: NewsQueryParams = {}): Promise<NewsListResponse> {
  const { data } = await client.get<NewsListResponse>('/api/news', { params })
  return {
    ...data,
    items: (data.items || []).map((item: any) => normalizeNewsArticle(item)),
  }
}

export async function getNewsFilters(): Promise<NewsFiltersResponse> {
  const { data } = await client.get<NewsFiltersResponse>('/api/news/filters')
  return {
    topics: (data.topics || []).map((item) => String(item).trim().toLowerCase()),
  }
}

export async function runNewsScrapers(payload: NewsScrapeRunPayload = {}): Promise<NewsScrapeRunResponse> {
  const body: NewsScrapeRunPayload = {
    sources: payload.sources || [],
    max_pages_per_source: payload.max_pages_per_source ?? 12,
    keep_days: payload.keep_days ?? 3,
  }
  const { data } = await client.post<NewsScrapeRunResponse>('/api/scraper/news/run', body, {
    timeout: LONG_RUNNING_TIMEOUT_MS,
  })
  return data
}

export async function streamRunNewsScrapers(
  payload: NewsScrapeRunPayload = {},
  callbacks: AdminStreamCallbacks<NewsScrapeRunResponse> = {}
): Promise<NewsScrapeRunResponse> {
  const body: NewsScrapeRunPayload = {
    sources: payload.sources || [],
    max_pages_per_source: payload.max_pages_per_source ?? 12,
    keep_days: payload.keep_days ?? 3,
  }
  return streamAdminJob<NewsScrapeRunResponse>('/api/scraper/news/run/stream', body, callbacks)
}

export async function sendNewsChatMessage(payload: NewsChatPayload): Promise<NewsChatResponse> {
  const { data } = await client.post<NewsChatResponse>('/api/news/chat', payload, {
    timeout: LONG_RUNNING_TIMEOUT_MS,
  })
  return data
}

interface NewsChatStreamCallbacks {
  onMeta?: (event: NewsChatStreamMetaEvent) => void
  onDelta?: (delta: string) => void
  onDone?: () => void
}

function parseNewsStreamLine(line: string): NewsChatStreamEvent | null {
  try {
    return JSON.parse(line) as NewsChatStreamEvent
  } catch {
    return null
  }
}

export async function streamNewsChatMessage(
  payload: NewsChatPayload,
  callbacks: NewsChatStreamCallbacks = {}
): Promise<void> {
  const session = getAuthSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const response = await fetch(`${BASE_URL}/api/news/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = `News chat storage failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body?.detail === 'string' && body.detail.trim()) {
        detail = body.detail.trim()
      }
    } catch {
      // Keep default detail.
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response body is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    let lastNewlineIndex = buffer.lastIndexOf('\n')
    if (lastNewlineIndex === -1) continue

    const lines = buffer.slice(0, lastNewlineIndex).split('\n')
    buffer = buffer.slice(lastNewlineIndex + 1)

    for (let line of lines) {
      line = line.trim()
      if (!line || !line.startsWith('data: ')) continue
      const jsonStr = line.replace(/^data:\s*/, '')
      const event = parseNewsStreamLine(jsonStr)

      if (event?.type === 'meta') {
        callbacks.onMeta?.(event)
      } else if (event?.type === 'content') {
        callbacks.onDelta?.(event.delta)
      } else if (event?.type === 'delta') {
        callbacks.onDelta?.(event.delta)
      } else if (event?.type === 'done') {
        callbacks.onDone?.()
      } else if (event?.type === 'error') {
        throw new Error(event.detail || 'News chat stream failed')
      }
    }
  }
}

interface AdminStreamLogEvent {
  type: 'log'
  line: string
}

interface AdminStreamDoneEvent<T> {
  type: 'done'
  result: T
}

interface AdminStreamErrorEvent {
  type: 'error'
  detail: string
}

type AdminStreamEvent<T> = AdminStreamLogEvent | AdminStreamDoneEvent<T> | AdminStreamErrorEvent

interface AdminStreamCallbacks<T> {
  onLog?: (line: string) => void
  onDone?: (result: T) => void
}

function parseAdminStreamLine<T>(line: string): AdminStreamEvent<T> | null {
  try {
    return JSON.parse(line) as AdminStreamEvent<T>
  } catch {
    return null
  }
}

async function streamAdminJob<T>(
  path: string,
  payload: unknown,
  callbacks: AdminStreamCallbacks<T> = {}
): Promise<T> {
  const session = getAuthSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = `Admin stream failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body?.detail === 'string' && body.detail.trim()) {
        detail = body.detail.trim()
      }
    } catch {
      // Keep default error detail.
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response body is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: T | undefined

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    let newlineIndex = buffer.indexOf('\n')

    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)

      if (line.startsWith('data:')) {
        const event = parseAdminStreamLine<T>(line.replace(/^data:\s*/, ''))
        if (event?.type === 'log') {
          callbacks.onLog?.(event.line)
        } else if (event?.type === 'done') {
          finalResult = event.result
          callbacks.onDone?.(event.result)
        } else if (event?.type === 'error') {
          throw new Error(event.detail || 'Admin stream failed')
        }
      }

      newlineIndex = buffer.indexOf('\n')
    }
  }

  const remaining = buffer.trim()
  if (remaining.startsWith('data:')) {
    const event = parseAdminStreamLine<T>(remaining.replace(/^data:\s*/, ''))
    if (event?.type === 'log') {
      callbacks.onLog?.(event.line)
    } else if (event?.type === 'done') {
      finalResult = event.result
      callbacks.onDone?.(event.result)
    } else if (event?.type === 'error') {
      throw new Error(event.detail || 'Admin stream failed')
    }
  }

  if (finalResult === undefined) {
    throw new Error('Admin stream ended without a completion payload')
  }

  return finalResult
}

// ─── Bookmarks ────────────────────────────────────────────────────────────────

export async function getBookmarks(type?: string): Promise<Bookmark[]> {
  const { data } = await client.get<Bookmark[]>('/api/bookmarks', {
    params: type ? { type } : {},
  })
  return data.map((b: any) => ({ ...b, opportunity: normalizeOpportunity(b.opportunity) }))
}

export async function createBookmark(payload: CreateBookmarkPayload): Promise<Bookmark> {
  const { data } = await client.post<Bookmark>('/api/bookmarks', payload)
  return { ...(data as any), opportunity: normalizeOpportunity((data as any).opportunity) }
}

export async function deleteBookmark(bookmarkId: string): Promise<void> {
  await client.delete(`/api/bookmarks/${bookmarkId}`)
}

// ─── Applications ─────────────────────────────────────────────────────────────

export async function getApplications(params?: {
  type?: string
  status?: string
}): Promise<Application[]> {
  const { data } = await client.get<Application[]>('/api/applications', { params })
  return data.map((a: any) => ({ ...a, opportunity: normalizeOpportunity(a.opportunity) }))
}

export async function createApplication(payload: CreateApplicationPayload): Promise<Application> {
  const { data } = await client.post<Application>('/api/applications', payload)
  return { ...(data as any), opportunity: normalizeOpportunity((data as any).opportunity) }
}

export async function updateApplication(
  applicationId: string,
  payload: UpdateApplicationPayload
): Promise<Application> {
  const { data } = await client.put<Application>(`/api/applications/${applicationId}`, payload)
  return { ...(data as any), opportunity: normalizeOpportunity((data as any).opportunity) }
}

export async function deleteApplication(applicationId: string): Promise<void> {
  await client.delete(`/api/applications/${applicationId}`)
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  const { data } = await client.post<ChatResponse>('/api/opportunities/chat', payload)
  return {
    ...data,
    opportunities: data.opportunities.map((o: any) => ({
      ...o,
      opportunity_type: normalizeType(String(o.opportunity_type || 'hackathon')),
      status: normalizeStatus(String(o.status || 'active')),
    })),
  }
}

interface StreamChatCallbacks {
  onMeta?: (event: ChatStreamMetaEvent) => void
  onDelta?: (event: { content: string }) => void
  onDone?: (event: ChatStreamDoneEvent) => void
}

function parseStreamLine(line: string): ChatStreamEvent | null {
  try {
    return JSON.parse(line) as ChatStreamEvent
  } catch {
    return null
  }
}

function normalizeStreamOpportunities(items: any[]): any[] {
  return (items || []).map((o: any) => ({
    ...o,
    opportunity_type: normalizeType(String(o.opportunity_type || 'hackathon')),
    status: normalizeStatus(String(o.status || 'active')),
  }))
}

export async function streamChatMessage(payload: ChatRequest, callbacks: StreamChatCallbacks = {}): Promise<void> {
  const session = getAuthSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const response = await fetch(`${BASE_URL}/api/opportunities/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = `Chat request failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body?.detail === 'string' && body.detail.trim()) {
        detail = body.detail.trim()
      }
    } catch {
      // Keep default error detail.
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response body is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    let newlineIndex = buffer.indexOf('\n')
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)

      if (line) {
        const event = parseStreamLine(line)
        if (event?.type === 'meta') {
          callbacks.onMeta?.({
            ...event,
            opportunities: normalizeStreamOpportunities(event.opportunities as any),
          })
        } else if (event?.type === 'delta') {
          callbacks.onDelta?.({ content: event.content })
        } else if (event?.type === 'done') {
          callbacks.onDone?.({
            ...event,
            opportunities: normalizeStreamOpportunities(event.opportunities as any),
          })
        } else if (event?.type === 'error') {
          const errEvent = event as ChatStreamErrorEvent
          throw new Error(errEvent.detail || 'Chat stream failed')
        }
      }

      newlineIndex = buffer.indexOf('\n')
    }
  }

  const remaining = buffer.trim()
  if (remaining) {
    const event = parseStreamLine(remaining)
    if (event?.type === 'error') {
      throw new Error((event as ChatStreamErrorEvent).detail || 'Chat stream failed')
    }
    if (event?.type === 'done') {
      callbacks.onDone?.({
        ...event,
        opportunities: normalizeStreamOpportunities(event.opportunities as any),
      })
    }
  }
}

export async function getChatThreads(): Promise<ChatThreadSummary[]> {
  const { data } = await client.get<ChatThreadSummary[]>('/api/opportunities/chat/threads')
  return data
}

export async function createChatThread(payload: CreateChatThreadPayload = {}): Promise<ChatThreadSummary> {
  const { data } = await client.post<ChatThreadSummary>('/api/opportunities/chat/threads', payload)
  return data
}

export async function deleteChatThread(threadId: string): Promise<void> {
  await client.delete(`/api/opportunities/chat/threads/${threadId}`)
}

export async function getChatMessages(threadId: string): Promise<ChatMessage[]> {
  const { data } = await client.get<ChatMessage[]>(`/api/opportunities/chat/threads/${threadId}/messages`)
  return data.map((m: any) => ({
    ...m,
    context: (m.context || []).map((o: any) => ({
      ...o,
      opportunity_type: normalizeType(String(o.opportunity_type || 'hackathon')),
      status: normalizeStatus(String(o.status || 'active')),
    })),
  }))
}

// ─── Cold Email ───────────────────────────────────────────────────────────────

interface ColdEmailStreamCallbacks {
  onMeta?: (event: ColdEmailStreamMetaEvent) => void
  onProgress?: (event: ColdEmailStreamProgressEvent) => void
  onDraft?: (draft: ColdEmailDraft) => void
  onDone?: (event: ColdEmailStreamDoneEvent) => void
}

function parseColdEmailStreamLine(line: string): ColdEmailStreamEvent | null {
  try {
    return JSON.parse(line) as ColdEmailStreamEvent
  } catch {
    return null
  }
}

export async function getColdEmailDrafts(limit = 50, offset = 0): Promise<ColdEmailListResponse> {
  const { data } = await client.get<ColdEmailListResponse>('/api/coldemail/drafts', {
    params: { limit, offset },
  })
  return data
}

export async function parseColdEmailResume(
  payload: ColdEmailResumeParsePayload
): Promise<ColdEmailResumeParseResult> {
  const { data } = await client.post<ColdEmailResumeParseResult>('/api/coldemail/resume/parse', payload)
  return data
}

export async function getColdEmailProfile(): Promise<ColdEmailProfileResponse> {
  const { data } = await client.get<ColdEmailProfileResponse>('/api/coldemail/profile')
  return data
}

export async function upsertColdEmailProfile(
  payload: ColdEmailProfileUpsertPayload
): Promise<ColdEmailProfileResponse> {
  const { data } = await client.post<ColdEmailProfileResponse>('/api/coldemail/profile', payload, {
    timeout: 300_000,
  })
  return data
}

export async function extractColdEmailSkills(
  payload: ColdEmailSkillExtractPayload
): Promise<ColdEmailSkillExtractResult> {
  const { data } = await client.post<ColdEmailSkillExtractResult>('/api/coldemail/skills/extract', payload)
  return data
}

export async function approveColdEmailDraft(
  draftId: string,
  payload: ColdEmailApprovePayload
): Promise<ColdEmailDraft> {
  const { data } = await client.patch<ColdEmailDraft>(`/api/coldemail/drafts/${draftId}/approve`, payload)
  return data
}

export async function sendColdEmailDraft(
  draftId: string,
  payload: ColdEmailSendPayload = {}
): Promise<ColdEmailDraft> {
  const { data } = await client.post<ColdEmailDraft>(`/api/coldemail/drafts/${draftId}/send`, payload)
  return data
}

export async function deleteColdEmailDraft(draftId: string): Promise<void> {
  await client.delete(`/api/coldemail/drafts/${draftId}`)
}

export async function streamGenerateColdEmails(
  payload: ColdEmailGeneratePayload,
  callbacks: ColdEmailStreamCallbacks = {}
): Promise<void> {
  const session = getAuthSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const response = await fetch(`${BASE_URL}/api/coldemail/generate/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = `Cold-email request failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body?.detail === 'string' && body.detail.trim()) {
        detail = body.detail.trim()
      }
    } catch {
      // Keep default detail.
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response body is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    let newlineIndex = buffer.indexOf('\n')

    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)

      if (line) {
        const event = parseColdEmailStreamLine(line)
        if (event?.type === 'meta') {
          callbacks.onMeta?.(event)
        } else if (event?.type === 'progress') {
          callbacks.onProgress?.(event)
        } else if (event?.type === 'draft') {
          callbacks.onDraft?.(event.draft)
        } else if (event?.type === 'done') {
          callbacks.onDone?.(event)
        } else if (event?.type === 'error') {
          throw new Error((event as ColdEmailStreamErrorEvent).detail || 'Cold-email stream failed')
        }
      }

      newlineIndex = buffer.indexOf('\n')
    }
  }

  const remaining = buffer.trim()
  if (remaining) {
    const event = parseColdEmailStreamLine(remaining)
    if (event?.type === 'done') {
      callbacks.onDone?.(event)
    }
    if (event?.type === 'error') {
      throw new Error((event as ColdEmailStreamErrorEvent).detail || 'Cold-email stream failed')
    }
  }
}

// ─── Settings ─────────────────────────────────────────────────────────────────

export async function getSettings(): Promise<UserSettings> {
  const { data } = await client.get<UserSettings>('/api/settings')
  return data
}

export async function updateSettings(payload: UpdateSettingsPayload): Promise<UserSettings> {
  const { data } = await client.put<UserSettings>('/api/settings', payload)
  return data
}

export async function addSavedModel(payload: SavedModelPayload): Promise<UserSettings> {
  const { data } = await client.post<UserSettings>('/api/settings/models', payload)
  return data
}

export async function removeSavedModel(provider: ChatProvider, model: string): Promise<UserSettings> {
  const { data } = await client.delete<UserSettings>('/api/settings/models', {
    params: { provider, model },
  })
  return data
}

// ─── Scraper ──────────────────────────────────────────────────────────────────

export async function runScraper(sources: string[] = []): Promise<ScraperRunResponse> {
  const { data } = await client.post<ScraperRunResponse>(
    '/api/scraper/opportunities/run',
    { sources },
    { timeout: XLONG_RUNNING_TIMEOUT_MS }
  )
  return data
}

export async function streamRunScraper(
  sources: string[] = [],
  callbacks: AdminStreamCallbacks<ScraperRunResponse> = {}
): Promise<ScraperRunResponse> {
  return streamAdminJob<ScraperRunResponse>('/api/scraper/opportunities/run/stream', { sources }, callbacks)
}

export async function getAvailableScrapers(): Promise<ScraperSourcesResponse> {
  const { data } = await client.get<ScraperSourcesResponse>('/api/scraper/available')
  return data
}

export async function backfillOpportunityEmbeddings(
  payload: EmbeddingTargetBackfillPayload = {}
): Promise<EmbeddingBackfillResult> {
  const body: EmbeddingTargetBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
  }
  const { data } = await client.post<EmbeddingBackfillResult>(
    '/api/scraper/embeddings/backfill/opportunities',
    body,
    { timeout: LONG_RUNNING_TIMEOUT_MS }
  )
  return data
}

export async function streamBackfillOpportunityEmbeddings(
  payload: EmbeddingTargetBackfillPayload = {},
  callbacks: AdminStreamCallbacks<EmbeddingBackfillResult> = {}
): Promise<EmbeddingBackfillResult> {
  const body: EmbeddingTargetBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
  }
  return streamAdminJob<EmbeddingBackfillResult>(
    '/api/scraper/embeddings/backfill/opportunities/stream',
    body,
    callbacks
  )
}

export async function backfillNewsEmbeddings(
  payload: EmbeddingTargetBackfillPayload = {}
): Promise<EmbeddingBackfillResult> {
  const body: EmbeddingTargetBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
  }
  const { data } = await client.post<EmbeddingBackfillResult>(
    '/api/scraper/embeddings/backfill/news',
    body,
    { timeout: XLONG_RUNNING_TIMEOUT_MS }
  )
  return data
}

export async function streamBackfillNewsEmbeddings(
  payload: EmbeddingTargetBackfillPayload = {},
  callbacks: AdminStreamCallbacks<EmbeddingBackfillResult> = {}
): Promise<EmbeddingBackfillResult> {
  const body: EmbeddingTargetBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
  }
  return streamAdminJob<EmbeddingBackfillResult>('/api/scraper/embeddings/backfill/news/stream', body, callbacks)
}

export async function backfillNewsTopics(
  payload: NewsTopicBackfillPayload = {}
): Promise<NewsTopicBackfillResult> {
  const body: NewsTopicBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
    overwrite_existing: payload.overwrite_existing ?? false,
  }
  const { data } = await client.post<NewsTopicBackfillResult>(
    '/api/scraper/topics/backfill/news',
    body,
    { timeout: LONG_RUNNING_TIMEOUT_MS }
  )
  return data
}

export async function streamBackfillNewsTopics(
  payload: NewsTopicBackfillPayload = {},
  callbacks: AdminStreamCallbacks<NewsTopicBackfillResult> = {}
): Promise<NewsTopicBackfillResult> {
  const body: NewsTopicBackfillPayload = {
    batch_size: payload.batch_size ?? 16,
    source: payload.source,
    run_until_empty: payload.run_until_empty ?? false,
    overwrite_existing: payload.overwrite_existing ?? false,
  }
  return streamAdminJob<NewsTopicBackfillResult>('/api/scraper/topics/backfill/news/stream', body, callbacks)
}

export async function cleanupExpiredOpportunities(
  payload: ExpiredCleanupPayload = {}
): Promise<ExpiredCleanupResult> {
  const body: ExpiredCleanupPayload = {
    news_keep_days: payload.news_keep_days ?? 3,
  }
  const { data } = await client.post<ExpiredCleanupResult>('/api/scraper/cleanup/expired', body)
  return data
}

// ─── Health ───────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    await client.get('/health')
    return true
  } catch {
    return false
  }
}
