'use client'

import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  totalItems: number
  pageSize: number
}

export default function Pagination({ page, totalPages, onPageChange, totalItems, pageSize }: PaginationProps) {
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalItems)

  if (totalItems === 0) return null

  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {start}–{end} of {totalItems}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="px-2 text-xs">
          {page} / {totalPages}
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
