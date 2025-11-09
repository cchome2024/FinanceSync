import { Link } from 'expo-router'
import { useCallback, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { apiClient } from '@/src/services/apiClient'
import { useFinanceStore } from '@/src/state/financeStore'

type CandidateRecord = {
  recordType: 'account_balance' | 'revenue' | 'expense' | 'income_forecast'
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

  const { importChat, importPreview, importLoading, addImportMessage, setImportPreview, setImportLoading } =
    useFinanceStore()

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

      const response = await apiClient.post<ParseJobResponse>('/api/v1/parse/upload', formData)
      console.log('[IMPORT CHAT] response', response)
      setImportPreview([])

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `原始响应：\n${JSON.stringify(response.rawResponse ?? response.preview, null, 2)}`,
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

      response.preview.forEach((record, index) => {
        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: formatRecord(record, index),
          createdAt: new Date().toISOString(),
        })
      })
    } catch (error) {
      console.error(error)
      Alert.alert('解析失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setImportLoading(false)
    }
  }, [messageInput, addImportMessage, setImportPreview, companyId, setImportLoading])

  const messages = useMemo(() => importChat.slice(-20), [importChat])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>FinanceSync 助手</Text>
            <Text style={styles.subtitle}>粘贴文本或说明需求，AI 帮你解析财务数据。</Text>
          </View>
          <Link href="/(app)/history" style={styles.historyLink}>
            历史记录
          </Link>
          <Link href="/(app)/analysis" style={styles.historyLink}>
            查询分析
          </Link>
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
        </ScrollView>

        <View style={styles.form}>
          <TextInput
            style={styles.companyInput}
            placeholder="可选：输入公司 ID"
            placeholderTextColor="#6B7280"
            value={companyId}
            onChangeText={setCompanyId}
            autoCapitalize="none"
          />
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

