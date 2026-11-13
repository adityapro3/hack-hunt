'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { addSavedModel, getSettings, removeSavedModel, updateSettings } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Settings, Key, Bot, Play, CheckCircle2, XCircle, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import type { ChatProvider, UpdateSettingsPayload } from '@/lib/types'

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

export default function SettingsPage() {
  const qc = useQueryClient()
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  })

  const [form, setForm] = useState<UpdateSettingsPayload>({
    gemini_api_key: '',
    openai_api_key: '',
    anthropic_api_key: '',
    ollama_cloud_api_key: '',
    ollama_base_url: 'http://localhost:11434',
  })
  const [modelProvider, setModelProvider] = useState<ChatProvider>('ollama')
  const [modelName, setModelName] = useState('')

  useEffect(() => {
    if (settings) {
      setForm((prev) => ({
        ...prev,
        ollama_base_url: settings.ollama_base_url,
      }))
    }
  }, [settings])

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      toast.success('Settings saved!')
      qc.invalidateQueries({ queryKey: ['settings'] })
      setForm((prev) => ({
        ...prev,
        gemini_api_key: '',
        openai_api_key: '',
        anthropic_api_key: '',
        ollama_cloud_api_key: '',
      }))
    },
    onError: () => toast.error('Failed to save settings'),
  })

  const addModelMutation = useMutation({
    mutationFn: () => addSavedModel({ provider: modelProvider, model: modelName.trim() }),
    onSuccess: () => {
      toast.success('Model saved')
      setModelName('')
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: () => toast.error('Failed to save model'),
  })

  const removeModelMutation = useMutation({
    mutationFn: ({ provider, model }: { provider: ChatProvider; model: string }) =>
      removeSavedModel(provider, model),
    onSuccess: () => {
      toast.success('Model removed')
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: () => toast.error('Failed to remove model'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: UpdateSettingsPayload = {}
    if (form.gemini_api_key) payload.gemini_api_key = form.gemini_api_key
    if (form.openai_api_key) payload.openai_api_key = form.openai_api_key
    if (form.anthropic_api_key) payload.anthropic_api_key = form.anthropic_api_key
    if (form.ollama_cloud_api_key) payload.ollama_cloud_api_key = form.ollama_cloud_api_key
    if (form.ollama_base_url) payload.ollama_base_url = form.ollama_base_url
    updateMutation.mutate(payload)
  }

  function handleAddSavedModel() {
    if (!modelName.trim()) {
      toast.error('Enter a model name')
      return
    }
    addModelMutation.mutate()
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-muted-foreground" />
          Settings
        </h1>
        <p className="text-muted-foreground text-sm mt-1">Configure LLM providers and scraping</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* LLM API Keys */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Key className="h-4 w-4" />
              LLM API Keys
            </CardTitle>
            <CardDescription>
              Configure at least one provider for SeerAI. Keys are stored securely.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="gemini">Google Gemini</Label>
                    {settings?.has_gemini_key ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" /> Configured
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3 w-3" /> Not set
                      </span>
                    )}
                  </div>
                  <Input
                    id="gemini"
                    type="password"
                    placeholder={settings?.has_gemini_key ? '•••••••• (leave blank to keep)' : 'Enter Gemini API key'}
                    value={form.gemini_api_key || ''}
                    onChange={(e) => setForm((p) => ({ ...p, gemini_api_key: e.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="openai">OpenAI</Label>
                    {settings?.has_openai_key ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" /> Configured
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3 w-3" /> Not set
                      </span>
                    )}
                  </div>
                  <Input
                    id="openai"
                    type="password"
                    placeholder={settings?.has_openai_key ? '•••••••• (leave blank to keep)' : 'Enter OpenAI API key'}
                    value={form.openai_api_key || ''}
                    onChange={(e) => setForm((p) => ({ ...p, openai_api_key: e.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="anthropic">Anthropic (Claude)</Label>
                    {settings?.has_anthropic_key ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" /> Configured
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3 w-3" /> Not set
                      </span>
                    )}
                  </div>
                  <Input
                    id="anthropic"
                    type="password"
                    placeholder={settings?.has_anthropic_key ? '•••••••• (leave blank to keep)' : 'Enter Anthropic API key'}
                    value={form.anthropic_api_key || ''}
                    onChange={(e) => setForm((p) => ({ ...p, anthropic_api_key: e.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="ollama-cloud-key">Ollama Cloud</Label>
                    {settings?.has_ollama_cloud_key ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" /> Configured
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3 w-3" /> Not set
                      </span>
                    )}
                  </div>
                  <Input
                    id="ollama-cloud-key"
                    type="password"
                    placeholder={settings?.has_ollama_cloud_key ? '•••••••• (leave blank to keep)' : 'Enter Ollama Cloud API key'}
                    value={form.ollama_cloud_api_key || ''}
                    onChange={(e) => setForm((p) => ({ ...p, ollama_cloud_api_key: e.target.value }))}
                  />
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Ollama Config */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Bot className="h-4 w-4" />
              Ollama (Local LLM)
            </CardTitle>
            <CardDescription>
              Use a locally running Ollama instance as a fallback or primary provider.
              Configure Ollama model names in Saved Chat Models below.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-9 w-full" />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="ollama-url">Base URL</Label>
                  <Input
                    id="ollama-url"
                    placeholder="http://localhost:11434"
                    value={form.ollama_base_url || ''}
                    onChange={(e) => setForm((p) => ({ ...p, ollama_base_url: e.target.value }))}
                  />
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Bot className="h-4 w-4" />
              Saved Chat Models
            </CardTitle>
            <CardDescription>
              Save model names per provider to reuse them quickly in chat.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <Select value={modelProvider} onValueChange={(v) => setModelProvider(v as ChatProvider)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(PROVIDER_LABELS) as ChatProvider[]).map((provider) => (
                        <SelectItem key={provider} value={provider}>
                          {PROVIDER_LABELS[provider]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="e.g. gemma-3-12b-it"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    className="md:col-span-2"
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddSavedModel}
                  disabled={addModelMutation.isPending}
                  className="w-full"
                >
                  <Plus className="h-4 w-4" />
                  {addModelMutation.isPending ? 'Saving model...' : 'Add Saved Model'}
                </Button>

                <div className="space-y-3">
                  {(Object.keys(PROVIDER_LABELS) as ChatProvider[]).map((provider) => {
                    const models = settings?.saved_models?.[provider] || []
                    return (
                      <div key={provider} className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground">{PROVIDER_LABELS[provider]}</p>
                        {models.length === 0 ? (
                          <p className="text-xs text-muted-foreground/70">No saved models</p>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {models.map((model) => (
                              <Badge key={`${provider}:${model}`} variant="secondary" className="gap-1.5 pr-1">
                                {formatModelLabel(model)}
                                <button
                                  type="button"
                                  className="rounded p-0.5 hover:bg-background"
                                  onClick={() => removeModelMutation.mutate({ provider, model })}
                                  disabled={removeModelMutation.isPending}
                                  title={`Remove ${model}`}
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Button type="submit" disabled={updateMutation.isPending || isLoading} className="w-full">
          {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
        </Button>
      </form>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Play className="h-4 w-4" />
            Admin Tools
          </CardTitle>
          <CardDescription>
            Scraper controls are now available on the Admin page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" variant="outline" className="w-full" onClick={() => (window.location.href = '/admin')}>
            Open Admin Page
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
