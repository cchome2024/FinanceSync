import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ImportPreviewRecord = {
  id: string
  recordType: 'account_balance' | 'revenue' | 'expense' | 'income_forecast'
  payload: Record<string, unknown>
  confidence?: number
  warnings?: string[]
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
}

type FinanceState = {
  chatHistory: ChatMessage[]
  importPreview: ImportPreviewRecord[]
  isLoading: boolean
  setLoading: (value: boolean) => void
  setChatHistory: (messages: ChatMessage[]) => void
  setImportPreview: (records: ImportPreviewRecord[]) => void
  reset: () => void
}

const initialState: Pick<FinanceState, 'chatHistory' | 'importPreview' | 'isLoading'> = {
  chatHistory: [],
  importPreview: [],
  isLoading: false,
}

export const useFinanceStore = create<FinanceState>()(
  persist(
    (set) => ({
      ...initialState,
      setLoading: (value) => set({ isLoading: value }),
      setChatHistory: (messages) => set({ chatHistory: messages }),
      setImportPreview: (records) => set({ importPreview: records }),
      reset: () => set(initialState),
    }),
    {
      name: 'finance-sync-store',
      partialize: (state) => ({ chatHistory: state.chatHistory }),
    }
  )
)
