import { Link } from 'expo-router'
import { useMemo } from 'react'
import { Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { useFinanceStore } from '@/src/state/financeStore'

export default function HistoryScreen() {
  const { importChat, analysisChat, importPreview, reset } = useFinanceStore()

  const hasData = importChat.length > 0 || analysisChat.length > 0 || importPreview.length > 0
  const importMessages = useMemo(() => importChat, [importChat])
  const analysisMessages = useMemo(() => analysisChat, [analysisChat])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>历史记录</Text>
            <Text style={styles.subtitle}>查看最近提交的对话与解析结果</Text>
          </View>
          <View style={styles.links}>
            <Link href="/(app)/dashboard" style={styles.link}>
              财务看板
            </Link>
            <Link href="/(app)/ai-chat" style={styles.link}>
              数据录入
            </Link>
            <Link href="/(app)/analysis" style={styles.link}>
              查询分析
            </Link>
          </View>
        </View>

        {!hasData && <Text style={styles.placeholder}>暂无历史记录，先去和 AI 聊天吧。</Text>}

        {hasData && (
          <ScrollView style={styles.scroll}>
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>数据录入对话</Text>
              {importMessages.map((message) => (
                <View key={message.id} style={styles.messageCard}>
                  <Text style={styles.messageMeta}>
                    {message.role === 'user' ? '你' : message.role === 'assistant' ? 'AI' : '系统'} ·{' '}
                    {new Date(message.createdAt).toLocaleString()}
                  </Text>
                  <Text style={styles.messageText}>{message.content}</Text>
                </View>
              ))}
            </View>

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>查询分析对话</Text>
              {analysisMessages.map((message) => (
                <View key={message.id} style={styles.messageCard}>
                  <Text style={styles.messageMeta}>
                    {message.role === 'user' ? '你' : 'AI'} · {new Date(message.createdAt).toLocaleString()}
                  </Text>
                  <Text style={styles.messageText}>{message.content}</Text>
                </View>
              ))}
            </View>

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>最近候选记录</Text>
              {importPreview.map((record) => (
                <View key={record.id} style={styles.recordCard}>
                  <Text style={styles.recordTitle}>{record.recordType}</Text>
                  <Text style={styles.recordBody}>{JSON.stringify(record.payload, null, 2)}</Text>
                </View>
              ))}
            </View>
          </ScrollView>
        )}

        {hasData && (
          <TouchableOpacity style={styles.resetButton} onPress={reset}>
            <Text style={styles.resetText}>清除历史</Text>
          </TouchableOpacity>
        )}
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
    paddingBottom: 24,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 16,
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
  link: {
    color: '#60A5FA',
    fontSize: 14,
  },
  placeholder: {
    color: '#64748B',
    marginTop: 32,
    textAlign: 'center',
  },
  scroll: {
    flex: 1,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: '#E2E8F0',
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  messageCard: {
    backgroundColor: '#141C2C',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  messageMeta: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 4,
  },
  messageText: {
    color: '#F8FAFC',
    fontSize: 14,
    lineHeight: 20,
  },
  recordCard: {
    backgroundColor: '#141C2C',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  recordTitle: {
    color: '#60A5FA',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  recordBody: {
    color: '#CBD5F5',
    fontSize: 13,
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
  },
  resetButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  resetText: {
    color: '#F87171',
    fontSize: 16,
    fontWeight: '600',
  },
})

