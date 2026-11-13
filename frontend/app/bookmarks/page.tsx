'use client'

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getBookmarks, deleteBookmark } from '@/lib/api'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Bookmark, ExternalLink, Trash2, Calendar, Trophy } from 'lucide-react'
import { toast } from 'sonner'
import { cn, formatDeadline, formatType, getTypeColor, getTypeAccent } from '@/lib/utils'
import type { OpportunityType } from '@/lib/types'

const TABS: { value: string; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'hackathon', label: 'Hackathons' },
]

export default function BookmarksPage() {
  const [activeTab, setActiveTab] = useState('all')
  const qc = useQueryClient()

  const { data: bookmarks = [], isLoading } = useQuery({
    queryKey: ['bookmarks'],
    queryFn: () => getBookmarks(),
    staleTime: 30_000,
  })

  const removeMutation = useMutation({
    mutationFn: deleteBookmark,
    onSuccess: () => {
      toast.success('Bookmark removed')
      qc.invalidateQueries({ queryKey: ['bookmarks'] })
    },
    onError: () => toast.error('Failed to remove bookmark'),
  })

  const filtered = useMemo(() => {
    if (activeTab === 'all') return bookmarks
    return bookmarks.filter((b) => b.opportunity.opportunity_type === activeTab)
  }, [bookmarks, activeTab])

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bookmark className="h-6 w-6 text-primary" />
            Bookmarks
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Your saved opportunities</p>
        </div>
        {!isLoading && (
          <span className="text-sm text-muted-foreground mt-1">{bookmarks.length} saved</span>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {TABS.map((tab) => {
            const count = tab.value === 'all'
              ? bookmarks.length
              : bookmarks.filter((b) => b.opportunity.opportunity_type === tab.value).length
            return (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
                {count > 0 && (
                  <span className="ml-1.5 text-[10px] bg-muted rounded px-1 py-0.5">{count}</span>
                )}
              </TabsTrigger>
            )
          })}
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Bookmark className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No bookmarks yet</p>
              <p className="text-sm text-muted-foreground/60 mt-1">
                Bookmark opportunities from the listings to save them here.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((bm) => {
                const opp = bm.opportunity
                return (
                  <div
                    key={bm.id}
                    className={cn(
                      'flex items-start gap-4 rounded-lg border border-border bg-card p-4 border-l-4',
                      getTypeAccent(opp.opportunity_type)
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap gap-1.5 mb-1.5">
                        <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', getTypeColor(opp.opportunity_type))}>
                          {formatType(opp.opportunity_type)}
                        </span>
                        <span className="text-xs text-muted-foreground">{opp.source}</span>
                      </div>
                      <h3 className="font-semibold text-sm">{opp.title}</h3>
                      {opp.description && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{opp.description}</p>
                      )}
                      <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                        {opp.deadline && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {formatDeadline(opp.deadline)}
                          </span>
                        )}
                        {opp.prize_money && (
                          <span className="flex items-center gap-1">
                            <Trophy className="h-3 w-3" />
                            {opp.prize_money}
                          </span>
                        )}
                      </div>
                      {bm.notes && (
                        <p className="mt-2 text-xs text-muted-foreground italic">&ldquo;{bm.notes}&rdquo;</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <a href={opp.url} target="_blank" rel="noopener noreferrer">
                        <Button variant="outline" size="icon-sm">
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      </a>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => removeMutation.mutate(bm.id)}
                        disabled={removeMutation.isPending}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
