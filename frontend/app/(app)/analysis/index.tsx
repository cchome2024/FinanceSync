import { Link } from 'expo-router'
import { useCallback, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { apiClient } from '@/src/services/apiClient'
import { useFinanceStore } from '@/src/state/financeStore'

type AnalysisResponse = {
  queryId: string
  answer: string
  highlights?: string[]
}

const generateId = () => Math.random().toString(36).slice(2)

export default function AnalysisChatScreen() {
  const [messageInput, setMessageInput] = useState('')
  const { analysisChat, analysisLoading, addAnalysisMessage, setAnalysisLoading } = useFinanceStore()

  const handleSend = useCallback(async () => {
    if (!messageInput.trim()) {
      return
    }

    const question = messageInput.trim()
    const userMessage = {
      id: generateId(),
      role: 'user' as const,
      content: question,
      createdAt: new Date().toISOString(),
    }

    addAnalysisMessage(userMessage)
    setMessageInput('')
    setAnalysisLoading(true)

    try {
      const response = await apiClient.post<AnalysisResponse>('/api/v1/query', { question })
      console.log('[ANALYSIS CHAT] response', response)

      addAnalysisMessage({
        id: generateId(),
        role: 'assistant',
        content: response.answer,
        createdAt: new Date().toISOString(),
      })

      if (response.highlights && response.highlights.length > 0) {
        addAnalysisMessage({
          id: generateId(),
          role: 'assistant',
          content: response.highlights.map((item) => `• ${item}`).join('\n'),
          createdAt: new Date().toISOString(),
        })
      }
    } catch (error) {
      console.error(error)
      Alert.alert('查询失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setAnalysisLoading(false)
    }
  }, [messageInput, addAnalysisMessage, setAnalysisLoading])

  const messages = useMemo(() => analysisChat.slice(-20), [analysisChat])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>查询分析助手</Text>
            <Text style={styles.subtitle}>提出自然语言问题，获取财务洞察与提示。</Text>
          </View>
          <Link href="/(app)/ai-chat" style={styles.historyLink}>
            数据录入
          </Link>
        </View>

        <ScrollView style={styles.messageContainer}>
          {messages.length === 0 && <Text style={styles.placeholder}>输入问题，例如“本月收入趋势如何？”。</Text>}
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
            style={styles.textArea}
            placeholder="请输入你的问题…"
            placeholderTextColor="#6B7280"
            value={messageInput}
            onChangeText={setMessageInput}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} onPress={handleSend} disabled={analysisLoading}>
            {analysisLoading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.sendButtonText}>发送</Text>}
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


