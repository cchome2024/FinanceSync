import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ImportPreviewRecord = {
  id: string
  recordType:
    | 'account_balance'
    | 'revenue'
    | 'expense'
    | 'income_forecast'
    | 'expense_forecast'
    | 'revenue_forecast'
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
  importChat: ChatMessage[]
  analysisChat: ChatMessage[]
  importPreview: ImportPreviewRecord[]
  importLoading: boolean
  analysisLoading: boolean
  currentJobId: string | null
  setImportLoading: (value: boolean) => void
  setAnalysisLoading: (value: boolean) => void
  addImportMessage: (message: ChatMessage) => void
  addAnalysisMessage: (message: ChatMessage) => void
  setImportPreview: (records: ImportPreviewRecord[]) => void
  setCurrentJobId: (jobId: string | null) => void
  reset: () => void
}

const initialState: Pick<
  FinanceState,
  'importChat' | 'analysisChat' | 'importPreview' | 'importLoading' | 'analysisLoading' | 'currentJobId'
> = {
  importChat: [],
  analysisChat: [],
  importPreview: [],
  importLoading: false,
  analysisLoading: false,
  currentJobId: null,
}

export const useFinanceStore = create<FinanceState>()(
  persist(
    (set) => ({
      ...initialState,
      setImportLoading: (value) => set({ importLoading: value }),
      setAnalysisLoading: (value) => set({ analysisLoading: value }),
      addImportMessage: (message) =>
        set((state) => ({
          importChat: [...state.importChat, message],
        })),
      addAnalysisMessage: (message) =>
        set((state) => ({
          analysisChat: [...state.analysisChat, message],
        })),
      setImportPreview: (records) => set({ importPreview: records }),
      setCurrentJobId: (jobId) => set({ currentJobId: jobId }),
      reset: () => set(initialState),
    }),
    {
      name: 'finance-sync-store',
      partialize: (state) => ({
        importChat: state.importChat,
        analysisChat: state.analysisChat,
      }),
    }
  )
)
