'use client'

import { useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Bot, ExternalLink, Newspaper, Search, Send, User, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { toast } from 'sonner'
import { getNewsArticles, getNewsFilters, streamNewsChatMessage } from '@/lib/api'
import { formatDate, formatType } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const DEFAULT_BATCH_SIZE = 20
const FILTER_BATCH_SIZE = 30

export default function NewsPage() {
  const [searchDraft, setSearchDraft] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [topicFilter, setTopicFilter] = useState<string | undefined>(undefined)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [isStreaming, setIsStreaming] = useState(false)

  const hasActiveFilters = Boolean(searchTerm || topicFilter)
  const currentLimit = hasActiveFilters ? FILTER_BATCH_SIZE : DEFAULT_BATCH_SIZE

  const { data: newsFilters } = useQuery({
    queryKey: ['news-filters'],
    queryFn: getNewsFilters,
    staleTime: 60_000,
  })

  const {
    data: pagedNews,
    isLoading: newsLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    queryKey: ['news-feed', searchTerm, topicFilter || '__all__', currentLimit],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      getNewsArticles({
        topic: topicFilter,
        q: searchTerm || undefined,
        semantic: searchTerm ? true : undefined,
        limit: currentLimit,
        offset: hasActiveFilters ? 0 : Number(pageParam || 0),
      }),
    getNextPageParam: (lastPage, allPages) => {
      if (hasActiveFilters) {
        return undefined
      }
      const loaded = allPages.reduce((sum, page) => sum + (page.items?.length || 0), 0)
      return loaded < (lastPage.total_count || 0) ? loaded : undefined
    },
    staleTime: 20_000,
  })

  const articles = useMemo(
    () => (pagedNews?.pages || []).flatMap((page) => page.items || []),
    [pagedNews]
  )

  const totalCount = pagedNews?.pages?.[0]?.total_count || 0

  function applySearch() {
    setSearchTerm(searchDraft.trim())
  }

  function clearFilters() {
    setSearchDraft('')
    setSearchTerm('')
    setTopicFilter(undefined)
  }

  async function handleSendNewsChat() {
    const message = chatInput.trim()
    if (!message || isStreaming) {
      return
    }

    setChatMessages((prev) => [...prev, { role: 'user', content: message }])
    setChatInput('')
    setIsStreaming(true)

    // Add initial placeholder for assistant
    setChatMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      await streamNewsChatMessage(
        { message },
        {
          onDelta: (delta) => {
            setChatMessages((prev) => {
              const last = prev[prev.length - 1]
              if (last && last.role === 'assistant') {
                return [...prev.slice(0, -1), { role: 'assistant', content: last.content + delta }]
              }
              return prev
            })
          },
          onDone: () => {
            setIsStreaming(false)
          },
        }
      )
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'ScrollAI stream failed'
      toast.error(detail)
      setChatMessages((prev) => {
        const last = prev[prev.length - 1]
        if (last && last.role === 'assistant' && !last.content) {
          return [...prev.slice(0, -1), { role: 'assistant', content: 'I could not process this right now. Please try again.' }]
        }
        return prev
      })
      setIsStreaming(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Newspaper className="h-7 w-7 text-primary" />
          News Radar
        </h1>
        <p className="text-sm text-muted-foreground">
          Ask about headlines, policy shifts, markets, and global developments in one place.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            ScrollAI
          </CardTitle>
          <CardDescription>
            Ask what you want to read, and ScrollAI will answer your query.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-md border border-border/80 bg-card/40 p-3 max-h-96 overflow-auto space-y-3">
            {chatMessages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Try: "Give me today&apos;s biggest headlines" or "Summarize tech and policy updates"
              </p>
            ) : (
              chatMessages.map((message, index) => (
                <div key={`${index}-${message.role}`} className="space-y-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                    {message.role === 'user' ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                    {message.role === 'user' ? 'You' : 'ScrollAI'}
                  </p>
                  {message.role === 'assistant' ? (
                    <div className="text-sm leading-relaxed space-y-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_p]:whitespace-pre-wrap [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:leading-relaxed [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  )}
                </div>
              ))
            )}
            {isStreaming && chatMessages[chatMessages.length - 1]?.content === '' && (
              <p className="text-sm text-muted-foreground">Thinking...</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Input
              placeholder="Ask ScrollAI what news you want to read..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void handleSendNewsChat()
                }
              }}
            />
            <Button onClick={() => void handleSendNewsChat()} disabled={isStreaming || !chatInput.trim()}>
              <Send className="h-4 w-4" />
              Send
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
          <div className="space-y-1">
            <CardTitle>News Feed</CardTitle>
            <CardDescription>
              {hasActiveFilters
                ? 'Showing top filtered results. Clear filters to continue browsing with Load More.'
                : 'Browse among available articles.'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <div className="md:col-span-3 flex gap-2">
              <Input
                placeholder="Search across all articles..."
                value={searchDraft}
                onChange={(e) => setSearchDraft(e.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    applySearch()
                  }
                }}
              />
              <Button onClick={applySearch}>
                <Search className="h-4 w-4" />
                Search
              </Button>
            </div>

            <Select
              value={topicFilter || '__all__'}
              onValueChange={(value) => setTopicFilter(value === '__all__' ? undefined : value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="All Topics" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Topics</SelectItem>
                {(newsFilters?.topics || []).map((topic) => (
                  <SelectItem key={topic} value={topic}>
                    {formatType(topic)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {hasActiveFilters && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                {searchTerm
                  ? `Semantic matches for "${searchTerm}"`
                  : 'Filtered results'}
                {' · '}showing {articles.length} of {totalCount}
              </p>
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-3.5 w-3.5" />
                Clear Filters
              </Button>
            </div>
          )}

          {newsLoading ? (
            <p className="text-sm text-muted-foreground">Loading news...</p>
          ) : articles.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent articles available yet.</p>
          ) : (
            articles.map((item) => (
              <article key={item.id} className="rounded-md border border-border p-4 space-y-2 bg-card/40">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="text-base font-semibold leading-snug max-w-4xl">
                    {item.title}
                  </h3>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
                  >
                    Open source
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{formatType(item.source)}</Badge>
                  <Badge variant="outline">{formatType(item.topic || 'general')}</Badge>
                  <Badge variant="outline">Published: {formatDate(item.published_at || undefined)}</Badge>
                </div>

                <p className="text-sm text-muted-foreground leading-relaxed">
                  {(item.content || '').slice(0, 650)}
                  {(item.content || '').length > 650 ? '...' : ''}
                </p>
              </article>
            ))
          )}

          {!hasActiveFilters && hasNextPage && (
            <div className="pt-2 flex justify-center">
              <Button
                variant="outline"
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? 'Loading more...' : 'Load More'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
