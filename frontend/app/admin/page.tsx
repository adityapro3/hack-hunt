'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cleanupExpiredOpportunities,
  getAvailableScrapers,
  streamBackfillNewsEmbeddings,
  streamBackfillNewsTopics,
  streamBackfillOpportunityEmbeddings,
  streamRunNewsScrapers,
  streamRunScraper,
} from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Shield, Play, Newspaper, Trash2, Database, Tags } from 'lucide-react'
import { formatType } from '@/lib/utils'
import { toast } from 'sonner'

type AdminLogPanel = {
  title: string
  lines: string[]
}

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeError = error as {
      response?: { data?: { detail?: string } }
      message?: string
    }

    if (typeof maybeError.response?.data?.detail === 'string' && maybeError.response.data.detail.trim()) {
      return maybeError.response.data.detail
    }

    if (typeof maybeError.message === 'string' && maybeError.message.trim()) {
      return maybeError.message
    }
  }

  return 'Request failed'
}

export default function AdminPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [selected, setSelected] = useState<string[]>([])
  const [newsKeepDays, setNewsKeepDays] = useState(3)
  const [adminLogs, setAdminLogs] = useState<AdminLogPanel | null>(null)
  const logContainerRef = useRef<HTMLDivElement | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['scraper-available'],
    queryFn: getAvailableScrapers,
    enabled: !!user?.is_admin,
    staleTime: 60_000,
  })

  const selectedCount = useMemo(() => selected.length, [selected])
  const availableScrapers = data?.scrapers || []
  const allSelected = availableScrapers.length > 0 && selectedCount === availableScrapers.length

  useEffect(() => {
    if (!logContainerRef.current) {
      return
    }

    logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
  }, [adminLogs?.title, adminLogs?.lines.length])

  function clearCaches() {
    qc.removeQueries({ queryKey: ['opportunities'] })
    qc.removeQueries({ queryKey: ['filters'] })
    qc.invalidateQueries({ queryKey: ['news-latest-by-source'] })
    qc.invalidateQueries({ queryKey: ['news-feed'] })
    qc.invalidateQueries({ queryKey: ['news-filters'] })
  }

  function showLogs(title: string, lines: string[]) {
    setAdminLogs({ title, lines })
  }

  function replaceLogs(title: string, lines: string[] | undefined, fallback: string) {
    showLogs(title, lines && lines.length > 0 ? lines : [fallback])
  }

  function appendLogLine(title: string, line: string) {
    setAdminLogs((current) => {
      if (current?.title === title && current.lines[current.lines.length - 1] === line) {
        return current
      }

      return {
        title,
        lines: current?.title === title ? [...current.lines, line] : [line],
      }
    })
  }

  const runMutation = useMutation({
    mutationFn: (sources: string[]) =>
      streamRunScraper(sources, {
        onLog: (line) => appendLogLine('Hackathon Scrapers', line),
      }),
    onMutate: (sources) => {
      showLogs(
        'Hackathon Scrapers',
        [
          `Starting hackathon scraper run for ${
            sources.length > 0 ? sources.map((source) => formatType(source)).join(', ') : 'all available sources'
          }`,
        ]
      )
    },
    onSuccess: (result) => {
      replaceLogs('Hackathon Scrapers', result.logs, 'Hackathon scraper run completed')
      toast.success(`Scraped ${result.total_scraped} and saved ${result.total_saved}`)
      clearCaches()
    },
    onError: (error) => {
      appendLogLine('Hackathon Scrapers', `Run failed: ${getErrorMessage(error)}`)
      toast.error('Failed to run scraper')
    },
  })

  const runNewsScrapeMutation = useMutation({
    mutationFn: () =>
      streamRunNewsScrapers({
        max_pages_per_source: 12,
        keep_days: 3,
      }, {
        onLog: (line) => appendLogLine('News Scrapers', line),
      }),
    onMutate: () => {
      showLogs('News Scrapers', ['Starting latest-news scrape for all configured sources'])
    },
    onSuccess: (result) => {
      replaceLogs('News Scrapers', result.logs, 'News scrape completed')
      toast.success(
        `News scrape completed: scraped ${result.total_scraped}, saved ${result.total_saved}`
      )
      clearCaches()
    },
    onError: (error) => {
      appendLogLine('News Scrapers', `Run failed: ${getErrorMessage(error)}`)
      toast.error('Failed to run news scrapers')
    },
  })

  const backfillOpportunityEmbeddingsMutation = useMutation({
    mutationFn: () =>
      streamBackfillOpportunityEmbeddings({
        batch_size: 16,
        run_until_empty: true,
      }, {
        onLog: (line) => appendLogLine('Opportunity Embeddings', line),
      }),
    onMutate: () => {
      showLogs('Opportunity Embeddings', ['Starting opportunity embedding backfill'])
    },
    onSuccess: (result) => {
      replaceLogs('Opportunity Embeddings', result.logs, 'Opportunity embedding backfill completed')
      toast.success(
        `Opportunity embeddings updated: processed ${result.processed}, failed ${result.failed}, remaining ${result.remaining}`
      )
      clearCaches()
    },
    onError: (error) => {
      appendLogLine('Opportunity Embeddings', `Run failed: ${getErrorMessage(error)}`)
      toast.error('Failed to generate opportunity embeddings')
    },
  })

  const backfillNewsEmbeddingsMutation = useMutation({
    mutationFn: () =>
      streamBackfillNewsEmbeddings({
        batch_size: 16,
        run_until_empty: true,
      }, {
        onLog: (line) => appendLogLine('News Embeddings', line),
      }),
    onMutate: () => {
      showLogs('News Embeddings', ['Starting news embedding backfill'])
    },
    onSuccess: (result) => {
      replaceLogs('News Embeddings', result.logs, 'News embedding backfill completed')
      toast.success(
        `News embeddings updated: processed ${result.processed}, failed ${result.failed}, remaining ${result.remaining}`
      )
      clearCaches()
    },
    onError: (error) => {
      appendLogLine('News Embeddings', `Run failed: ${getErrorMessage(error)}`)
      toast.error('Failed to generate news embeddings')
    },
  })

  const backfillNewsTopicsMutation = useMutation({
    mutationFn: () =>
      streamBackfillNewsTopics({
        batch_size: 32,
        run_until_empty: true,
        overwrite_existing: false,
      }, {
        onLog: (line) => appendLogLine('News Topics', line),
      }),
    onMutate: () => {
      showLogs('News Topics', ['Starting news topic backfill'])
    },
    onSuccess: (result) => {
      replaceLogs('News Topics', result.logs, 'News topic backfill completed')
      toast.success(
        `News topics updated: processed ${result.processed}, failed ${result.failed}, remaining ${result.remaining}`
      )
      clearCaches()
    },
    onError: (error) => {
      appendLogLine('News Topics', `Run failed: ${getErrorMessage(error)}`)
      toast.error('Failed to populate news topics')
    },
  })

  const cleanupMutation = useMutation({
    mutationFn: () =>
      cleanupExpiredOpportunities({
        news_keep_days: newsKeepDays,
      }),
    onSuccess: (result) => {
      toast.success(
        `Deleted ${result.opportunity_deleted ?? 0} expired opportunities and ${result.news_deleted ?? 0} old news rows`
      )
      clearCaches()
    },
    onError: () => {
      toast.error('Failed to remove expired rows')
    },
  })

  if (!user?.is_admin) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Admin Access Required</CardTitle>
            <CardDescription>You must be an admin user to access scraper controls.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <div className="space-y-1">
        <h1 className="text-4xl font-semibold tracking-tight flex items-center gap-2">
          <Shield className="h-7 w-7 text-primary" />
          Admin Console
        </h1>
        <p className="text-muted-foreground text-sm">
          Run and monitor ingestion scrapers.
        </p>
      </div>

      {adminLogs && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Live Backend Logs
            </CardTitle>
            <CardDescription>Real-time output from ongoing jobs.</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              ref={logContainerRef}
              className="max-h-80 overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-5 whitespace-pre-wrap"
              aria-live="polite"
            >
              {adminLogs.lines.map((line, index) => (
                <div key={`${index}-${line}`}>{line}</div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Available Scrapers</CardTitle>
          <CardDescription>Select one or more sources and run ingestion directly.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-medium cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelected(availableScrapers)
                    } else {
                      setSelected([])
                    }
                  }}
                  className="h-4 w-4"
                />
                Select all
              </label>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {availableScrapers.map((scraper) => {
                const checked = selected.includes(scraper)
                return (
                  <label
                    key={scraper}
                    className="flex items-center gap-2 rounded-md border border-border bg-card/30 px-3 py-3 text-sm cursor-pointer select-none transition-colors hover:bg-accent/40"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      className="h-4 w-4"
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelected((prev) => [...prev, scraper])
                        } else {
                          setSelected((prev) => prev.filter((x) => x !== scraper))
                        }
                      }}
                    />
                    <span className="font-medium">{formatType(scraper)}</span>
                  </label>
                )
                })}
              </div>
            </div>
          )}

          <Button
            className="w-full h-10 text-sm"
            onClick={() => runMutation.mutate(selected)}
            disabled={runMutation.isPending || !selectedCount}
          >
            <Play className="h-4 w-4" />
            {runMutation.isPending ? 'Running Scrapers...' : 'Run Selected Scrapers'}
          </Button>

          {runMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>Scraped: {runMutation.data.total_scraped}</p>
              <p>Saved: {runMutation.data.total_saved}</p>
              {Object.entries(runMutation.data.by_source).map(([source, count]) => (
                <p key={source} className="text-xs text-muted-foreground">
                  {source}: {count}
                </p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Newspaper className="h-4 w-4" />
            Run News Scrapers
          </CardTitle>
          <CardDescription>
            Run all configured news scrapers from Admin.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            className="w-full"
            onClick={() => runNewsScrapeMutation.mutate()}
            disabled={runNewsScrapeMutation.isPending}
          >
            {runNewsScrapeMutation.isPending ? 'Running...' : 'Run News Scrapers'}
          </Button>

          {runNewsScrapeMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>Scraped: {runNewsScrapeMutation.data.total_scraped}</p>
              <p>Saved: {runNewsScrapeMutation.data.total_saved}</p>
              {Object.entries(runNewsScrapeMutation.data.by_source).map(([source, count]) => (
                <p key={source} className="text-xs text-muted-foreground">
                  {source}: {count}
                </p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Embedding Backfill
          </CardTitle>
          <CardDescription>
            Backfill embedding vectors for opportunites & news articles.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Button
              onClick={() => backfillOpportunityEmbeddingsMutation.mutate()}
              disabled={
                backfillOpportunityEmbeddingsMutation.isPending ||
                backfillNewsEmbeddingsMutation.isPending ||
                backfillNewsTopicsMutation.isPending
              }
            >
              {backfillOpportunityEmbeddingsMutation.isPending
                ? 'Filling Opportunities Embeddings...'
                : 'Fill Opportunities Embeddings'}
            </Button>

            <Button
              onClick={() => backfillNewsTopicsMutation.mutate()}
              disabled={
                backfillNewsTopicsMutation.isPending
                || backfillOpportunityEmbeddingsMutation.isPending
                || backfillNewsEmbeddingsMutation.isPending
              }
            >
              <Tags className="h-4 w-4" />
              {backfillNewsTopicsMutation.isPending
                ? 'Filling News Topics...'
                : 'Fill News Topics'}
            </Button>

            <Button
              onClick={() => backfillNewsEmbeddingsMutation.mutate()}
              disabled={
                backfillNewsEmbeddingsMutation.isPending ||
                backfillOpportunityEmbeddingsMutation.isPending ||
                backfillNewsTopicsMutation.isPending
              }
            >
              {backfillNewsEmbeddingsMutation.isPending
                ? 'Filling News Embeddings...'
                : 'Fill News Embeddings'}
            </Button>
          </div>

          {backfillOpportunityEmbeddingsMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>Opportunities processed: {backfillOpportunityEmbeddingsMutation.data.processed}</p>
              <p>Failed: {backfillOpportunityEmbeddingsMutation.data.failed}</p>
              <p>Remaining: {backfillOpportunityEmbeddingsMutation.data.remaining}</p>
            </div>
          )}

          {backfillNewsEmbeddingsMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>News processed: {backfillNewsEmbeddingsMutation.data.processed}</p>
              <p>Failed: {backfillNewsEmbeddingsMutation.data.failed}</p>
              <p>Remaining: {backfillNewsEmbeddingsMutation.data.remaining}</p>
            </div>
          )}

          {backfillNewsTopicsMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>News topics processed: {backfillNewsTopicsMutation.data.processed}</p>
              <p>Failed: {backfillNewsTopicsMutation.data.failed}</p>
              <p>Remaining needing topics: {backfillNewsTopicsMutation.data.remaining}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trash2 className="h-4 w-4" />
            Cleanup Expired Data
          </CardTitle>
          <CardDescription>
            Removes opportunities whose deadlines passed and news rows older than 3 days.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-xs space-y-1">
            <label className="text-xs text-muted-foreground">Delete news older than (days)</label>
            <Input
              type="number"
              min={1}
              max={30}
              value={newsKeepDays}
              onChange={(e) => setNewsKeepDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
            />
          </div>
          <div className="flex justify-center">
            <Button
              variant="destructive"
              onClick={() => {
                const confirmed = window.confirm(
                  `Delete all expired opportunities and news rows older than ${newsKeepDays} day(s)? This cannot be undone.`
                )
                if (!confirmed) return
                cleanupMutation.mutate()
              }}
              disabled={cleanupMutation.isPending}
            >
              {cleanupMutation.isPending ? 'Deleting...' : 'Delete Expired Rows'}
            </Button>
          </div>

          {cleanupMutation.data && (
            <div className="rounded-md border border-border p-3 text-sm space-y-1">
              <p>Matched total: {cleanupMutation.data.matched}</p>
              <p>Deleted total: {cleanupMutation.data.deleted}</p>
              <p>Expired opportunities deleted: {cleanupMutation.data.opportunity_deleted ?? 0}</p>
              <p>
                Old news rows deleted (older than {cleanupMutation.data.news_keep_days ?? 3} days):{' '}
                {cleanupMutation.data.news_deleted ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Executed at {cleanupMutation.data.now_utc}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
