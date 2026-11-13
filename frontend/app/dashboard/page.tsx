'use client'

import { useQuery } from '@tanstack/react-query'
import { getOpportunities, getApplications } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatDeadline, formatType, getTypeColor, isDeadlineSoon } from '@/lib/utils'
import { Code2, ClipboardList, TrendingUp, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function DashboardPage() {
  const { data: all = [], isLoading: loadingAll } = useQuery({
    queryKey: ['opportunities', 'dashboard'],
    queryFn: () => getOpportunities({ limit: 500 }),
    staleTime: 60_000,
  })

  const { data: applications = [], isLoading: loadingApps } = useQuery({
    queryKey: ['applications'],
    queryFn: () => getApplications(),
    staleTime: 30_000,
  })

  const hackathons = all.filter((o) => o.opportunity_type === 'hackathon')
  const active = all.filter((o) => o.status === 'active')
  const upcoming = all
    .filter((o) => o.deadline && isDeadlineSoon(o.deadline, 7))
    .sort((a, b) => new Date(a.deadline!).getTime() - new Date(b.deadline!).getTime())
    .slice(0, 8)
  const recent = [...all]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 10)

  const isLoading = loadingAll || loadingApps

  const stats = [
    {
      label: 'Total Opportunities',
      value: all.length,
      sub: `${active.length} active`,
      icon: TrendingUp,
      color: 'text-primary',
    },
    {
      label: 'Hackathons',
      value: hackathons.length,
      sub: `${hackathons.filter((o) => o.status === 'active').length} active`,
      icon: Code2,
      color: 'text-violet-400',
    },
    {
      label: 'Tracked',
      value: applications.length,
      sub: `${applications.filter((a) => a.status === 'applied').length} applied`,
      icon: ClipboardList,
      color: 'text-blue-400',
    },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Overview of your opportunities</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              {isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-7 w-16" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ) : (
                <>
                  <div className={cn('flex items-center gap-2 mb-1', stat.color)}>
                    <stat.icon className="h-4 w-4" />
                    <span className="text-2xl font-bold text-foreground">{stat.value}</span>
                  </div>
                  <p className="text-xs font-medium text-muted-foreground">{stat.label}</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-0.5">{stat.sub}</p>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Deadlines */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="h-4 w-4 text-yellow-400" />
              Deadlines in Next 7 Days
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="px-5 pb-5 space-y-2">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : upcoming.length === 0 ? (
              <p className="px-5 pb-5 text-sm text-muted-foreground">No upcoming deadlines</p>
            ) : (
              <div className="divide-y divide-border">
                {upcoming.map((o) => (
                  <div key={o.id} className="px-5 py-3 flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{o.title}</p>
                      <p className="text-xs text-muted-foreground">{o.source}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium', getTypeColor(o.opportunity_type))}>
                        {formatType(o.opportunity_type)}
                      </span>
                      <span className="text-xs text-yellow-400 font-medium whitespace-nowrap">
                        {formatDeadline(o.deadline).split('·')[1]?.trim() || formatDeadline(o.deadline)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Additions */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              Recently Added
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="px-5 pb-5 space-y-2">
                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : recent.length === 0 ? (
              <p className="px-5 pb-5 text-sm text-muted-foreground">No opportunities yet</p>
            ) : (
              <div className="divide-y divide-border">
                {recent.map((o) => (
                  <div key={o.id} className="px-5 py-3 flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{o.title}</p>
                      <p className="text-xs text-muted-foreground">{o.source}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium', getTypeColor(o.opportunity_type))}>
                        {formatType(o.opportunity_type)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(o.created_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Application Status Breakdown */}
      {applications.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-blue-400" />
              Application Tracker Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {(['interested', 'applied', 'in_progress', 'accepted', 'rejected'] as const).map((status) => {
                const count = applications.filter((a) => a.status === status).length
                if (!count) return null
                return (
                  <div key={status} className="flex items-center gap-2">
                    <Badge variant="outline" className="capitalize">
                      {status.replace('_', ' ')}: {count}
                    </Badge>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
