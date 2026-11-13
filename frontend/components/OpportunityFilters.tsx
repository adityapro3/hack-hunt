'use client'

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'
import { formatType } from '@/lib/utils'
import { groupDomainValues } from '@/lib/domainGroups'
import type { OpportunityFilters, OpportunityQueryParams } from '@/lib/types'

interface OpportunityFiltersProps {
  filters: OpportunityFilters | undefined
  params: OpportunityQueryParams
  onChange: (updates: Partial<OpportunityQueryParams>) => void
  hideMode?: boolean
  hideType?: boolean
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  formatOption,
}: {
  label: string
  value: string | undefined
  options: string[]
  onChange: (val: string | undefined) => void
  formatOption?: (option: string) => string
}) {
  const allLabel = label === 'Status' ? 'Statuses' : `${label}s`
  const normalizedAll = `all ${allLabel.toLowerCase()}`
  const safeOptions = Array.from(
    new Set(
      options
        .map((opt) => opt.trim())
        .filter((opt) => opt.length > 0)
        .filter((opt) => opt.toLowerCase() !== normalizedAll)
    )
  )

  return (
    <Select
      value={value || '__all__'}
      onValueChange={(v: string) => onChange(v === '__all__' ? undefined : v)}
    >
      <SelectTrigger className="h-8 text-xs min-w-[120px]">
        <SelectValue placeholder={`All ${allLabel}`} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all__">All {allLabel}</SelectItem>
        {safeOptions.map((opt) => (
          <SelectItem key={opt} value={opt}>
            {formatOption ? formatOption(opt) : opt}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default function OpportunityFilters({
  filters,
  params,
  onChange,
  hideMode = false,
  hideType = false,
}: OpportunityFiltersProps) {
  const groupedDomainOptions = filters ? groupDomainValues(filters.domains) : []
  const hasActiveFilters = params.domain || params.skill || params.source || params.status || params.mode

  function clearAll() {
    onChange({
      domain: undefined,
      skill: undefined,
      source: undefined,
      status: undefined,
      mode: undefined,
    })
  }

  return (
    <div className="w-full space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 w-full">
        {!hideType && filters && (
          <FilterSelect
            label="Type"
            value={params.type}
            options={filters.types}
            onChange={(v) => onChange({ type: v as OpportunityQueryParams['type'] })}
            formatOption={formatType}
          />
        )}

        {filters && (
          <>
            <FilterSelect
              label="Domain"
              value={params.domain}
              options={groupedDomainOptions}
              onChange={(v) => onChange({ domain: v })}
            />
            <FilterSelect
              label="Skill"
              value={params.skill}
              options={filters.skills}
              onChange={(v) => onChange({ skill: v })}
            />
            <FilterSelect
              label="Source"
              value={params.source}
              options={filters.sources}
              onChange={(v) => onChange({ source: v })}
            />
            <FilterSelect
              label="Status"
              value={params.status}
              options={filters.statuses}
              onChange={(v) => onChange({ status: v })}
              formatOption={formatType}
            />
            {!hideMode && (
              <FilterSelect
                label="Mode"
                value={params.mode}
                options={filters.modes}
                onChange={(v) => onChange({ mode: v })}
              />
            )}
          </>
        )}

        <Select
          value={params.sort || 'deadline'}
          onValueChange={(v: string) => onChange({ sort: v as 'deadline' | 'created_at' })}
        >
          <SelectTrigger className="h-8 text-xs min-w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="deadline">Sort: Deadline</SelectItem>
            <SelectItem value="created_at">Sort: Newest</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {hasActiveFilters && (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={clearAll}>
            <X className="h-3 w-3" />
            Clear
          </Button>
        </div>
      )}
    </div>
  )
}
