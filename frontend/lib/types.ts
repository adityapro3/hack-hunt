// ─── Opportunities ────────────────────────────────────────────────────────────

export type OpportunityType = 'hackathon'
export type OpportunityStatus = 'active' | 'upcoming'
export type ApplicationStatus = 'interested' | 'applied' | 'in_progress' | 'accepted' | 'rejected'

export interface Opportunity {
  id: string
  opportunity_type: OpportunityType
  title: string
  url: string
  source: string
  description?: string
  domains: string[]
  skills: string[]
  mode?: string
  location?: string
  start_date?: string
  end_date?: string
  deadline?: string
  prize_money?: string
  registration_fee?: string
  team_size?: string
  eligibility: string[]
  status: OpportunityStatus
  scraped_at: string
  created_at: string
  updated_at: string
}

export interface OpportunityFilters {
  types: string[]
  domains: string[]
  skills: string[]
  modes: string[]
  statuses: string[]
  sources: string[]
}

export interface OpportunityQueryParams {
  type?: OpportunityType
  mode?: string
  domain?: string
  skill?: string
  status?: string
  source?: string
  sort?: 'deadline' | 'created_at'
  limit?: number
  offset?: number
}

// ─── News ─────────────────────────────────────────────────────────────────────

export interface NewsArticle {
  id: string
  source: string
  topic: string
  title: string
  url: string
  content: string
  language: string
  published_at?: string | null
  scraped_at: string
  created_at: string
}

export interface NewsListResponse {
  items: NewsArticle[]
  total_count: number
  limit: number
  offset: number
}

export interface NewsFiltersResponse {
  topics: string[]
}

export interface NewsQueryParams {
  topic?: string
  q?: string
  semantic?: boolean
  limit?: number
  offset?: number
}

export interface NewsScrapeRunPayload {
  sources?: string[]
  max_pages_per_source?: number
  keep_days?: number
}

export interface NewsScrapeRunResponse {
  total_scraped: number
  total_saved: number
  by_source: Record<string, number>
  sources: string[]
  max_pages_per_source: number
  keep_days: number
  logs: string[]
}

export interface NewsChatPayload {
  message: string
}

export interface NewsChatContextItem {
  id: string
  title: string
  source: string
  topic: string
  url: string
  published_at?: string | null
}

export interface NewsChatResponse {
  answer: string
  provider: string
  model: string
  retrieved_count: number
  context: NewsChatContextItem[]
}

export interface NewsChatStreamMetaEvent {
  type: 'meta'
  provider: string
  model: string
  retrieved_count: number
  context: NewsChatContextItem[]
}

export interface NewsChatStreamDeltaEvent {
  type: 'content' | 'delta'
  delta: string
}

export interface NewsChatStreamDoneEvent {
  type: 'done'
}

export interface NewsChatStreamErrorEvent {
  type: 'error'
  detail: string
}

export type NewsChatStreamEvent =
  | NewsChatStreamMetaEvent
  | NewsChatStreamDeltaEvent
  | NewsChatStreamDoneEvent
  | NewsChatStreamErrorEvent

// ─── Bookmarks ────────────────────────────────────────────────────────────────

export interface Bookmark {
  id: string
  opportunity_id: string
  notes?: string
  created_at: string
  opportunity: Opportunity
}

export interface CreateBookmarkPayload {
  opportunity_id: string
  notes?: string
}

// ─── Applications (Tracker) ───────────────────────────────────────────────────

export interface Application {
  id: string
  opportunity_id: string
  status: ApplicationStatus
  applied_at?: string
  notes?: string
  created_at: string
  updated_at: string
  opportunity: Opportunity
}

export interface CreateApplicationPayload {
  opportunity_id: string
  status?: ApplicationStatus
  applied_at?: string
  notes?: string
}

export interface UpdateApplicationPayload {
  status?: ApplicationStatus
  applied_at?: string
  notes?: string
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id?: string
  thread_id?: string
  role: 'user' | 'assistant'
  content: string
  context?: ChatContextOpportunity[]
  provider?: string
  model?: string
  created_at?: string
}

export type ChatProvider = 'gemini' | 'openai' | 'anthropic' | 'ollama' | 'ollama_cloud'
export type SavedModelsMap = Record<ChatProvider, string[]>

export interface ChatContextOpportunity {
  id: string
  title: string
  opportunity_type: OpportunityType
  source: string
  url: string
  status: OpportunityStatus
  deadline?: string
}

export interface ChatRequest {
  message: string
  resume_text?: string
  provider?: ChatProvider
  model?: string
  use_free_tier?: boolean
  thread_id?: string
}

export interface ChatResponse {
  answer: string
  provider: string
  model: string
  thread_id: string
  retrieved_count: number
  opportunities: ChatContextOpportunity[]
}

export interface ChatStreamMetaEvent {
  type: 'meta'
  thread_id: string
  provider: string
  model: string
  retrieved_count: number
  opportunities: ChatContextOpportunity[]
}

export interface ChatStreamDeltaEvent {
  type: 'delta'
  content: string
}

export interface ChatStreamDoneEvent {
  type: 'done'
  thread_id: string
  provider: string
  model: string
  answer: string
  retrieved_count: number
  opportunities: ChatContextOpportunity[]
}

export interface ChatStreamErrorEvent {
  type: 'error'
  detail: string
}

export type ChatStreamEvent =
  | ChatStreamMetaEvent
  | ChatStreamDeltaEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent

export interface ChatThreadSummary {
  id: string
  title: string
  message_count: number
  last_message_preview?: string
  created_at: string
  updated_at: string
}

