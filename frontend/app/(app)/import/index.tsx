import { useCallback, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { ImportPreview } from '@/components/imports/ImportPreview'
import { NavLink } from '@/components/common/NavLink'
import { useFinanceStore } from '@/src/state/financeStore'
import { apiClient, HttpError } from '@/src/services/apiClient'

import { AIImportPanel } from './panels/AIImportPanel'
import { FileImportPanel } from './panels/FileImportPanel'
import { APIImportPanel } from './panels/APIImportPanel'

type ImportTab = 'ai' | 'file' | 'api'

const generateId = () => Math.random().toString(36).slice(2)

type ConfirmJobResponse = {
  approvedCount: number
  rejectedCount: number
}

const MAX_PREVIEW_LENGTH = 80 // 预览最大长度

const truncateMessage = (content: string, maxLength: number) => {
  if (content.length <= maxLength) {
    return content
  }
  return content.substring(0, maxLength) + '...'
}

const formatMessageTime = (isoString: string) => {
  try {
    const date = new Date(isoString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}`
  } catch {
    return ''
  }
}

export default function ImportScreen() {
  const [activeTab, setActiveTab] = useState<ImportTab>('ai')
  const [isConfirming, setIsConfirming] = useState(false)
  const [pendingOverwriteMessage, setPendingOverwriteMessage] = useState<string | null>(null)
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set())

  const {
    importPreview,
    currentJobId,
    importChat,
    setImportPreview,
    setCurrentJobId,
    addImportMessage,
  } = useFinanceStore()

  const toggleMessageExpanded = useCallback((messageId: string) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev)
      if (next.has(messageId)) {
        next.delete(messageId)
      } else {
        next.add(messageId)
      }
      return next
    })
  }, [])

  const messages = useMemo(() => {
    // 按操作时间倒序排列，显示最近50条
    return [...importChat]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 50)
  }, [importChat])

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
        setPendingOverwriteMessage(null)
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
          const recordType = detail?.recordType ?? 'record'
          const period =
            (conflict.occurredOn as string | undefined) ||
            (conflict.month as string | undefined) ||
            (conflict.reportedAt as string | undefined)
          const category = (conflict.category as string | undefined) || (conflict.categoryPath as string | undefined)
          const subcategory = conflict.subcategory as string | undefined
          const detailDescription = conflict.description as string | undefined
          const parts: string[] = []
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
              ? `${summaryText} 已存在收入记录，点击"覆盖入库"确认是否覆盖。`
              : `${summaryText} 已存在记录，点击"覆盖入库"确认是否覆盖。`

          setPendingOverwriteMessage(bannerMessage)
          addImportMessage({
            id: generateId(),
            role: 'assistant',
            content: bannerMessage,
            createdAt: new Date().toISOString(),
          })

          if (Platform.OS === 'web') {
            window.alert(`${bannerMessage}\n请在提示下面点击"覆盖入库"按钮继续。`)
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

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView 
        style={styles.scrollView} 
        contentContainerStyle={styles.scrollViewContent}
        showsVerticalScrollIndicator={true}
      >
        <View style={styles.container}>
          <View style={styles.header}>
            <View>
              <Text style={styles.title}>数据录入</Text>
              <Text style={styles.subtitle}>选择输入方式，导入财务数据</Text>
            </View>
            <View style={styles.links}>
              <NavLink href="/(app)/dashboard" label="财务看板" textStyle={styles.link} />
              <NavLink href="/(app)/analysis" label="查询分析" textStyle={styles.link} />
              <NavLink href="/(app)/history" label="历史记录" textStyle={styles.link} />
            </View>
          </View>

          {/* 标签页切换 */}
          <View style={styles.tabs}>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'ai' && styles.tabActive]}
              onPress={() => setActiveTab('ai')}
            >
              <Text style={[styles.tabText, activeTab === 'ai' && styles.tabTextActive]}>AI输入</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'file' && styles.tabActive]}
              onPress={() => setActiveTab('file')}
            >
              <Text style={[styles.tabText, activeTab === 'file' && styles.tabTextActive]}>文件上传</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'api' && styles.tabActive]}
              onPress={() => setActiveTab('api')}
            >
              <Text style={[styles.tabText, activeTab === 'api' && styles.tabTextActive]}>API同步</Text>
            </TouchableOpacity>
          </View>

          {/* 内容区域 */}
          <View style={styles.contentWrapper}>
            {/* 统一的历史记录区域 - 占据原来AI聊天区的空间，所有标签页都可见 */}
            <View style={styles.historySection}>
              <View style={styles.historyHeader}>
                <Text style={styles.historyTitle}>历史记录 {messages.length > 0 && `(${messages.length})`}</Text>
              </View>
              {messages.length > 0 ? (
                <ScrollView style={styles.historyContainer} contentContainerStyle={styles.historyContainerContent}>
                  {messages.map((message) => {
                    const isExpanded = expandedMessages.has(message.id)
                    const isLongMessage = message.content.length > MAX_PREVIEW_LENGTH
                    const displayContent = isExpanded || !isLongMessage ? message.content : truncateMessage(message.content, MAX_PREVIEW_LENGTH)

                    return (
                      <View key={message.id} style={styles.messageBubble}>
                        <View style={styles.messageHeader}>
                          <Text style={styles.messageContent}>{displayContent}</Text>
                          <Text style={styles.messageTime}>{formatMessageTime(message.createdAt)}</Text>
                        </View>
                        {isLongMessage && (
                          <TouchableOpacity
                            style={styles.expandButton}
                            onPress={() => toggleMessageExpanded(message.id)}
                          >
                            <Text style={styles.expandButtonText}>
                              {isExpanded ? '收起' : '展开查看完整内容'}
                            </Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    )
                  })}
                </ScrollView>
              ) : (
                <View style={styles.historyEmpty}>
                  <Text style={styles.historyEmptyText}>暂无历史记录</Text>
                </View>
              )}
            </View>

            {/* 标签页内容区域 */}
            {activeTab === 'ai' ? (
              <View style={styles.aiPanelWrapper}>
                <AIImportPanel />
              </View>
            ) : (
              <View style={styles.content}>
                {activeTab === 'file' && <FileImportPanel />}
                {activeTab === 'api' && <APIImportPanel />}
              </View>
            )}
          </View>

          {/* 统一的预览和确认区域 */}
          <View style={styles.previewSection}>
            <ImportPreview records={importPreview} />
            {pendingOverwriteMessage && (
              <View style={styles.overwriteBanner}>
                <Text style={styles.overwriteText}>{pendingOverwriteMessage}</Text>
                <View style={styles.overwriteButtonContainer}>
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
              </View>
            )}
            {importPreview.length > 0 && !pendingOverwriteMessage && (
              <TouchableOpacity
                style={[styles.confirmButton, (isConfirming || importPreview.length === 0) && styles.confirmButtonDisabled]}
                onPress={handleConfirm}
                disabled={isConfirming || importPreview.length === 0}
              >
                {isConfirming ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.confirmButtonText}>确认入库</Text>}
              </TouchableOpacity>
            )}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F1420',
  },
  scrollView: {
    flex: 1,
  },
  scrollViewContent: {
    flexGrow: 1,
  },
  container: {
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
  link: {
    color: '#60A5FA',
    fontSize: 14,
  },
  tabs: {
    flexDirection: 'row',
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 4,
    marginBottom: 16,
    gap: 4,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: {
    backgroundColor: '#3B82F6',
  },
  tabText: {
    color: '#94A3B8',
    fontSize: 14,
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  contentWrapper: {
    flexDirection: 'column',
    gap: 16,
  },
  historySection: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    overflow: 'hidden',
    height: 200, // 固定高度，避免占据过多空间
    maxHeight: 300, // 最大高度
  },
  historyHeader: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(148, 163, 184, 0.1)',
  },
  historyTitle: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '500',
  },
  historyContainer: {
    flex: 1,
  },
  historyContainerContent: {
    padding: 12,
    paddingBottom: 8,
  },
  historyEmpty: {
    flex: 1,
    padding: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  historyEmptyText: {
    color: '#64748B',
    fontSize: 12,
  },
  messageBubble: {
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
    backgroundColor: 'rgba(148, 163, 184, 0.1)',
  },
  messageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  messageContent: {
    flex: 1,
    color: '#CBD5F5',
    fontSize: 12,
    lineHeight: 18,
  },
  messageTime: {
    color: '#64748B',
    fontSize: 10,
    flexShrink: 0,
    marginTop: 2,
  },
  expandButton: {
    marginTop: 8,
    paddingVertical: 4,
  },
  expandButtonText: {
    color: '#60A5FA',
    fontSize: 12,
    fontWeight: '500',
  },
  content: {
    // 移除 flexShrink，让内容自然扩展
  },
  aiPanelWrapper: {
    // 移除 flexShrink，让内容自然扩展
  },
  previewSection: {
    marginTop: 16,
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
    padding: 16,
    marginTop: 16,
    marginBottom: 16,
    gap: 12,
  },
  overwriteText: {
    color: '#FCA5A5',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 4,
  },
  overwriteButtonContainer: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    alignItems: 'center',
  },
  overwriteButton: {
    backgroundColor: '#EF4444',
    borderRadius: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    minWidth: 120,
    alignItems: 'center',
    justifyContent: 'center',
  },
  overwriteButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
})

