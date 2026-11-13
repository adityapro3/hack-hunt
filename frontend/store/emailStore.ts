import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ColdEmailDraft } from '@/lib/types'

interface EmailState {
  drafts: ColdEmailDraft[]
  isGenerating: boolean
  progressMessage: string | null
  setGenerating: (isGenerating: boolean) => void
  setProgressMessage: (message: string | null) => void
  prependDraft: (draft: ColdEmailDraft) => void
  setDrafts: (drafts: ColdEmailDraft[]) => void
  clearSessionRun: () => void
}

export const useEmailStore = create<EmailState>()(
  persist(
    (set) => ({
      drafts: [],
      isGenerating: false,
      progressMessage: null,
      setGenerating: (isGenerating) => set({ isGenerating }),
      setProgressMessage: (message) => set({ progressMessage: message }),
      prependDraft: (draft) =>
        set((state) => ({
          drafts: [draft, ...state.drafts.filter((item) => item.id !== draft.id)].slice(0, 100),
        })),
      setDrafts: (drafts) => set({ drafts }),
      clearSessionRun: () => set({ isGenerating: false, progressMessage: null }),
    }),
    {
      name: 'hack-hunt-cold-email',
      partialize: (state) => ({
        drafts: state.drafts,
      }),
    }
  )
)
