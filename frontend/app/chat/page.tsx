'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as SelectPrimitive from '@radix-ui/react-select'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createChatThread, deleteChatThread, getChatMessages, getChatThreads, getSettings, streamChatMessage } from '@/lib/api'
import { useChatStore } from '@/store/chatStore'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  MessageSquare,
  Send,
  Upload,
  X,
  FileText,
  Check,
  ChevronDown,
  ChevronUp,
  Bot,
  User,
  Plus,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn, formatType } from '@/lib/utils'
import type { ChatContextOpportunity, ChatProvider, ChatThreadSummary } from '@/lib/types'

const MAX_RESUME_PAGES = 2

const PROVIDER_LABELS: Record<ChatProvider, string> = {
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  ollama: 'Ollama (Local)',
  ollama_cloud: 'Ollama (Cloud)',
}

function formatModelLabel(model: string): string {
  const overrides: Record<string, string> = {
    ai: 'AI',
    gpt: 'GPT',
    llm: 'LLM',
    api: 'API',
  }

  return model
    .split(/[-_]+/)
    .filter(Boolean)
    .map((token) => {
      const lower = token.toLowerCase()
      if (overrides[lower]) return overrides[lower]
      if (/^[0-9.]+$/.test(token)) return token
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}

function formatProviderLabel(provider: string | undefined): string {
  if (!provider) return ''
  const key = provider.toLowerCase() as ChatProvider
  return PROVIDER_LABELS[key] || provider
}

export default function ChatPage() {
  const qc = useQueryClient()
  const {
    messages,
    resumeText,
    resumeName,
    selectedProvider,
    selectedModel,
    selectedThreadId,
    addMessage,
    setMessages,
    setResume,
    clearResume,
    setModelSelection,
    setSelectedThreadId,
  } = useChatStore()
  const [input, setInput] = useState('')
  const [usagePlan, setUsagePlan] = useState<'standard' | 'free'>('standard')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState<{
    content: string
    provider?: string
    model?: string
    context?: ChatContextOpportunity[]
  } | null>(null)
  const [expandedCtx, setExpandedCtx] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: settings, isLoading: isSettingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  })

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
    if (!selectedProvider) return []
    return settings?.saved_models?.[selectedProvider] || []
  }, [selectedProvider, settings?.saved_models])

  const { data: threads, isLoading: isThreadsLoading } = useQuery({
    queryKey: ['chat-threads'],
    queryFn: getChatThreads,
    staleTime: 10_000,
  })

  const { data: threadMessages, isLoading: isMessagesLoading } = useQuery({
    queryKey: ['chat-messages', selectedThreadId],
    queryFn: () => getChatMessages(selectedThreadId as string),
    enabled: !!selectedThreadId,
    staleTime: 0,
  })

  useEffect(() => {
    if (!threads || threads.length === 0) {
      if (selectedThreadId !== null) {
        setSelectedThreadId(null)
      }
      return
    }

    if (!selectedThreadId) {
      setSelectedThreadId(threads[0].id)
      return
    }

    const exists = threads.some((thread) => thread.id === selectedThreadId)
    if (!exists) {
      setSelectedThreadId(threads[0].id)
    }
  }, [threads, selectedThreadId, setSelectedThreadId])

  useEffect(() => {
    if (!selectedThreadId) {
      setMessages([])
      return
    }
    if (threadMessages) {
      setMessages(threadMessages)
    }
  }, [selectedThreadId, threadMessages, setMessages])

  useEffect(() => {
    if (!availableProviders.length) return

    const nextProvider =
      selectedProvider && availableProviders.includes(selectedProvider)
        ? selectedProvider
        : availableProviders[0]

    const nextModelOptions = settings?.saved_models?.[nextProvider] || []
    const providerChanged = nextProvider !== selectedProvider
    const hasCurrentModel = !!selectedModel && nextModelOptions.includes(selectedModel)
    const nextModel = providerChanged
      ? (nextModelOptions[0] || '')
      : (hasCurrentModel ? (selectedModel as string) : (nextModelOptions[0] || ''))

    if (providerChanged || selectedModel === null || !hasCurrentModel) {
      setModelSelection(nextProvider, nextModel)
    }
  }, [
    availableProviders,
    selectedProvider,
    selectedModel,
    setModelSelection,
    settings?.saved_models,
  ])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const createThreadMutation = useMutation({
    mutationFn: () => createChatThread(),
    onSuccess: (thread) => {
      qc.setQueryData<ChatThreadSummary[]>(['chat-threads'], (prev) => {
        const list = prev || []
        const withoutCurrent = list.filter((item) => item.id !== thread.id)
        return [thread, ...withoutCurrent]
      })
      setSelectedThreadId(thread.id)
      setMessages([])
      setExpandedCtx(null)
      qc.setQueryData(['chat-messages', thread.id], [])
      qc.invalidateQueries({ queryKey: ['chat-threads'] })
    },
    onError: () => {
      toast.error('Failed to create new chat')
    },
  })

  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: string) => deleteChatThread(threadId),
    onSuccess: (_, deletedThreadId) => {
      let updated: ChatThreadSummary[] = []
      qc.setQueryData<ChatThreadSummary[]>(['chat-threads'], (prev) => {
        updated = (prev || []).filter((thread) => thread.id !== deletedThreadId)
        return updated
      })
      qc.removeQueries({ queryKey: ['chat-messages', deletedThreadId] })

      if (selectedThreadId === deletedThreadId) {
        setMessages([])
        setExpandedCtx(null)
        setSelectedThreadId(updated[0]?.id ?? null)
      }

      qc.invalidateQueries({ queryKey: ['chat-threads'] })
      toast.success('Chat deleted')
    },
    onError: (error) => {
      let detail = 'Failed to delete chat'
      if (axios.isAxiosError(error)) {
        const data = error.response?.data as { detail?: string } | undefined
        if (typeof data?.detail === 'string' && data.detail.trim()) {
          detail = data.detail.trim()
        }
      }
      toast.error(detail)
    },
  })

  async function handleSend() {
    const text = input.trim()
    if (!text || isStreaming) return

    if (usagePlan !== 'free' && selectedProvider && modelOptions.length === 0) {
      toast.error(`No models configured for ${PROVIDER_LABELS[selectedProvider]}. Add one in Settings first.`)
      return
    }

    addMessage({ role: 'user', content: text })
    setInput('')

    setIsStreaming(true)
    setStreamingMessage({
      content: '',
      provider: usagePlan === 'free' ? undefined : (selectedProvider || undefined),
      model: usagePlan === 'free' ? undefined : (selectedModel || undefined),
      context: [],
    })

    let finalThreadId = selectedThreadId || null
    let finalProvider: string | undefined = usagePlan === 'free' ? undefined : (selectedProvider || undefined)
    let finalModel = usagePlan === 'free' ? undefined : (selectedModel || undefined)
    let finalContext: ChatContextOpportunity[] = []
    let streamedContent = ''

    try {
      await streamChatMessage(
        {
          message: text,
          resume_text: resumeText || undefined,
          provider: usagePlan === 'free' ? undefined : (selectedProvider || undefined),
          model: usagePlan === 'free' ? undefined : (selectedModel || undefined),
          use_free_tier: usagePlan === 'free',
          thread_id: selectedThreadId || undefined,
        },
        {
          onMeta: (event) => {
            finalThreadId = event.thread_id
            finalProvider = event.provider
            finalModel = event.model
            finalContext = event.opportunities
            setStreamingMessage((prev) => ({
              content: prev?.content || '',
              provider: event.provider,
              model: event.model,
              context: event.opportunities,
            }))
          },
          onDelta: ({ content }) => {
            streamedContent += content
            setStreamingMessage((prev) => ({
              content: streamedContent,
              provider: prev?.provider,
              model: prev?.model,
              context: prev?.context,
            }))
          },
          onDone: (event) => {
            finalThreadId = event.thread_id
            finalProvider = event.provider
            finalModel = event.model
            finalContext = event.opportunities
            streamedContent = event.answer
          },
        }
      )

      const finalAnswer = streamedContent.trim()
      if (!finalAnswer) {
        throw new Error('Provider returned an empty response')
      }

      if (finalThreadId && (!selectedThreadId || finalThreadId !== selectedThreadId)) {
        setSelectedThreadId(finalThreadId)
      }

      addMessage({
        role: 'assistant',
        content: finalAnswer,
        context: finalContext,
        provider: finalProvider,
        model: finalModel,
      })

      if (finalThreadId) {
        qc.invalidateQueries({ queryKey: ['chat-threads'] })
        qc.invalidateQueries({ queryKey: ['chat-messages', finalThreadId] })
      }
    } catch (error) {
      const detail = error instanceof Error && error.message ? error.message : 'Chat request failed'
      addMessage({
        role: 'assistant',
        content: `Sorry, I encountered an error: ${detail}`,
      })
      toast.error(detail)
    } finally {
      setIsStreaming(false)
      setStreamingMessage(null)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.type !== 'application/pdf') {
      toast.error('Only PDF files are supported')
      return
    }

    // We send the file to backend for text extraction — but the frontend
    // currently uses PyMuPDF server-side. We'll send the binary and let
    // the backend handle it. Since the backend /api/chat only accepts
    // resume_text (string), we show a message here.
    toast.info('Resume support: paste your resume text or use the backend extraction endpoint.')
    e.target.value = ''
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <MessageSquare className="h-5 w-5 text-primary" />
          <div>
            <h1 className="font-semibold">SeerAI</h1>
            <p className="text-xs text-muted-foreground">
              Ask about opportunities, get recommendations
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={selectedThreadId ?? ''}
            onValueChange={(value) => {
              setSelectedThreadId(value)
              setExpandedCtx(null)
            }}
          >
            <SelectTrigger className="w-[260px]">
              <SelectValue placeholder={isThreadsLoading ? 'Loading chats...' : 'Select a chat'} />
            </SelectTrigger>
            <SelectContent>
              {(threads || []).map((thread) => (
                <SelectPrimitive.Item
                  key={thread.id}
                  value={thread.id}
                  className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-2 pr-10 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                >
                  <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
                    <SelectPrimitive.ItemIndicator>
                      <Check className="h-4 w-4" />
                    </SelectPrimitive.ItemIndicator>
                  </span>
                  <SelectPrimitive.ItemText>
                    <span className="block max-w-[180px] truncate">{thread.title}</span>
                  </SelectPrimitive.ItemText>
                  <div className="absolute right-6 top-1/2 -translate-y-1/2">
                    <button
                      type="button"
                      className="inline-flex h-6 w-6 items-center justify-center rounded-sm text-muted-foreground hover:bg-muted hover:text-destructive"
                      onPointerDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        if (!deleteThreadMutation.isPending) {
                          deleteThreadMutation.mutate(thread.id)
                        }
                      }}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                      }}
                      disabled={deleteThreadMutation.isPending}
                      title={`Delete ${thread.title}`}
                      aria-label={`Delete ${thread.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </SelectPrimitive.Item>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => createThreadMutation.mutate()}
            disabled={createThreadMutation.isPending || deleteThreadMutation.isPending}
          >
            <Plus className="h-3.5 w-3.5" />
            {createThreadMutation.isPending ? 'Creating...' : 'New Chat'}
          </Button>
          {resumeName && (
            <div className="flex items-center gap-1.5 text-xs bg-muted rounded-md px-2 py-1">
              <FileText className="h-3 w-3 text-primary" />
              <span className="text-muted-foreground">{resumeName}</span>
              <button onClick={clearResume} className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="border-b border-border px-6 py-3 bg-muted/20 flex-shrink-0">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Configured API Keys</p>
            {isSettingsLoading ? (
              <div className="flex gap-2">
                <Skeleton className="h-6 w-28" />
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-28" />
              </div>
            ) : (
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
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:min-w-[640px]">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Usage Plan</Label>
              <Select
                value={usagePlan}
                onValueChange={(value) => setUsagePlan(value as 'standard' | 'free')}
              >
                <SelectTrigger disabled={isStreaming || isSettingsLoading}>
                  <SelectValue placeholder="Choose plan" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="standard">Standard</SelectItem>
                  <SelectItem value="free">Free Tier (5 total)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Provider</Label>
              <Select
                value={selectedProvider ?? ''}
                onValueChange={(value) => {
                  const nextProvider = value as ChatProvider
                  const nextOptions = settings?.saved_models?.[nextProvider] || []
                  setModelSelection(nextProvider, nextOptions[0] || '')
                }}
              >
                <SelectTrigger disabled={usagePlan === 'free' || isStreaming || isSettingsLoading}>
                  <SelectValue placeholder="Choose provider" />
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

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Model</Label>
              <div className="space-y-2">
                <Select
                  value={selectedModel && modelOptions.includes(selectedModel) ? selectedModel : ''}
                  onValueChange={(value) => {
                    if (!selectedProvider) return
                    setModelSelection(selectedProvider, value)
                  }}
                >
                  <SelectTrigger disabled={usagePlan === 'free' || isStreaming || !selectedProvider || modelOptions.length === 0}>
                    <SelectValue placeholder={modelOptions.length ? 'Choose model' : 'No configured models'} />
                  </SelectTrigger>
                  <SelectContent>
                    {modelOptions.map((model) => (
                      <SelectItem key={model} value={model}>
                        {formatModelLabel(model)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {selectedThreadId && isMessagesLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-4/5" />
          </div>
        )}

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <Bot className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <h2 className="text-lg font-semibold text-muted-foreground">
              Ask me about opportunities
            </h2>
            <p className="text-sm text-muted-foreground/70 mt-2 max-w-md">
              I can help you find most relevant opportunities based on your interests.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {[
                'Find hackathons for ML engineers',
                'Show active team-based hackathons',
                'What are the upcoming deadlines?',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  className="text-xs border border-border rounded-full px-3 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  onClick={() => setInput(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            {msg.role === 'assistant' && (
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary mt-1">
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div className={cn('max-w-[80%] space-y-2', msg.role === 'user' ? 'items-end' : 'items-start')}>
              <div
                className={cn(
                  'rounded-xl px-4 py-3 text-sm leading-relaxed',
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-sm'
                    : 'bg-card border border-border rounded-bl-sm'
                )}
              >
                {msg.role === 'assistant' ? (
                  <div className="space-y-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_p]:whitespace-pre-wrap [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:leading-relaxed [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>

              {msg.role === 'assistant' && msg.provider && (
                <div className="flex items-center gap-1.5 pl-1">
                  <span className="text-[10px] text-muted-foreground/60">
                    {formatProviderLabel(msg.provider)} · {formatModelLabel(msg.model || '')}
                  </span>
                  {msg.context && msg.context.length > 0 && (
                    <button
                      className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors ml-1"
                      onClick={() => setExpandedCtx(expandedCtx === i ? null : i)}
                    >
                      {expandedCtx === i ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      {msg.context.length} sources
                    </button>
                  )}
                </div>
              )}

              {expandedCtx === i && msg.context && msg.context.length > 0 && (
                <Card className="p-3 space-y-1.5">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                    Retrieved Context
                  </p>
                  {msg.context.map((ctx: ChatContextOpportunity) => (
                    <div key={ctx.id} className="flex items-center justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">{ctx.title}</p>
                        <p className="text-[10px] text-muted-foreground">{ctx.source} · {formatType(ctx.opportunity_type)}</p>
                      </div>
                      <a href={ctx.url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                      </a>
                    </div>
                  ))}
                </Card>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-muted mt-1">
                <User className="h-4 w-4 text-muted-foreground" />
              </div>
            )}
          </div>
        ))}

        {isStreaming && streamingMessage && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary mt-1">
              <Bot className="h-4 w-4" />
            </div>
            <div className="max-w-[80%] space-y-2">
              <div className="bg-card border border-border rounded-xl rounded-bl-sm px-4 py-3 text-sm leading-relaxed">
                {streamingMessage.content ? (
                  <div className="space-y-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_p]:whitespace-pre-wrap [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:leading-relaxed [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingMessage.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Skeleton className="h-3 w-48" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                )}
              </div>
              {(streamingMessage.provider || streamingMessage.model) && (
                <div className="flex items-center gap-1.5 pl-1">
                  <span className="text-[10px] text-muted-foreground/60">
                    {formatProviderLabel(streamingMessage.provider)} · {formatModelLabel(streamingMessage.model || '')}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border px-6 py-4 flex-shrink-0">
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <Textarea
              placeholder="Ask about opportunities... (Enter to send, Shift+Enter for newline)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              className="min-h-[60px] resize-none"
              disabled={isStreaming || isMessagesLoading}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming || isMessagesLoading}
              size="icon"
            >
              <Send className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              title="Upload resume (PDF)"
            >
              <Upload className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleResumeUpload}
        />
        {resumeText && (
          <p className="text-xs text-muted-foreground mt-2">
            Resume loaded: {resumeName} · Context will be included in responses
          </p>
        )}
      </div>
    </div>
  )
}
