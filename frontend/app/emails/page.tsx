'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Sparkles, Copy, Loader2, Info, Upload, CheckCircle2, XCircle, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  approveColdEmailDraft,
  deleteColdEmailDraft,
  getColdEmailProfile,
  getColdEmailDrafts,
  getSettings,
  sendColdEmailDraft,
  streamGenerateColdEmails,
  upsertColdEmailProfile,
} from '@/lib/api'
import { useEmailStore } from '@/store/emailStore'
import type { ChatProvider, ColdEmailAskType } from '@/lib/types'
import { formatDate } from '@/lib/utils'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

const PROVIDER_LABELS: Record<ChatProvider, string> = {
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  ollama: 'Ollama (Local)',
  ollama_cloud: 'Ollama (Cloud)',
}

const ASK_TYPE_LABELS: Record<ColdEmailAskType, string> = {
  phd_inquiry: 'PhD Inquiry',
  research_assistant: 'Research Assistant',
  collaboration: 'Collaboration',
  meeting_request: 'Meeting Request',
  internship_inquiry: 'Internship Inquiry',
}

export default function ColdEmailPage() {
  const qc = useQueryClient()
  const { drafts, isGenerating, progressMessage, setDrafts, setGenerating, setProgressMessage, prependDraft } = useEmailStore()
  const [runLogs, setRunLogs] = useState<string[]>([])
  const [countriesInput, setCountriesInput] = useState('USA')
  const [tone, setTone] = useState('professional')
  const [askType, setAskType] = useState<ColdEmailAskType>('collaboration')
  const [maxProfessors, setMaxProfessors] = useState(5)
  const [profileFileName, setProfileFileName] = useState('')
  const [allowProfileReupload, setAllowProfileReupload] = useState(false)
  const [usagePlan, setUsagePlan] = useState<'standard' | 'free'>('standard')
  const [selectedProvider, setSelectedProvider] = useState<ChatProvider>('ollama')
  const [selectedModel, setSelectedModel] = useState('')
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [recipientByDraft, setRecipientByDraft] = useState<Record<string, string>>({})
  const [approvingDraftId, setApprovingDraftId] = useState<string | null>(null)
  const [sendingDraftId, setSendingDraftId] = useState<string | null>(null)
  const [deletingDraftId, setDeletingDraftId] = useState<string | null>(null)
  const profileInputRef = useRef<HTMLInputElement>(null)
  const providerManuallySelectedRef = useRef(false)

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  })

  const { data: draftResponse, isLoading: isDraftsLoading } = useQuery({
    queryKey: ['coldemail-drafts'],
    queryFn: () => getColdEmailDrafts(50, 0),
    staleTime: 10_000,
  })

  const {
    data: coldEmailProfile,
    isLoading: isProfileLoading,
    isError: isProfileMissing,
  } = useQuery({
    queryKey: ['coldemail-profile'],
    queryFn: getColdEmailProfile,
    retry: false,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (draftResponse?.drafts) {
      setDrafts(draftResponse.drafts)
    }
  }, [draftResponse?.drafts, setDrafts])

  useEffect(() => {
    if (!drafts.length) return
    setRecipientByDraft((prev) => {
      const next = { ...prev }
      for (const draft of drafts) {
        if (!next[draft.id] && draft.recipient_email) {
          next[draft.id] = draft.recipient_email
        }
      }
      return next
    })
  }, [drafts])

  const availableProviders = useMemo<ChatProvider[]>(() => {
    if (!settings) return ['ollama']
    const providers: ChatProvider[] = []
    if (settings.has_gemini_key) providers.push('gemini')
    if (settings.has_openai_key) providers.push('openai')
    if (settings.has_anthropic_key) providers.push('anthropic')
    if (settings.has_ollama_cloud_key) providers.push('ollama_cloud')
    providers.push('ollama')
    return providers
  }, [settings])

  const modelOptions = useMemo<string[]>(() => {
    if (!settings?.saved_models?.[selectedProvider]) return []
    return settings.saved_models[selectedProvider]
  }, [selectedProvider, settings?.saved_models])

  useEffect(() => {
    if (!availableProviders.length) return
    const preferredProvider = availableProviders[0]

    if (!availableProviders.includes(selectedProvider)) {
      setSelectedProvider(preferredProvider)
      return
    }

    // Apply configured-provider priority by default, but do not override manual user choice.
    if (settings && !providerManuallySelectedRef.current && selectedProvider !== preferredProvider) {
      setSelectedProvider(preferredProvider)
      return
    }

    if (!selectedModel || !modelOptions.includes(selectedModel)) {
      setSelectedModel(modelOptions[0] || '')
    }
  }, [availableProviders, selectedProvider, selectedModel, modelOptions, settings])

  function fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result
        if (typeof result !== 'string') {
          reject(new Error('Could not read file data'))
          return
        }
        const split = result.split(',')
        resolve(split.length > 1 ? split[1] : result)
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(file)
    })
  }

  async function handleProfileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    if (coldEmailProfile && !allowProfileReupload) {
      toast.error('Enable resume update option before re-uploading your profile')
      e.target.value = ''
      return
    }

    setIsSavingProfile(true)
    try {
      const contentBase64 = await fileToBase64(file)
      const profile = await upsertColdEmailProfile({
        filename: file.name,
        content_base64: contentBase64,
        allow_reupload: Boolean(coldEmailProfile && allowProfileReupload),
      })
      setProfileFileName(profile.resume_filename || file.name)
      setAllowProfileReupload(false)
      toast.success('Profile saved and extracted from resume')
      await qc.invalidateQueries({ queryKey: ['coldemail-profile'] })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to save cold-email profile'
      toast.error(detail)
    } finally {
      setIsSavingProfile(false)
      e.target.value = ''
    }
  }

  async function handleGenerate() {
    const countries = countriesInput
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

    if (!countries.length) {
      toast.error('Please enter at least one country')
      return
    }

    if (usagePlan !== 'free' && !selectedProvider) {
      toast.error('Please select a provider')
      return
    }

    if (isProfileLoading) {
      toast.error('Please wait for profile status to load')
      return
    }

    if (!coldEmailProfile) {
      toast.error('Upload your resume first to create your cold-email profile')
      return
    }

    const appendRunLog = (message: string) => {
      const entry = `${new Date().toLocaleTimeString()} | ${message}`
      setRunLogs((prev) => [...prev, entry].slice(-40))
    }

    setGenerating(true)
    setRunLogs([])
    setProgressMessage('Starting cold-email generation...')
    appendRunLog('Starting cold-email generation...')

    try {
      await streamGenerateColdEmails(
        {
          countries,
          tone,
          ask_type: askType,
          max_professors: maxProfessors,
          provider: usagePlan === 'free' ? undefined : selectedProvider,
          model: usagePlan === 'free' ? undefined : (selectedModel || undefined),
          use_free_tier: usagePlan === 'free',
        },
        {
          onMeta: (event) => {
            const freeSuffix =
              event.use_free_tier && typeof event.free_tier_remaining === 'number'
                ? ` (free tier left: ${event.free_tier_remaining})`
                : ''
            const msg = `Using ${event.provider} / ${event.model}${freeSuffix}`
            setProgressMessage(msg)
            appendRunLog(msg)
          },
          onProgress: (event) => {
            setProgressMessage(event.message)
            appendRunLog(event.message)
          },
          onDraft: (draft) => {
            prependDraft(draft)
            appendRunLog(`Draft created for ${draft.professor_name} (${draft.country})`)
          },
          onDone: async (event) => {
            setProgressMessage(`Completed. Generated ${event.generated_count}, failed ${event.failed_count}.`)
            appendRunLog(`Completed. Generated ${event.generated_count}, failed ${event.failed_count}.`)

            if (event.generated_count === 0 && event.failed_count === 0) {
              toast.error('No drafts were generated. Check run logs below for scrape diagnostics.')
            } else {
              toast.success('Cold-email generation run completed')
            }

            await qc.invalidateQueries({ queryKey: ['coldemail-drafts'] })
          },
        }
      )
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Generation failed'
      toast.error(detail)
      setProgressMessage(detail)
      appendRunLog(`Error: ${detail}`)
    } finally {
      setGenerating(false)
    }
  }

  const approveMutation = useMutation({
    mutationFn: ({ draftId, recipientEmail }: { draftId: string; recipientEmail: string }) =>
      approveColdEmailDraft(draftId, { recipient_email: recipientEmail }),
  })

  const sendMutation = useMutation({
    mutationFn: ({ draftId, recipientEmail }: { draftId: string; recipientEmail?: string }) =>
      sendColdEmailDraft(draftId, { recipient_email: recipientEmail }),
  })

  const deleteMutation = useMutation({
    mutationFn: (draftId: string) => deleteColdEmailDraft(draftId),
  })

  async function handleApproveDraft(draftId: string) {
    const recipientEmail = (recipientByDraft[draftId] || '').trim()
    if (!recipientEmail) {
      toast.error('Enter recipient email before approving')
      return
    }

    setApprovingDraftId(draftId)
    try {
      await approveMutation.mutateAsync({ draftId, recipientEmail })
      toast.success('Draft approved for sending')
      await qc.invalidateQueries({ queryKey: ['coldemail-drafts'] })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to approve draft'
      toast.error(detail)
    } finally {
      setApprovingDraftId(null)
    }
  }

  async function handleSendDraft(draftId: string) {
    const recipientEmail = (recipientByDraft[draftId] || '').trim()

    setSendingDraftId(draftId)
    try {
      await sendMutation.mutateAsync({
        draftId,
        recipientEmail: recipientEmail || undefined,
      })
      toast.success('Email sent successfully')
      await qc.invalidateQueries({ queryKey: ['coldemail-drafts'] })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to send email'
      toast.error(detail)
    } finally {
      setSendingDraftId(null)
    }
  }

  async function handleDeleteDraft(draftId: string) {
    const proceed = window.confirm('Delete this draft permanently?')
    if (!proceed) {
      return
    }

    setDeletingDraftId(draftId)
    try {
      await deleteMutation.mutateAsync(draftId)
      setDrafts(drafts.filter((draft) => draft.id !== draftId))
      toast.success('Draft deleted')
      await qc.invalidateQueries({ queryKey: ['coldemail-drafts'] })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to delete draft'
      toast.error(detail)
    } finally {
      setDeletingDraftId(null)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Mail className="h-7 w-7 text-primary" />
          ScribeAI
        </h1>
        <p className="text-sm text-muted-foreground">
          Discover professors by country and generate personalized outreach drafts.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Generate Drafts
          </CardTitle>
          <CardDescription>Generate, review, and send personalized drafts.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Configured API Keys (same as SeerAI settings)</p>
            <div className="flex flex-wrap gap-2">
              <Badge variant={settings?.has_gemini_key ? 'default' : 'secondary'} className="gap-1.5">
                {settings?.has_gemini_key ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                Gemini
              </Badge>
              <Badge variant={settings?.has_openai_key ? 'default' : 'secondary'} className="gap-1.5">
                {settings?.has_openai_key ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                OpenAI
              </Badge>
              <Badge variant={settings?.has_anthropic_key ? 'default' : 'secondary'} className="gap-1.5">
                {settings?.has_anthropic_key ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                Anthropic
              </Badge>
              <Badge variant={settings?.has_ollama_cloud_key ? 'default' : 'secondary'} className="gap-1.5">
                {settings?.has_ollama_cloud_key ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                Ollama (Cloud)
              </Badge>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="countries">Countries (comma separated)</Label>
                <Input
                  id="countries"
                  value={countriesInput}
                  onChange={(e) => setCountriesInput(e.target.value)}
                  placeholder="Germany, France"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-professors" className="flex items-center gap-1.5">
                  Max Professors per Country
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center" aria-label="Max professors limit">
                          <Info className="h-3.5 w-3.5 text-muted-foreground" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        Limit is 50 per country in one run.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </Label>
                <Input
                  id="max-professors"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={String(maxProfessors)}
                  onChange={(e) => {
                    const digitsOnly = e.target.value.replace(/\D/g, '')
                    const parsed = Number(digitsOnly || '1')
                    setMaxProfessors(Math.max(1, Math.min(50, parsed)))
                  }}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tone</Label>
                <Select value={tone} onValueChange={setTone}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="friendly">Friendly</SelectItem>
                    <SelectItem value="enthusiastic">Enthusiastic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Ask Type</Label>
                <Select value={askType} onValueChange={(value) => setAskType(value as ColdEmailAskType)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(ASK_TYPE_LABELS) as ColdEmailAskType[]).map((key) => (
                      <SelectItem key={key} value={key}>
                        {ASK_TYPE_LABELS[key]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Usage Plan</Label>
                <Select value={usagePlan} onValueChange={(value) => setUsagePlan(value as 'standard' | 'free')}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="free">Free Tier (5 total)</SelectItem>
                  </SelectContent>
                </Select>
                {usagePlan === 'free' && (
                  <p className="text-xs text-muted-foreground">
                    Free Tier uses Oppora&apos;s Cloud model.
                  </p>
                )}
              </div>
              <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                Provider
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center" aria-label="Provider tradeoffs">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      Local models (Ollama) are private and low-cost, but can be slower and less consistent for nuanced personalization. Cloud models often produce stronger writing quality with added API cost.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </Label>
              <Select
                value={selectedProvider}
                onValueChange={(value) => {
                  const nextProvider = value as ChatProvider
                  const nextOptions = settings?.saved_models?.[nextProvider] || []
                  providerManuallySelectedRef.current = true
                  setSelectedProvider(nextProvider)
                  setSelectedModel(nextOptions[0] || '')
                }}
              >
                <SelectTrigger disabled={usagePlan === 'free'}>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {availableProviders.map((provider) => (
                    <SelectItem key={provider} value={provider}>
                      {PROVIDER_LABELS[provider]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              </div>
              <div className="space-y-2">
                <Label>Model</Label>
                <Select
                  value={selectedModel && modelOptions.includes(selectedModel) ? selectedModel : ''}
                  onValueChange={(value) => setSelectedModel(value)}
                >
                  <SelectTrigger disabled={usagePlan === 'free' || !selectedProvider || modelOptions.length === 0}>
                    <SelectValue placeholder={modelOptions.length ? 'Choose model' : 'No configured models'} />
                  </SelectTrigger>
                  <SelectContent>
                    {modelOptions.map((model) => (
                      <SelectItem key={model} value={model}>
                        {model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="rounded-md border border-border p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Label>Student Profile (Required)</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Upload your resume once. The platform extracts and stores profile details for reuse in every draft run.
                </p>
              </div>
              {coldEmailProfile && (
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={allowProfileReupload}
                    onChange={(e) => setAllowProfileReupload(e.target.checked)}
                    className="h-3.5 w-3.5"
                  />
                  I updated my resume and want to replace my saved profile
                </label>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={isSavingProfile || (Boolean(coldEmailProfile) && !allowProfileReupload)}
                onClick={() => profileInputRef.current?.click()}
              >
                {isSavingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                {isSavingProfile
                  ? 'Saving Profile...'
                  : coldEmailProfile
                    ? 'Re-upload Resume (.pdf/.txt)'
                    : 'Upload Resume (.pdf/.txt)'}
              </Button>
              <input
                ref={profileInputRef}
                type="file"
                accept=".pdf,.txt,.md"
                className="hidden"
                onChange={handleProfileUpload}
              />
            </div>

            {isProfileLoading ? (
              <p className="text-xs text-muted-foreground">Checking profile status...</p>
            ) : coldEmailProfile ? (
              <div className="rounded-md border border-border/80 p-3 space-y-2 bg-muted/20">
                <p className="text-xs text-muted-foreground">
                  Saved profile from: {coldEmailProfile.resume_filename || profileFileName || 'uploaded resume'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Name: {coldEmailProfile.profile.full_name || 'Not detected'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Degree: {coldEmailProfile.profile.degree || 'Not detected'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Interests: {(coldEmailProfile.profile.research_interests || []).slice(0, 6).join(', ') || 'Not detected'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Skills: {(coldEmailProfile.profile.technical_skills || []).slice(0, 8).join(', ') || 'Not detected'}
                </p>
              </div>
            ) : (
              <p className="text-xs text-amber-600">
                No profile found yet. Upload resume to unlock cold-email generation.
              </p>
            )}

            {isProfileMissing && !coldEmailProfile && (
              <p className="text-xs text-muted-foreground">
                First-time setup required for your account.
              </p>
            )}

            {coldEmailProfile && !allowProfileReupload && (
              <p className="text-xs text-muted-foreground">
                Re-upload is locked. Enable the update option to replace your existing profile.
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={handleGenerate} disabled={isGenerating || isProfileLoading || !coldEmailProfile}>
              {isGenerating && <Loader2 className="h-4 w-4 animate-spin" />}
              {isGenerating ? 'Generating...' : 'Generate Cold Emails'}
            </Button>
            {progressMessage && (
              <p className="text-sm text-muted-foreground">{progressMessage}</p>
            )}
          </div>

          {runLogs.length > 0 && (
            <div className="rounded-md border border-border p-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">Run Logs</p>
              <div className="max-h-44 overflow-auto space-y-1">
                {runLogs.map((line, index) => (
                  <p key={`${index}-${line}`} className="text-xs font-mono text-muted-foreground">
                    {line}
                  </p>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Draft History</CardTitle>
          <CardDescription>
            Most recent generated drafts for your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isDraftsLoading ? (
            <p className="text-sm text-muted-foreground">Loading drafts...</p>
          ) : drafts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No drafts yet. Run generation to create your first set.</p>
          ) : (
            drafts.map((draft) => (
              <div key={draft.id} className="rounded-md border border-border p-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">{draft.professor_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {draft.university_name || 'Unknown University'} · {draft.country} · {formatDate(draft.created_at)}
                    </p>
                    {draft.profile_url && (
                      <a
                        href={draft.profile_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-primary underline-offset-4 hover:underline"
                      >
                        Professor webpage
                      </a>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{draft.status}</Badge>
                    <Badge variant="secondary">{ASK_TYPE_LABELS[draft.ask_type] || draft.ask_type}</Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        await navigator.clipboard.writeText(`Subject: ${draft.subject_line}\n\n${draft.body}`)
                        toast.success('Draft copied to clipboard')
                      }}
                    >
                      <Copy className="h-4 w-4" />
                      Copy
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteDraft(draft.id)}
                      disabled={deletingDraftId === draft.id || sendingDraftId === draft.id || approvingDraftId === draft.id}
                    >
                      {deletingDraftId === draft.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      {deletingDraftId === draft.id ? 'Deleting...' : 'Delete'}
                    </Button>
                  </div>
                </div>
                <div className="rounded-md border border-border/70 bg-background p-3 space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Email draft</p>
                  <p className="text-sm font-medium">Subject: {draft.subject_line}</p>
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{draft.body}</p>
                </div>

                {draft.research_matches?.length > 0 && (
                  <div className="rounded-md border border-border/80 bg-muted/20 p-3 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Research used for this draft</p>
                    <div className="space-y-2">
                      {draft.research_matches.map((item, index) => (
                        <div key={`${draft.id}-research-${index}`} className="rounded border border-border/70 bg-background/40 p-2 space-y-1">
                          <p className="text-sm font-medium">
                            {item.title}
                            {item.year ? ` (${item.year})` : ''}
                          </p>
                          <p className="text-xs text-muted-foreground">Similarity score: {item.similarity_score.toFixed(3)}</p>
                          {item.url && (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-primary underline-offset-4 hover:underline"
                            >
                              Open research link
                            </a>
                          )}
                          {item.abstract && (
                            <p className="text-xs text-muted-foreground leading-relaxed">{item.abstract}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2 pt-1">
                  <Input
                    type="email"
                    placeholder="recipient@example.edu"
                    value={recipientByDraft[draft.id] ?? ''}
                    onChange={(e) => {
                      const value = e.target.value
                      setRecipientByDraft((prev) => ({ ...prev, [draft.id]: value }))
                    }}
                  />
                  <Button
                    variant="outline"
                    onClick={() => handleApproveDraft(draft.id)}
                    disabled={approvingDraftId === draft.id || sendingDraftId === draft.id}
                  >
                    {approvingDraftId === draft.id ? 'Approving...' : 'Approve'}
                  </Button>
                  <Button
                    onClick={() => handleSendDraft(draft.id)}
                    disabled={sendingDraftId === draft.id || approvingDraftId === draft.id}
                  >
                    {sendingDraftId === draft.id ? 'Sending...' : 'Send'}
                  </Button>
                </div>

                {(draft.sent_at || draft.last_error) && (
                  <p className="text-xs text-muted-foreground">
                    {draft.sent_at ? `Sent at ${formatDate(draft.sent_at)}` : `Last error: ${draft.last_error}`}
                  </p>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
