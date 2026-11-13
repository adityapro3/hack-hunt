'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApplications, updateApplication, deleteApplication } from '@/lib/api'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog'
import { ClipboardList, ExternalLink, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn, formatDate, formatType, getStatusColor, getTypeColor, formatApplicationStatus } from '@/lib/utils'
import type { Application, ApplicationStatus } from '@/lib/types'

const STATUS_TABS = [
  { value: 'all', label: 'All' },
  { value: 'interested', label: 'Interested' },
  { value: 'applied', label: 'Applied' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
]

const ALL_STATUSES: ApplicationStatus[] = [
  'interested', 'applied', 'in_progress', 'accepted', 'rejected',
]

interface EditState {
  app: Application
  status: ApplicationStatus
  notes: string
}

export default function TrackerPage() {
  const [activeTab, setActiveTab] = useState('all')
  const [editState, setEditState] = useState<EditState | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Application | null>(null)
  const qc = useQueryClient()

  const { data: applications = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => getApplications(),
    staleTime: 30_000,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { status: ApplicationStatus; notes: string } }) =>
      updateApplication(id, payload),
    onSuccess: () => {
      toast.success('Updated!')
      setEditState(null)
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
    onError: () => toast.error('Update failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteApplication,
    onSuccess: () => {
      toast.success('Removed from tracker')
      setDeleteTarget(null)
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
    onError: () => toast.error('Delete failed'),
  })

  const filtered =
    activeTab === 'all'
      ? applications
      : applications.filter((a) => a.status === activeTab)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-blue-400" />
            Application Tracker
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Track your application statuses</p>
        </div>
        {!isLoading && (
          <span className="text-sm text-muted-foreground mt-1">{applications.length} tracked</span>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex-wrap h-auto gap-1 p-1">
          {STATUS_TABS.map((tab) => {
            const count =
              tab.value === 'all'
                ? applications.length
                : applications.filter((a) => a.status === tab.value).length
            return (
              <TabsTrigger key={tab.value} value={tab.value} className="text-xs">
                {tab.label}
                {count > 0 && (
                  <span className="ml-1 text-[10px] bg-muted rounded px-1 py-0.5">{count}</span>
                )}
              </TabsTrigger>
            )
          })}
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <ClipboardList className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">Nothing here yet</p>
              <p className="text-sm text-muted-foreground/60 mt-1">
                Track applications from the listings pages.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Title</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden md:table-cell">Type</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden lg:table-cell">Source</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Status</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden sm:table-cell">Updated</th>
                    <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filtered.map((app) => (
                    <tr key={app.id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-sm line-clamp-1">{app.opportunity.title}</p>
                        {app.notes && (
                          <p className="text-xs text-muted-foreground italic mt-0.5 line-clamp-1">{app.notes}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', getTypeColor(app.opportunity.opportunity_type))}>
                          {formatType(app.opportunity.opportunity_type)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground hidden lg:table-cell">
                        {app.opportunity.source}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', getStatusColor(app.status))}>
                          {formatApplicationStatus(app.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground hidden sm:table-cell">
                        {formatDate(app.updated_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <a href={app.opportunity.url} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="icon-sm">
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Button>
                          </a>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() =>
                              setEditState({ app, status: app.status, notes: app.notes || '' })
                            }
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => setDeleteTarget(app)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Edit dialog */}
      <Dialog open={!!editState} onOpenChange={(open) => !open && setEditState(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Application</DialogTitle>
            <DialogDescription className="line-clamp-1">
              {editState?.app.opportunity.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <Select
                value={editState?.status}
                onValueChange={(v) =>
                  setEditState((s) => s ? { ...s, status: v as ApplicationStatus } : s)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {formatApplicationStatus(s)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Notes</label>
              <Textarea
                placeholder="Add personal notes..."
                value={editState?.notes || ''}
                onChange={(e) =>
                  setEditState((s) => s ? { ...s, notes: e.target.value } : s)
                }
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditState(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!editState) return
                updateMutation.mutate({
                  id: editState.app.id,
                  payload: { status: editState.status, notes: editState.notes },
                })
              }}
              disabled={updateMutation.isPending}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove from Tracker?</DialogTitle>
            <DialogDescription>
              &ldquo;{deleteTarget?.opportunity.title}&rdquo; will be removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
