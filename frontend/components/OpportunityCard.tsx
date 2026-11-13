'use client'

import { useState } from 'react'
import { ExternalLink, Bookmark, BookmarkCheck, ClipboardList, CheckCircle2, Calendar, MapPin, Trophy, Users } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn, formatDeadline, formatDate, formatApplicationStatus, formatType, getTypeColor, getTypeAccent, getOpportunityStatusColor, isDeadlineSoon, isDeadlinePast } from '@/lib/utils'
import { createBookmark, deleteBookmark, createApplication } from '@/lib/api'
import { groupDomainValues } from '@/lib/domainGroups'
import type { Opportunity } from '@/lib/types'

interface OpportunityCardProps {
  opportunity: Opportunity
  bookmarkId?: string   // set if already bookmarked
  applicationId?: string // set if already tracked
  applicationStatus?: string
}

export default function OpportunityCard({
  opportunity,
  bookmarkId,
  applicationId,
  applicationStatus,
}: OpportunityCardProps) {
  const qc = useQueryClient()
  const [localBookmarkId, setLocalBookmarkId] = useState(bookmarkId)
  const [localAppId, setLocalAppId] = useState(applicationId)
  const [localAppStatus, setLocalAppStatus] = useState(applicationStatus)

  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      if (localBookmarkId) {
        await deleteBookmark(localBookmarkId)
        return null
      } else {
        return await createBookmark({ opportunity_id: opportunity.id })
      }
    },
    onSuccess: (result) => {
      if (result) {
        setLocalBookmarkId(result.id)
        toast.success('Bookmarked!')
      } else {
        setLocalBookmarkId(undefined)
        toast.success('Bookmark removed')
      }
      qc.invalidateQueries({ queryKey: ['bookmarks'] })
    },
    onError: () => toast.error('Failed to update bookmark'),
  })

  const trackMutation = useMutation({
    mutationFn: () =>
      createApplication({ opportunity_id: opportunity.id, status: 'interested' }),
    onSuccess: (result) => {
      setLocalAppId(result.id)
      setLocalAppStatus(result.status)
      toast.success('Added to tracker!')
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
    onError: () => toast.error('Failed to track'),
  })

  const appliedMutation = useMutation({
    mutationFn: () =>
      createApplication({ opportunity_id: opportunity.id, status: 'applied' }),
    onSuccess: (result) => {
      setLocalAppId(result.id)
      setLocalAppStatus(result.status)
      toast.success('Marked as applied!')
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
    onError: () => toast.error('Failed to update'),
  })

  const isClosed = isDeadlinePast(opportunity.deadline)
  const isSoon = isDeadlineSoon(opportunity.deadline)
  const groupedDomains = groupDomainValues(opportunity.domains)

  return (
    <div
      className={cn(
        'group relative flex flex-col rounded-lg border border-border bg-card transition-all hover:border-border/80 hover:shadow-lg hover:shadow-black/20 border-l-4',
        getTypeAccent(opportunity.opportunity_type),
        isClosed && 'opacity-60'
      )}
    >
      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap gap-1.5 mb-2">
              <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', getTypeColor(opportunity.opportunity_type))}>
                {formatType(opportunity.opportunity_type)}
              </span>
              <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', getOpportunityStatusColor(opportunity.status))}>
                {formatType(opportunity.status)}
              </span>
              {localAppStatus && (
                <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium bg-blue-500/15 text-blue-400 border-blue-500/30">
                  {formatApplicationStatus(localAppStatus)}
                </span>
              )}
              {isSoon && !isClosed && (
                <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium bg-yellow-500/15 text-yellow-400 border-yellow-500/30">
                  deadline soon
                </span>
              )}
            </div>
            <h3 className="font-semibold text-sm leading-snug text-foreground line-clamp-2">
              {opportunity.title}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">{opportunity.source}</p>
          </div>
        </div>

        {/* Description */}
        {opportunity.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
            {opportunity.description}
          </p>
        )}

        {/* Metrics */}
        <div className="space-y-1.5 text-xs text-muted-foreground">
          {opportunity.deadline && (
            <div className={cn('flex items-center gap-1.5', isSoon && !isClosed && 'text-yellow-400')}>
              <Calendar className="h-3 w-3" />
              {formatDeadline(opportunity.deadline)}
            </div>
          )}
          {opportunity.location && (
            <div className="flex items-center gap-1.5">
              <MapPin className="h-3 w-3" />
              {opportunity.location}
            </div>
          )}
          {opportunity.prize_money && (
            <div className="flex items-center gap-1.5">
              <Trophy className="h-3 w-3" />
              {opportunity.prize_money}
            </div>
          )}
          {opportunity.team_size && (
            <div className="flex items-center gap-1.5">
              <Users className="h-3 w-3" />
              {opportunity.team_size}
            </div>
          )}
          {opportunity.mode && (
            <div>
              <Badge variant="muted" className="text-[10px] py-0">
                {opportunity.mode}
              </Badge>
            </div>
          )}
        </div>

        {/* Tags */}
        {(groupedDomains.length > 0 || opportunity.skills.length > 0) && (
          <div className="flex flex-wrap gap-1">
            {groupedDomains.slice(0, 3).map((d) => (
              <span key={d} className="inline-flex items-center rounded-sm bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {d}
              </span>
            ))}
            {opportunity.skills.slice(0, 3).map((s) => (
              <span key={s} className="inline-flex items-center rounded-sm bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {s}
              </span>
            ))}
            {groupedDomains.length + opportunity.skills.length > 6 && (
              <span className="inline-flex items-center rounded-sm bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                +{groupedDomains.length + opportunity.skills.length - 6}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 pb-3 flex items-center gap-1.5 border-t border-border/50 pt-3">
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn(localBookmarkId ? 'text-primary' : 'text-muted-foreground')}
          onClick={() => bookmarkMutation.mutate()}
          disabled={bookmarkMutation.isPending}
          title={localBookmarkId ? 'Remove bookmark' : 'Bookmark'}
        >
          {localBookmarkId ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
        </Button>

        {!localAppId && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground h-7"
            onClick={() => trackMutation.mutate()}
            disabled={trackMutation.isPending}
          >
            <ClipboardList className="h-3 w-3" />
            Track
          </Button>
        )}

        {(!localAppStatus || localAppStatus === 'interested') && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground h-7"
            onClick={() => appliedMutation.mutate()}
            disabled={appliedMutation.isPending}
          >
            <CheckCircle2 className="h-3 w-3" />
            Applied
          </Button>
        )}

        <div className="flex-1" />

        <a href={opportunity.url} target="_blank" rel="noopener noreferrer">
          <Button variant="outline" size="sm" className="text-xs h-7">
            <ExternalLink className="h-3 w-3" />
            View
          </Button>
        </a>
      </div>
    </div>
  )
}
