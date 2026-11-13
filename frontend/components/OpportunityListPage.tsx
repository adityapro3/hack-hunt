'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getOpportunities, getOpportunityFilters, getBookmarks, getApplications } from '@/lib/api'
import OpportunityCard from '@/components/OpportunityCard'
import OpportunityFilters from '@/components/OpportunityFilters'
import Pagination from '@/components/Pagination'
import { Skeleton } from '@/components/ui/skeleton'
import { paginate, totalPages } from '@/lib/utils'
import { opportunityMatchesDomainGroup } from '@/lib/domainGroups'
import type { OpportunityType, OpportunityQueryParams } from '@/lib/types'
import { SlidersHorizontal } from 'lucide-react'

const PAGE_SIZE = 24

interface OpportunityListPageProps {
  type: OpportunityType
  title: string
  description: string
}

export default function OpportunityListPage({ type, title, description }: OpportunityListPageProps) {
  const [page, setPage] = useState(1)
  const [filterParams, setFilterParams] = useState<Omit<OpportunityQueryParams, 'type' | 'limit'>>({
    sort: 'deadline',
  })

  const queryParams: OpportunityQueryParams = {
    ...filterParams,
    domain: undefined,
    type,
    limit: 500,
  }

  const { data: opportunities = [], isLoading } = useQuery({
    queryKey: ['opportunities', queryParams],
    queryFn: () => getOpportunities(queryParams),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })

  const { data: filters } = useQuery({
    queryKey: ['filters', type],
    queryFn: () => getOpportunityFilters(type),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  })

  const { data: bookmarks = [] } = useQuery({
    queryKey: ['bookmarks'],
    queryFn: () => getBookmarks(),
    staleTime: 30_000,
  })

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => getApplications(),
    staleTime: 30_000,
  })

  // Build lookup maps for O(1) card state
  const bookmarkMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const b of bookmarks) map.set(b.opportunity_id, b.id)
    return map
  }, [bookmarks])

  const applicationMap = useMemo(() => {
    const map = new Map<string, { id: string; status: string }>()
    for (const a of applications) map.set(a.opportunity_id, { id: a.id, status: a.status })
    return map
  }, [applications])

  const visibleOpportunities = useMemo(() => {
    return opportunities.filter((opp) => opportunityMatchesDomainGroup(opp, filterParams.domain))
  }, [opportunities, filterParams.domain])

  function handleFilterChange(updates: Partial<OpportunityQueryParams>) {
    setPage(1)
    setFilterParams((prev) => ({ ...prev, ...updates }))
  }

  const numPages = totalPages(visibleOpportunities.length, PAGE_SIZE)
  const pageItems = paginate(visibleOpportunities, page, PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-muted-foreground text-sm mt-1">{description}</p>
        </div>
        {!isLoading && (
          <span className="text-sm text-muted-foreground mt-1 flex-shrink-0">
            {visibleOpportunities.length} results
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        <OpportunityFilters
          filters={filters}
          params={filterParams}
          onChange={handleFilterChange}
          hideType
        />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(9)].map((_, i) => (
            <Skeleton key={i} className="h-64 w-full rounded-lg" />
          ))}
        </div>
      ) : visibleOpportunities.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-muted-foreground">No {type}s found matching your filters.</p>
          <p className="text-sm text-muted-foreground/60 mt-1">Try adjusting or clearing your filters.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {pageItems.map((opp) => {
              const bm = bookmarkMap.get(opp.id)
              const app = applicationMap.get(opp.id)
              return (
                <OpportunityCard
                  key={opp.id}
                  opportunity={opp}
                  bookmarkId={bm}
                  applicationId={app?.id}
                  applicationStatus={app?.status}
                />
              )
            })}
          </div>

          <Pagination
            page={page}
            totalPages={numPages}
            onPageChange={setPage}
            totalItems={visibleOpportunities.length}
            pageSize={PAGE_SIZE}
          />
        </>
      )}
    </div>
  )
}