export interface CreateChatThreadPayload {
  title?: string
}

// ─── Cold Email ───────────────────────────────────────────────────────────────

export type ColdEmailAskType =
  | 'phd_inquiry'
  | 'research_assistant'
  | 'collaboration'
  | 'meeting_request'
  | 'internship_inquiry'

export interface ColdEmailStudentProject {
  title: string
  what: string
  impact?: string | null
}

export interface ColdEmailStudentProfile {
  full_name?: string | null
  research_interests: string[]
  technical_skills: string[]
  projects: ColdEmailStudentProject[]
  publications: string[]
  goal?: string | null
  degree?: string | null
}

export interface ColdEmailProfileUpsertPayload {
  filename: string
  content_base64: string
  allow_reupload?: boolean
}

export interface ColdEmailProfileResponse {
  user_id: string
  resume_filename?: string | null
  profile: ColdEmailStudentProfile
  profile_provider: string
  profile_model: string
  generated_at: string
  updated_at: string
}

export interface ColdEmailGeneratePayload {
  countries: string[]
  website?: string
  tone?: string
  ask_type?: ColdEmailAskType
  max_professors?: number
  provider?: ChatProvider
  model?: string
  use_free_tier?: boolean
}

export interface ColdEmailResumeParsePayload {
  filename: string
  content_base64: string
}

export interface ColdEmailResumeParseResult {
  filename: string
  resume_text: string
}

export interface ColdEmailSkillExtractPayload {
  resume_text: string
  provider?: ChatProvider
  model?: string
}

export interface ColdEmailSkillExtractResult {
  skills_text: string
  provider: string
  model: string
}

export interface ColdEmailApprovePayload {
  recipient_email: string
}

export interface ColdEmailSendPayload {
  recipient_email?: string
}

export interface ColdEmailDraft {
  id: string
  country: string
  source: string
  professor_name: string
  university_name?: string
  profile_url?: string
  research_summary?: string
  research_matches: ColdEmailResearchMatch[]
  subject_line: string
  body: string
  recipient_email?: string
  tone: string
  ask_type: ColdEmailAskType
  provider: string
  model: string
  status: string
  approved_at?: string
  sent_at?: string
  last_error?: string
  created_at: string
}

export interface ColdEmailResearchMatch {
  title: string
  similarity_score: number
  year?: number | null
  url?: string | null
  abstract?: string | null
}

export interface ColdEmailListResponse {
  drafts: ColdEmailDraft[]
  total_count: number
  limit: number
  offset: number
}

export interface ColdEmailStreamMetaEvent {
  type: 'meta'
  provider: string
  model: string
  countries: string[]
  max_professors: number
  ask_type: ColdEmailAskType
  use_free_tier?: boolean
  free_tier_remaining?: number | null
}

export interface ColdEmailStreamProgressEvent {
  type: 'progress'
  stage: string
  message: string
  country?: string
  professor_name?: string
}

export interface ColdEmailStreamDraftEvent {
  type: 'draft'
  draft: ColdEmailDraft
}

export interface ColdEmailStreamDoneEvent {
  type: 'done'
  generated_count: number
  failed_count: number
}

export interface ColdEmailStreamErrorEvent {
  type: 'error'
  detail: string
}

export type ColdEmailStreamEvent =
  | ColdEmailStreamMetaEvent
  | ColdEmailStreamProgressEvent
  | ColdEmailStreamDraftEvent
  | ColdEmailStreamDoneEvent
  | ColdEmailStreamErrorEvent

// ─── Settings ─────────────────────────────────────────────────────────────────

export interface UserSettings {
  id: number
  has_gemini_key: boolean
  has_openai_key: boolean
  has_anthropic_key: boolean
  has_ollama_cloud_key: boolean
  ollama_model: string
  ollama_base_url: string
  saved_models: SavedModelsMap
  created_at: string
  updated_at: string
}

export interface UpdateSettingsPayload {
  gemini_api_key?: string
  openai_api_key?: string
  anthropic_api_key?: string
  ollama_model?: string
  ollama_base_url?: string
  ollama_cloud_api_key?: string
}

export interface SavedModelPayload {
  provider: ChatProvider
  model: string
}

// ─── Scraper ──────────────────────────────────────────────────────────────────

export interface ScraperRunResponse {
  total_scraped: number
  total_saved: number
  by_source: Record<string, number>
  logs: string[]
}

export interface ScraperSourcesResponse {
  scrapers: string[]
}

export interface EmbeddingTargetBackfillPayload {
  batch_size?: number
  source?: string
  run_until_empty?: boolean
}

export interface EmbeddingBackfillResult {
  processed: number
  failed: number
  remaining: number
  batches_ran: number
  source?: string | null
  logs: string[]
}

export interface NewsTopicBackfillPayload {
  batch_size?: number
  source?: string
  run_until_empty?: boolean
  overwrite_existing?: boolean
}

export interface NewsTopicBackfillResult {
  processed: number
  failed: number
  remaining: number
  batches_ran: number
  source?: string | null
  logs: string[]
}

export interface ExpiredCleanupResult {
  matched: number
  deleted: number
  opportunity_matched?: number
  opportunity_deleted?: number
  news_matched?: number
  news_deleted?: number
  news_keep_days?: number
  now_utc: string
}

export interface ExpiredCleanupPayload {
  news_keep_days?: number
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string
  email: string
  full_name?: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface SignInPayload {
  email: string
  password: string
}

export interface SignUpPayload {
  email: string
  password: string
  full_name?: string
  admin_signup_key?: string
}
