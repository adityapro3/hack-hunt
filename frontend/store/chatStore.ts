import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatMessage, ChatProvider } from '@/lib/types'

interface ChatState {
  messages: ChatMessage[]
  resumeText: string | null
  resumeName: string | null
  selectedProvider: ChatProvider | null
  selectedModel: string | null
  selectedThreadId: string | null
  addMessage: (msg: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  clearMessages: () => void
  setResume: (text: string, name: string) => void
  clearResume: () => void
  setModelSelection: (provider: ChatProvider, model: string) => void
  setSelectedThreadId: (threadId: string | null) => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      resumeText: null,
      resumeName: null,
      selectedProvider: null,
      selectedModel: null,
      selectedThreadId: null,
      addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
      setMessages: (messages) => set({ messages }),
      clearMessages: () => set({ messages: [] }),
      setResume: (text, name) => set({ resumeText: text, resumeName: name }),
      clearResume: () => set({ resumeText: null, resumeName: null }),
      setModelSelection: (provider, model) =>
        set({ selectedProvider: provider, selectedModel: model }),
      setSelectedThreadId: (threadId) => set({ selectedThreadId: threadId }),
    }),
    {
      name: 'hack-hunt-chat',
      partialize: (state) => ({
        messages: state.messages.slice(-50), // keep last 50 messages
        resumeText: state.resumeText,
        resumeName: state.resumeName,
        selectedProvider: state.selectedProvider,
        selectedModel: state.selectedModel,
        selectedThreadId: state.selectedThreadId,
      }),
    }
  )
)
