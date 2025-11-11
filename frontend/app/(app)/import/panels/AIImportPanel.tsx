import { useCallback, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native'
import * as DocumentPicker from 'expo-document-picker'

import { apiClient } from '@/src/services/apiClient'
import { useFinanceStore } from '@/src/state/financeStore'

type CandidateRecord = {
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

type ParseJobResponse = {
  jobId: string
  status: string
  preview: CandidateRecord[]
  rawResponse?: unknown
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

export function AIImportPanel() {
  const [messageInput, setMessageInput] = useState('')
  const [selectedFile, setSelectedFile] = useState<DocumentPicker.DocumentPickerAsset | null>(null)
  const [isPickingFile, setIsPickingFile] = useState(false)

  const {
    importChat,
    importLoading,
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
        expense_forecast: '支出预测',
      }
      const counts: Record<CandidateRecord['recordType'], number> = {
        account_balance: 0,
        revenue: 0,
        expense: 0,
        income_forecast: 0,
        revenue_forecast: 0,
        expense_forecast: 0,
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
  }, [messageInput, addImportMessage, setImportPreview, setImportLoading, setCurrentJobId, selectedFile])

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

  return (
    <View style={styles.container}>
      <View style={styles.description}>
        <Text style={styles.descriptionText}>支持文字、图片、文件，AI 自动识别并提取财务数据</Text>
      </View>

      <View style={styles.form}>
        <View style={styles.fileRow}>
          <TouchableOpacity
            style={[styles.fileButton, (importLoading || isPickingFile) && styles.fileButtonDisabled]}
            onPress={handlePickFile}
            disabled={importLoading || isPickingFile}
          >
            <Text style={styles.fileButtonText}>{isPickingFile ? '选择中…' : '📁 选择文件'}</Text>
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
          textAlignVertical="top"
        />
        <TouchableOpacity style={styles.sendButton} onPress={handleSend} disabled={importLoading}>
          {importLoading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.sendButtonText}>发送</Text>}
        </TouchableOpacity>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    gap: 12,
    flexDirection: 'column',
  },
  description: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 12,
  },
  descriptionText: {
    color: '#94A3B8',
    fontSize: 13,
    lineHeight: 18,
  },
  form: {
    backgroundColor: '#131A2B',
    borderRadius: 16,
    padding: 16,
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.1)',
    flex: 1, // 让输入区域占据更多空间
    justifyContent: 'flex-end', // 输入框靠底部
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
    flex: 1,
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
  textArea: {
    minHeight: 120,
    maxHeight: 200,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 12,
    color: '#E2E8F0',
    fontSize: 15,
    textAlignVertical: 'top',
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
})

