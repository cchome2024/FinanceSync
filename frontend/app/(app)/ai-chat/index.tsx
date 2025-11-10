import { useFocusEffect } from 'expo-router'
import { useCallback, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import * as DocumentPicker from 'expo-document-picker'
import { ImportPreview } from '@/components/imports/ImportPreview'
import { apiClient, HttpError } from '@/src/services/apiClient'
import { useFinanceStore } from '@/src/state/financeStore'
import { NavLink } from '@/components/common/NavLink'

type CandidateRecord = {
  recordType: 'account_balance' | 'revenue' | 'expense' | 'income_forecast' | 'revenue_forecast'
  payload: Record<string, unknown>
  confidence?: number
  warnings?: string[]
}

type ParseJobResponse = {
  jobId: string
  status: string
  preview: CandidateRecord[]
  rawResponse?: unknown
}

type ConfirmJobResponse = {
  approvedCount: number
  rejectedCount: number
}

const formatRawResponse = (raw: unknown): string => {
  if (!raw) {
    return '暂无原始响应'
  }

  if (typeof raw === 'string') {
    return raw
  }

  if (typeof raw === 'object' && raw !== null && 'rawText' in raw) {
    const rawText = (raw as { rawText?: unknown }).rawText
    if (typeof rawText === 'string') {
      try {
        const parsed = JSON.parse(rawText)
        return JSON.stringify(parsed, null, 2)
      } catch {
        return rawText
      }
    }
  }

  try {
    return JSON.stringify(raw, null, 2)
  } catch {
    return String(raw)
  }
}

const generateId = () => Math.random().toString(36).slice(2)

const formatRecord = (record: CandidateRecord, index: number) => {
  const lines: string[] = []
  lines.push(`记录 ${index + 1}（类型：${record.recordType}）`)
  if (record.confidence != null) {
    lines.push(`可信度：${(record.confidence * 100).toFixed(1)}%`)
  }
  lines.push('明细：')
  Object.entries(record.payload).forEach(([key, value]) => {
    lines.push(`  • ${key}: ${String(value ?? '')}`)
  })
  if (record.warnings && record.warnings.length > 0) {
    lines.push('提示：')
    record.warnings.forEach((warning) => lines.push(`  ⚠ ${warning}`))
  }
  return lines.join('\n')
}

export default function AIChatScreen() {
  const [messageInput, setMessageInput] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [isConfirming, setIsConfirming] = useState(false)
  const [selectedFile, setSelectedFile] = useState<DocumentPicker.DocumentPickerAsset | null>(null)
  const [isPickingFile, setIsPickingFile] = useState(false)
  const [pendingOverwriteMessage, setPendingOverwriteMessage] = useState<string | null>(null)

  const {
    importChat,
    importPreview,
    importLoading,
    currentJobId,
    addImportMessage,
    setImportPreview,
    setImportLoading,
    setCurrentJobId,
  } = useFinanceStore()

  const handleSend = useCallback(async () => {
    if (!messageInput.trim()) {
      return
    }

    const userMessage = {
      id: generateId(),
      role: 'user' as const,
      content: messageInput.trim(),
      createdAt: new Date().toISOString(),
    }

    addImportMessage(userMessage)
    setMessageInput('')
    setImportLoading(true)

    try {
      const formData = new FormData()
      formData.append('prompt', userMessage.content)
      if (companyId.trim()) {
        formData.append('company_id', companyId.trim())
      }
      if (selectedFile) {
        if (selectedFile.file) {
          formData.append('file', selectedFile.file)
        } else if (selectedFile.uri) {
          formData.append('file', {
            uri: selectedFile.uri,
            name: selectedFile.name ?? 'upload',
            type: selectedFile.mimeType ?? 'application/octet-stream',
          } as unknown as Blob)
        }
      }

      const response = await apiClient.post<ParseJobResponse>('/api/v1/parse/upload', formData)
      console.log('[IMPORT CHAT] response', response)
      setCurrentJobId(response.jobId)
      const previewRecords = response.preview.map((record, index) => ({
        id: `${response.jobId}-${index}`,
        recordType: record.recordType,
        payload: record.payload,
        confidence: record.confidence,
        warnings: record.warnings ?? [],
      }))
      setImportPreview(previewRecords)
      setSelectedFile(null)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `原始响应：\n${formatRawResponse(response.rawResponse ?? response.preview)}`,
        createdAt: new Date().toISOString(),
      })

      if (response.preview.length === 0) {
        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: '没有识别到结构化记录，请检查输入内容。',
          createdAt: new Date().toISOString(),
        })
        return
      }

      const typeNames: Record<CandidateRecord['recordType'], string> = {
        account_balance: '账户余额',
        revenue: '收入',
        expense: '支出',
        income_forecast: '收入预测',
        revenue_forecast: '收入预测',
      }
      const counts: Record<CandidateRecord['recordType'], number> = {
        account_balance: 0,
        revenue: 0,
        expense: 0,
        income_forecast: 0,
        revenue_forecast: 0,
      }
      response.preview.forEach((record) => {
        counts[record.recordType] += 1
      })

      const detailLines = (Object.keys(counts) as Array<CandidateRecord['recordType']>)
        .filter((type) => counts[type] > 0)
        .map((type) => `- ${typeNames[type]} ${counts[type]} 条`)
      const summaryLines = [
        `识别到 ${response.preview.length} 条记录：`,
        ...detailLines,
        '请在下方候选记录列表中确认内容。',
      ]

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: summaryLines.join('\n'),
        createdAt: new Date().toISOString(),
      })
    } catch (error) {
      console.error(error)
      Alert.alert('解析失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setImportLoading(false)
    }
  }, [messageInput, addImportMessage, setImportPreview, companyId, setImportLoading, setCurrentJobId])

  const executeConfirm = useCallback(
    async (forceOverwrite = false) => {
      if (!currentJobId) {
        return
      }

      try {
        setIsConfirming(true)
        const payload = {
          actions: importPreview.map((record) => ({
            recordType: record.recordType,
            operation: 'approve' as const,
            payload: record.payload,
            overwrite: forceOverwrite,
          })),
        }
        const result = await apiClient.post<ConfirmJobResponse>(
          `/api/v1/import-jobs/${currentJobId}/confirm`,
          payload
        )

        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: `已确认入库 ${result.approvedCount} 条记录，拒绝 ${result.rejectedCount} 条。`,
          createdAt: new Date().toISOString(),
        })
        setImportPreview([])
        setCurrentJobId(null)
      } catch (error) {
        const httpError = error instanceof HttpError ? error : undefined
        if (httpError?.status === 409) {
          let parsed: { detail?: { conflict?: Record<string, unknown>; recordType?: string; message?: string } } | undefined
          try {
            parsed = httpError.body ? JSON.parse(httpError.body) : undefined
          } catch {
            // ignore
          }
          const detail = parsed?.detail
          const conflict = detail?.conflict ?? {}
          const companyName = (conflict.companyId as string | undefined) || '该公司'
          const recordType = detail?.recordType ?? 'record'
          const period =
            (conflict.occurredOn as string | undefined) ||
            (conflict.month as string | undefined) ||
            (conflict.reportedAt as string | undefined)
          const category = (conflict.category as string | undefined) || (conflict.categoryPath as string | undefined)
          const subcategory = conflict.subcategory as string | undefined
          const detailDescription = conflict.description as string | undefined
          const parts: string[] = [companyName]
          if (period) {
            parts.push(period)
          }
          if (recordType === 'revenue') {
            if (category) {
              parts.push(category)
            }
            if (subcategory) {
              parts.push(subcategory)
            }
            if (detailDescription) {
              parts.push(detailDescription)
            }
          }
          const summaryText = parts.join(' / ')
          const bannerMessage =
            recordType === 'revenue'
              ? `${summaryText} 已存在收入记录，点击“覆盖入库”确认是否覆盖。`
              : `${summaryText} 已存在记录，点击“覆盖入库”确认是否覆盖。`

          setPendingOverwriteMessage(bannerMessage)
          addImportMessage({
            id: generateId(),
            role: 'assistant',
            content: bannerMessage,
            createdAt: new Date().toISOString(),
          })

          if (Platform.OS === 'web') {
            window.alert(`${bannerMessage}\n请在提示下面点击“覆盖入库”按钮继续。`)
          } else {
            Alert.alert('检测到重复记录', bannerMessage, [
              { text: '取消', style: 'cancel' },
              {
                text: '覆盖',
                onPress: () => {
                  setPendingOverwriteMessage(null)
                  setTimeout(() => {
                    void executeConfirm(true)
                  }, 0)
                },
              },
            ])
          }
          return
        }

        const fallback =
          (httpError?.body && httpError.body.toString()) ||
          (error instanceof Error ? error.message : '未知错误')
        Alert.alert('确认失败', fallback)
      } finally {
        setIsConfirming(false)
      }
    },
    [addImportMessage, currentJobId, importPreview, setCurrentJobId, setImportPreview]
  )

  const handleConfirm = useCallback(() => {
    if (!currentJobId || importPreview.length === 0 || isConfirming) {
      return
    }

    if (Platform.OS === 'web') {
      if (window.confirm('确认将当前候选记录写入数据库吗？')) {
        void executeConfirm(false)
      }
      return
    }

    Alert.alert('确认入库', '确认将当前候选记录写入数据库吗？', [
      { text: '取消', style: 'cancel' },
      { text: '确认', onPress: () => void executeConfirm(false) },
    ])
  }, [currentJobId, importPreview, isConfirming, executeConfirm])

  const handlePickFile = useCallback(async () => {
    try {
      setIsPickingFile(true)
      const result = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true,
        multiple: false,
      })
      if (!('canceled' in result && result.canceled) && result.assets && result.assets.length > 0) {
        setSelectedFile(result.assets[0])
      }
    } catch (error) {
      console.error('[IMPORT CHAT] pick file failed', error)
      Alert.alert('选择文件失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setIsPickingFile(false)
    }
  }, [])

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null)
  }, [])

  const messages = useMemo(() => importChat.slice(-20), [importChat])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>FinanceSync 助手</Text>
            <Text style={styles.subtitle}>粘贴文本或说明需求，AI 帮你解析财务数据。</Text>
          </View>
          <View style={styles.links}>
            <NavLink href="/(app)/dashboard" label="财务看板" textStyle={styles.historyLink} />
            <NavLink href="/(app)/analysis" label="查询分析" textStyle={styles.historyLink} />
            <NavLink href="/(app)/history" label="历史记录" textStyle={styles.historyLink} />
          </View>
        </View>

        <ScrollView style={styles.messageContainer}>
          {messages.length === 0 && <Text style={styles.placeholder}>开始对话，等待 AI 解析结果。</Text>}
          {messages.map((message) => (
            <View
              key={message.id}
              style={[styles.messageBubble, message.role === 'user' ? styles.userBubble : styles.assistantBubble]}
            >
              <Text style={styles.messageRole}>{message.role === 'user' ? '你' : 'AI'}</Text>
              <Text style={styles.messageContent}>{message.content}</Text>
            </View>
          ))}
          {pendingOverwriteMessage && (
            <View style={[styles.messageBubble, styles.assistantBubble]}>
              <Text style={styles.messageRole}>AI</Text>
              <Text style={styles.messageContent}>{pendingOverwriteMessage}</Text>
            </View>
          )}
        </ScrollView>

        <ImportPreview records={importPreview} />
        {pendingOverwriteMessage && (
          <View style={styles.overwriteBanner}>
            <Text style={styles.overwriteText}>{pendingOverwriteMessage}</Text>
            <TouchableOpacity
              style={styles.overwriteButton}
              onPress={() => {
                setPendingOverwriteMessage(null)
                void executeConfirm(true)
              }}
              disabled={isConfirming}
            >
              {isConfirming ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.overwriteButtonText}>覆盖入库</Text>}
            </TouchableOpacity>
          </View>
        )}
        {importPreview.length > 0 && (
          <TouchableOpacity
            style={[styles.confirmButton, (isConfirming || importLoading) && styles.confirmButtonDisabled]}
            onPress={handleConfirm}
            disabled={isConfirming || importLoading}
          >
            {isConfirming ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.confirmButtonText}>确认入库</Text>}
          </TouchableOpacity>
        )}

        <View style={styles.form}>
          <TextInput
            style={styles.companyInput}
            placeholder="可选：输入公司 ID"
            placeholderTextColor="#6B7280"
            value={companyId}
            onChangeText={setCompanyId}
            autoCapitalize="none"
          />
          <View style={styles.fileRow}>
            <TouchableOpacity
              style={[styles.fileButton, (importLoading || isPickingFile) && styles.fileButtonDisabled]}
              onPress={handlePickFile}
              disabled={importLoading || isPickingFile}
            >
              <Text style={styles.fileButtonText}>{isPickingFile ? '选择中…' : '选择文件'}</Text>
            </TouchableOpacity>
            {selectedFile && (
              <View style={styles.fileInfo}>
                <Text style={styles.fileName} numberOfLines={1}>
                  {selectedFile.name ?? '已选择文件'}
                </Text>
                <TouchableOpacity onPress={handleRemoveFile}>
                  <Text style={styles.fileRemove}>移除</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
          <TextInput
            style={styles.textArea}
            placeholder="请输入待解析的财务文本或说明…"
            placeholderTextColor="#6B7280"
            value={messageInput}
            onChangeText={setMessageInput}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} onPress={handleSend} disabled={importLoading}>
            {importLoading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.sendButtonText}>发送</Text>}
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F1420',
  },
  container: {
    flex: 1,
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    marginTop: 8,
  },
  title: {
    color: '#FFFFFF',
    fontSize: 24,
    fontWeight: '700',
  },
  subtitle: {
    color: '#94A3B8',
    fontSize: 14,
    marginTop: 4,
  },
  links: {
    flexDirection: 'row',
    gap: 12,
  },
  historyLink: {
    color: '#60A5FA',
    fontSize: 14,
  },
  messageContainer: {
    flex: 1,
    borderRadius: 16,
    backgroundColor: '#131A2B',
    padding: 16,
  },
  placeholder: {
    color: '#64748B',
  },
  messageBubble: {
    padding: 14,
    borderRadius: 12,
    marginBottom: 12,
  },
  userBubble: {
    backgroundColor: 'rgba(59, 130, 246, 0.25)',
    alignSelf: 'flex-end',
  },
  assistantBubble: {
    backgroundColor: 'rgba(148, 163, 184, 0.25)',
    alignSelf: 'flex-start',
  },
  messageRole: {
    color: '#E2E8F0',
    fontSize: 12,
    marginBottom: 6,
  },
  messageContent: {
    color: '#F8FAFC',
    fontSize: 14,
    lineHeight: 20,
  },
  form: {
    marginTop: 20,
    backgroundColor: '#131A2B',
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  companyInput: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#E2E8F0',
    fontSize: 14,
  },
  textArea: {
    minHeight: 80,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#E2E8F0',
    fontSize: 14,
    textAlignVertical: 'top',
  },
  fileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  fileButton: {
    backgroundColor: '#475569',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignSelf: 'flex-start',
  },
  fileButtonDisabled: {
    opacity: 0.7,
  },
  fileButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
  },
  fileInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  fileName: {
    flex: 1,
    color: '#CBD5F5',
    fontSize: 13,
  },
  fileRemove: {
    color: '#F87171',
    fontSize: 13,
  },
  sendButton: {
    backgroundColor: '#3B82F6',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  sendButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  confirmButton: {
    backgroundColor: '#22C55E',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 16,
  },
  confirmButtonDisabled: {
    opacity: 0.7,
  },
  confirmButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  overwriteBanner: {
    backgroundColor: 'rgba(248, 113, 113, 0.15)',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    gap: 12,
  },
  overwriteText: {
    color: '#FCA5A5',
    fontSize: 14,
    lineHeight: 20,
  },
  overwriteButton: {
    alignSelf: 'flex-start',
    backgroundColor: '#EF4444',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  overwriteButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
})

