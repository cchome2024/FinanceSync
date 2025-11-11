import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, FlatList, Platform, StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import { apiClient } from '@/src/services/apiClient'
import { useFinanceStore } from '@/src/state/financeStore'

type ApiSource = {
  id: string
  name: string
  apiType: string
  enabled: boolean
  lastRunAt: string | null
  schedule: string | null
}

type ApiSourceListResponse = ApiSource[]

type TriggerResponse = {
  jobId: string
  status: string
  preview: Array<{
    recordType: string
    payload: Record<string, unknown>
    confidence?: number
    warnings?: string[]
  }>
}

const generateId = () => Math.random().toString(36).slice(2)

const formatTimeAgo = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 7) return `${diffDays} 天前`
  return date.toLocaleDateString('zh-CN')
}

export function APIImportPanel() {
  const [apiSources, setApiSources] = useState<ApiSource[]>([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)

  const { addImportMessage, setImportPreview, setCurrentJobId } = useFinanceStore()

  const loadApiSources = useCallback(async () => {
    setLoading(true)
    try {
      const response = await apiClient.get<ApiSourceListResponse>('/api/v1/api-sources')
      setApiSources(response)
    } catch (error) {
      console.error('[API IMPORT] load sources failed', error)
      // 如果接口不存在，显示空状态
      if (error instanceof Error && error.message.includes('404')) {
        setApiSources([])
      } else {
        Alert.alert('加载失败', error instanceof Error ? error.message : '未知错误')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadApiSources()
  }, [loadApiSources])

  const handleSync = useCallback(
    async (sourceId: string) => {
      setSyncing(sourceId)
      try {
        const response = await apiClient.post<TriggerResponse>(`/api/v1/api-sources/${sourceId}/trigger`)
        console.log('[API IMPORT] sync response', response)
        setCurrentJobId(response.jobId)
        const previewRecords = response.preview.map((record, index) => ({
          id: `${response.jobId}-${index}`,
          recordType: record.recordType as any,
          payload: record.payload,
          confidence: record.confidence,
          warnings: record.warnings ?? [],
        }))
        setImportPreview(previewRecords)

        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: `API 同步完成，识别到 ${response.preview.length} 条记录。请在下方候选记录列表中确认内容。`,
          createdAt: new Date().toISOString(),
        })

        if (response.preview.length === 0) {
          addImportMessage({
            id: generateId(),
            role: 'assistant',
            content: 'API 返回的数据中没有识别到结构化记录。',
            createdAt: new Date().toISOString(),
          })
        }

        // 刷新列表
        await loadApiSources()
      } catch (error) {
        console.error(error)
        Alert.alert('同步失败', error instanceof Error ? error.message : '未知错误')
      } finally {
        setSyncing(null)
      }
    },
    [addImportMessage, setImportPreview, setCurrentJobId, loadApiSources]
  )

  const handleAdd = useCallback(() => {
    Alert.alert('提示', 'API 源配置功能开发中，请通过后端配置')
  }, [])

  const handleClearIncomeForecastsConfirm = useCallback(async () => {
    setClearing(true)
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/income-forecasts`, {
        method: 'DELETE',
        headers: {
          Accept: 'application/json',
        },
      })

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = `清空失败: ${response.status}`
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.detail || errorMessage
        } catch {
          errorMessage = errorText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const result: { deleted_count: number } = await response.json()
      console.log('[API IMPORT] Clear income forecasts response:', result)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `已清空 ${result.deleted_count} 条预测收入记录。`,
        createdAt: new Date().toISOString(),
      })

      Alert.alert('清空成功', `已清空 ${result.deleted_count} 条预测收入记录。`)
    } catch (error) {
      console.error('[API IMPORT] clear income forecasts error', error)
      Alert.alert('清空失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setClearing(false)
    }
  }, [addImportMessage])

  const handleClearIncomeForecasts = useCallback(() => {
    if (Platform.OS === 'web') {
      if (window.confirm('确定要清空所有预测收入记录吗？此操作不可恢复！')) {
        void handleClearIncomeForecastsConfirm()
      }
    } else {
      Alert.alert('确认清空', '确定要清空所有预测收入记录吗？此操作不可恢复！', [
        { text: '取消', style: 'cancel' },
        { text: '确认', style: 'destructive', onPress: () => void handleClearIncomeForecastsConfirm() },
      ])
    }
  }, [handleClearIncomeForecastsConfirm])

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color="#60A5FA" />
        <Text style={styles.loadingText}>加载中...</Text>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <View style={styles.description}>
        <View style={styles.descriptionHeader}>
          <View style={styles.descriptionContent}>
            <Text style={styles.descriptionText}>配置 API 数据源，自动或手动同步预期收入数据</Text>
            <Text style={styles.descriptionHint}>第一阶段主要处理预期收入数据</Text>
          </View>
          <TouchableOpacity
            style={[styles.clearButton, clearing && styles.clearButtonDisabled]}
            onPress={handleClearIncomeForecasts}
            disabled={clearing}
          >
            {clearing ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <Text style={styles.clearButtonText}>清空预测收入表</Text>
            )}
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.header}>
        <Text style={styles.sectionTitle}>API 数据源</Text>
        <TouchableOpacity style={styles.addButton} onPress={handleAdd}>
          <Text style={styles.addButtonText}>➕ 添加</Text>
        </TouchableOpacity>
      </View>

      {apiSources.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>暂无 API 数据源</Text>
          <Text style={styles.emptyHint}>点击上方"添加"按钮配置新的 API 数据源</Text>
          <Text style={styles.emptyHint}>或通过后端配置文件添加</Text>
        </View>
      ) : (
        <FlatList
          data={apiSources}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={styles.apiSourceCard}>
              <View style={styles.apiSourceHeader}>
                <View style={styles.apiSourceInfo}>
                  <Text style={styles.apiSourceName}>{item.name}</Text>
                  <Text style={styles.apiSourceType}>{item.apiType}</Text>
                </View>
                <View style={styles.apiSourceStatus}>
                  {item.enabled ? (
                    <View style={styles.statusBadge}>
                      <Text style={styles.statusBadgeText}>已启用</Text>
                    </View>
                  ) : (
                    <View style={[styles.statusBadge, styles.statusBadgeDisabled]}>
                      <Text style={[styles.statusBadgeText, styles.statusBadgeTextDisabled]}>已禁用</Text>
                    </View>
                  )}
                </View>
              </View>
              {item.lastRunAt && (
                <Text style={styles.apiSourceMeta}>最后同步：{formatTimeAgo(item.lastRunAt)}</Text>
              )}
              {item.schedule && <Text style={styles.apiSourceMeta}>定时同步：{item.schedule}</Text>}
              <View style={styles.apiSourceActions}>
                <TouchableOpacity
                  style={[styles.syncButton, syncing === item.id && styles.syncButtonDisabled]}
                  onPress={() => handleSync(item.id)}
                  disabled={syncing === item.id || !item.enabled}
                >
                  {syncing === item.id ? (
                    <>
                      <ActivityIndicator color="#FFFFFF" size="small" />
                      <Text style={styles.syncButtonText}>同步中...</Text>
                    </>
                  ) : (
                    <Text style={styles.syncButtonText}>立即同步</Text>
                  )}
                </TouchableOpacity>
                <TouchableOpacity style={styles.configButton} disabled>
                  <Text style={styles.configButtonText}>配置</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    gap: 16,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    color: '#94A3B8',
    fontSize: 14,
  },
  description: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 12,
  },
  descriptionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  descriptionContent: {
    flex: 1,
    gap: 4,
  },
  descriptionText: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '500',
  },
  descriptionHint: {
    color: '#94A3B8',
    fontSize: 12,
  },
  clearButton: {
    backgroundColor: '#EF4444',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginLeft: 12,
  },
  clearButtonDisabled: {
    opacity: 0.7,
  },
  clearButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
  },
  addButton: {
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  addButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '500',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 48,
  },
  emptyText: {
    color: '#94A3B8',
    fontSize: 16,
    fontWeight: '500',
  },
  emptyHint: {
    color: '#64748B',
    fontSize: 13,
  },
  apiSourceCard: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    gap: 12,
  },
  apiSourceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  apiSourceInfo: {
    flex: 1,
    gap: 4,
  },
  apiSourceName: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '600',
  },
  apiSourceType: {
    color: '#94A3B8',
    fontSize: 12,
  },
  apiSourceStatus: {
    marginLeft: 12,
  },
  statusBadge: {
    backgroundColor: 'rgba(34, 197, 94, 0.2)',
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  statusBadgeDisabled: {
    backgroundColor: 'rgba(148, 163, 184, 0.2)',
  },
  statusBadgeText: {
    color: '#22C55E',
    fontSize: 11,
    fontWeight: '500',
  },
  statusBadgeTextDisabled: {
    color: '#94A3B8',
  },
  apiSourceMeta: {
    color: '#94A3B8',
    fontSize: 12,
  },
  apiSourceActions: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  syncButton: {
    flex: 1,
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
  },
  syncButtonDisabled: {
    opacity: 0.7,
  },
  syncButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '500',
  },
  configButton: {
    backgroundColor: '#475569',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    opacity: 0.5,
  },
  configButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '500',
  },
})

