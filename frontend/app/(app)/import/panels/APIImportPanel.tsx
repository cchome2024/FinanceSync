import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, FlatList, Modal, Platform, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native'

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

type RawDataItem = {
  FlareAssetCode?: number | string
  FundName?: string
  Date?: string
  name?: string
  cost?: number
  [key: string]: unknown
}

type ProcessedDataItem = RawDataItem & {
  categoryLevel1?: string
  categoryLevel2?: string
  categoryLevel3?: string
  categoryLevel4?: string
  expectedAmount?: number
  incomeStatus?: string
}

// 处理数据，计算类别和预计收入信息
// 只对符合规则的记录填充字段，不符合规则的记录不填充
const processDataItem = (item: RawDataItem): ProcessedDataItem => {
  const fundName = String(item.FundName || '')
  const name = String(item.name || '')
  const cost = Number(item.cost || 0)
  const assetCode = String(item.FlareAssetCode || '')
  
  // 判断是否符合规则覆盖条件
  // 规则覆盖条件：基金名称包含"慧度"（自主募集）或其他（投资顾问）
  const isCovered = fundName.includes('慧度') || true // 目前所有记录都覆盖，但可以根据需要调整
  
  if (!isCovered) {
    // 未覆盖的记录，不填充任何字段
    return {
      ...item,
    }
  }
  
  // 类别一级：固定为"资产管理"
  const categoryLevel1 = '资产管理'
  
  // 类别二级：根据基金名称判断
  let categoryLevel2 = '投资顾问'
  if (fundName.includes('慧度')) {
    categoryLevel2 = '自主募集'
  }
  
  // 类别四级：产品简称（基金名称）
  const categoryLevel4 = fundName
  
  // 特殊处理：中信信托·睿信稳健配置TOF金融投资集合资金信托计划
  const isSpecialProduct = fundName.includes('中信信托·睿信稳健配置TOF金融投资集合资金信托计划')
  const isSpecialAssetCode = String(assetCode).startsWith('2241')
  
  // 类别三级：根据资产编码结尾判断
  let categoryLevel3 = ''
  let incomeStatus = '已确认'
  
  // 特殊处理：如果产品是中信信托·睿信稳健配置TOF金融投资集合资金信托计划且资产编码以2241开头
  if (isSpecialProduct && isSpecialAssetCode) {
    categoryLevel3 = '浮动费用'
    incomeStatus = '未确认'
  } else {
    // 资产编码以1结尾 → "固定费用"，已确认
    // 资产编码以2结尾 → "浮动费用"，未确认
    if (assetCode.endsWith('1')) {
      categoryLevel3 = '固定费用'
      incomeStatus = '已确认'
    } else if (assetCode.endsWith('2')) {
      categoryLevel3 = '浮动费用'
      incomeStatus = '未确认'
    }
  }
  
  // 预计应收金额：根据二级分类和资产编码判断
  let expectedAmount = 0
  
  // 特殊处理：中信信托·睿信稳健配置TOF金融投资集合资金信托计划且资产编码以2241开头
  if (isSpecialProduct && isSpecialAssetCode) {
    expectedAmount = cost / 3
  } else if (categoryLevel2 === '自主募集') {
    // 自主募集：金额全额计入
    expectedAmount = cost
  } else if (categoryLevel2 === '投资顾问') {
    // 投资顾问：只计入资产编码以221开头的项目，其余计为0
    if (assetCode.startsWith('221')) {
      expectedAmount = cost
    } else {
      expectedAmount = 0
    }
  }
  
  return {
    ...item,
    categoryLevel1,
    categoryLevel2,
    categoryLevel3,
    categoryLevel4,
    expectedAmount,
    incomeStatus,
  }
}

// 收入状态选项
const INCOME_STATUS_OPTIONS = ['已确认', '未确认']

// 下拉选择组件
function StatusPicker({
  value,
  onChange,
  style,
}: {
  value: string
  onChange: (value: string) => void
  style?: any
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <View style={style}>
      <TouchableOpacity
        style={styles.pickerButton}
        onPress={() => setIsOpen(true)}
      >
        <Text style={styles.pickerButtonText}>{value || '选择状态'}</Text>
        <Text style={styles.pickerArrow}>▼</Text>
      </TouchableOpacity>
      <Modal
        visible={isOpen}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setIsOpen(false)}
      >
        <TouchableOpacity
          style={styles.pickerModalOverlay}
          activeOpacity={1}
          onPress={() => setIsOpen(false)}
        >
          <View style={styles.pickerModalContent}>
            {INCOME_STATUS_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option}
                style={[
                  styles.pickerOption,
                  value === option && styles.pickerOptionSelected,
                ]}
                onPress={() => {
                  onChange(option)
                  setIsOpen(false)
                }}
              >
                <Text
                  style={[
                    styles.pickerOptionText,
                    value === option && styles.pickerOptionTextSelected,
                  ]}
                >
                  {option}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  )
}

export function APIImportPanel() {
  const [apiSources, setApiSources] = useState<ApiSource[]>([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const [clearingExpense, setClearingExpense] = useState(false)
  const [rawData, setRawData] = useState<Record<string, RawDataItem[]>>({})
  const [editedData, setEditedData] = useState<Record<string, ProcessedDataItem[]>>({})
  const [confirming, setConfirming] = useState<Record<string, boolean>>({})

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
        // API导入面板不使用统一的预览和确认区域，所以不需要设置importPreview
        // const previewRecords = response.preview.map((record, index) => ({
        //   id: `${response.jobId}-${index}`,
        //   recordType: record.recordType as any,
        //   payload: record.payload,
        //   confidence: record.confidence,
        //   warnings: record.warnings ?? [],
        // }))
        // setImportPreview(previewRecords)

        // 保存原始查询结果数据，并进行处理
        if (response.rawResponse && 'raw_data' in response.rawResponse && Array.isArray(response.rawResponse.raw_data)) {
          const rawDataItems = response.rawResponse.raw_data as RawDataItem[]
          console.log('[API IMPORT] Raw data items:', rawDataItems.length)
          const processedData = rawDataItems.map(processDataItem)
          // 保存原始数据
          setRawData((prev) => {
            const newData = {
              ...prev,
              [sourceId]: rawDataItems,
            }
            console.log('[API IMPORT] Setting rawData for', sourceId, 'with', rawDataItems.length, 'items')
            return newData
          })
          // 初始化编辑数据（使用处理后的数据）
          setEditedData((prev) => ({
            ...prev,
            [sourceId]: processedData.map((item) => ({ ...item })),
          }))
        } else {
          console.log('[API IMPORT] No raw_data in response:', response.rawResponse)
        }

        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: `API 同步完成，获取到 ${response.rawResponse?.raw_data?.length || 0} 条记录。请在下方表格中查看和编辑数据，然后点击"确认入库"按钮。`,
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

  const handleClearExpenseForecastsConfirm = useCallback(async () => {
    setClearingExpense(true)
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/expense-forecasts`, {
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
      console.log('[API IMPORT] Clear expense forecasts response:', result)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `已清空 ${result.deleted_count} 条预测支出记录。`,
        createdAt: new Date().toISOString(),
      })

      Alert.alert('清空成功', `已清空 ${result.deleted_count} 条预测支出记录。`)
    } catch (error) {
      console.error('[API IMPORT] clear expense forecasts error', error)
      Alert.alert('清空失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setClearingExpense(false)
    }
  }, [addImportMessage])

  const handleClearExpenseForecasts = useCallback(() => {
    if (Platform.OS === 'web') {
      if (window.confirm('确定要清空所有预测支出记录吗？此操作不可恢复！')) {
        void handleClearExpenseForecastsConfirm()
      }
    } else {
      Alert.alert('确认清空', '确定要清空所有预测支出记录吗？此操作不可恢复！', [
        { text: '取消', style: 'cancel' },
        { text: '确认', style: 'destructive', onPress: () => void handleClearExpenseForecastsConfirm() },
      ])
    }
  }, [handleClearExpenseForecastsConfirm])

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
          <View style={styles.clearButtonsContainer}>
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
            <TouchableOpacity
              style={[styles.clearButton, clearingExpense && styles.clearButtonDisabled]}
              onPress={handleClearExpenseForecasts}
              disabled={clearingExpense}
            >
              {clearingExpense ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Text style={styles.clearButtonText}>清空预测支出表</Text>
              )}
            </TouchableOpacity>
          </View>
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
              {/* 显示查询结果表格 */}
              {rawData[item.id] && rawData[item.id].length > 0 && (() => {
                console.log('[API IMPORT] Rendering table for', item.id, 'with', rawData[item.id].length, 'items')
                const currentData = editedData[item.id] || rawData[item.id].map(processDataItem)
                
                // 计算汇总金额：基于预计应收金额进行汇总
                let confirmedTotal = 0
                let unconfirmedTotal = 0
                
                currentData.forEach((row) => {
                  // 使用预计应收金额（expectedAmount）进行汇总
                  const amount = row.expectedAmount || 0
                  const status = row.incomeStatus || ''
                  
                  if (amount !== 0 && amount !== null && amount !== undefined) {
                    if (status === '已确认') {
                      confirmedTotal += amount
                    } else if (status === '未确认') {
                      unconfirmedTotal += amount
                    }
                  }
                })
                
                const summary = { confirmedTotal, unconfirmedTotal }
                
                const handleAmountChange = (index: number, value: string) => {
                  const newData = [...currentData]
                  const numValue = parseFloat(value.replace(/[¥,]/g, '')) || 0
                  newData[index] = { ...newData[index], expectedAmount: numValue }
                  setEditedData((prev) => ({
                    ...prev,
                    [item.id]: newData,
                  }))
                }
                
                const handleStatusChange = (index: number, value: string) => {
                  const newData = [...currentData]
                  newData[index] = { ...newData[index], incomeStatus: value }
                  setEditedData((prev) => ({
                    ...prev,
                    [item.id]: newData,
                  }))
                }
                
                const handleConfirmConfirm = async () => {
                  setConfirming((prev) => ({ ...prev, [item.id]: true }))
                  try {
                    // 过滤出预计收入非0的数据
                    const dataToImport = currentData.filter((row) => {
                      const amount = row.expectedAmount || 0
                      return amount !== 0 && amount !== null && amount !== undefined
                    })
                    
                    const response = await apiClient.post<{ deleted_count: number; imported_count: number }>(
                      `/api/v1/api-sources/${item.id}/confirm`,
                      { data: dataToImport }
                    )
                    
                    addImportMessage({
                      id: generateId(),
                      role: 'assistant',
                      content: `确认入库完成：删除了 ${response.deleted_count} 条旧记录，导入了 ${response.imported_count} 条新记录。`,
                      createdAt: new Date().toISOString(),
                    })
                    
                    Alert.alert('入库成功', `删除了 ${response.deleted_count} 条旧记录，导入了 ${response.imported_count} 条新记录。`)
                  } catch (error) {
                    console.error('[API IMPORT] confirm error', error)
                    Alert.alert('入库失败', error instanceof Error ? error.message : '未知错误')
                  } finally {
                    setConfirming((prev) => ({ ...prev, [item.id]: false }))
                  }
                }
                
                const handleConfirm = () => {
                  if (Platform.OS === 'web') {
                    if (window.confirm('确认入库将删除所有一级分类为"资产管理"的预计收入数据，然后导入当前数据。确定要继续吗？')) {
                      void handleConfirmConfirm()
                    }
                  } else {
                    Alert.alert('确认入库', '确认入库将删除所有一级分类为"资产管理"的预计收入数据，然后导入当前数据。确定要继续吗？', [
                      { text: '取消', style: 'cancel' },
                      { text: '确认', style: 'destructive', onPress: () => void handleConfirmConfirm() },
                    ])
                  }
                }
                
                return (
                  <View style={styles.rawDataContainer}>
                    <View style={styles.rawDataTitleRow}>
                      <Text style={styles.rawDataTitle}>查询结果 ({rawData[item.id].length} 条)</Text>
                      <View style={styles.summaryRow}>
                        <Text style={styles.summaryText}>
                          已确认: ¥{summary.confirmedTotal.toLocaleString('zh-CN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </Text>
                        <Text style={styles.summaryText}>
                          未确认: ¥{summary.unconfirmedTotal.toLocaleString('zh-CN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </Text>
                      </View>
                    </View>
                    <TouchableOpacity
                      style={[styles.confirmImportButton, confirming[item.id] && styles.confirmImportButtonDisabled]}
                      onPress={handleConfirm}
                      disabled={confirming[item.id]}
                    >
                      {confirming[item.id] ? (
                        <>
                          <ActivityIndicator color="#FFFFFF" size="small" />
                          <Text style={styles.confirmImportButtonText}>入库中...</Text>
                        </>
                      ) : (
                        <Text style={styles.confirmImportButtonText}>确认入库</Text>
                      )}
                    </TouchableOpacity>
                    <View style={styles.tableWrapper}>
                      <ScrollView horizontal showsHorizontalScrollIndicator={true}>
                        <View>
                          {/* 表头 */}
                          <View style={styles.tableHeader}>
                            <View style={[styles.tableHeaderCell, styles.tableCellAssetCode]}>
                              <Text style={styles.tableHeaderText}>资产编码</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellFundName]}>
                              <Text style={styles.tableHeaderText}>基金名称</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellDate]}>
                              <Text style={styles.tableHeaderText}>日期</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellName]}>
                              <Text style={styles.tableHeaderText}>名称</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellCost]}>
                              <Text style={styles.tableHeaderText}>金额</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellCategory1]}>
                              <Text style={styles.tableHeaderText}>类别一级</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellCategory2]}>
                              <Text style={styles.tableHeaderText}>类别二级</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellCategory3]}>
                              <Text style={styles.tableHeaderText}>类别三级</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellExpectedAmount]}>
                              <Text style={styles.tableHeaderText}>预计应收金额</Text>
                            </View>
                            <View style={[styles.tableHeaderCell, styles.tableCellIncomeStatus]}>
                              <Text style={styles.tableHeaderText}>收入确认状态</Text>
                            </View>
                          </View>
                          {/* 数据行 */}
                          <ScrollView showsVerticalScrollIndicator={true} style={styles.tableBodyScrollView}>
                            {currentData.map((row, index) => {
                              const amount = row.expectedAmount || 0
                              const status = row.incomeStatus || ''
                              const isConfirmed = status === '已确认'
                              const isUnconfirmed = status === '未确认'
                              
                              // 根据收入状态和金额设置行背景色
                              let rowStyle = [styles.tableRow]
                              if (index % 2 === 1) {
                                rowStyle.push(styles.tableRowEven)
                              }
                              if (amount !== 0 && amount !== null && amount !== undefined) {
                                if (isConfirmed) {
                                  rowStyle.push(styles.tableRowConfirmed)
                                } else if (isUnconfirmed) {
                                  rowStyle.push(styles.tableRowUnconfirmed)
                                }
                              }
                              
                              return (
                                <View
                                  key={`raw-${item.id}-${index}`}
                                  style={rowStyle}
                                >
                                  <View style={[styles.tableCell, styles.tableCellAssetCode]}>
                                    <Text style={styles.tableCellText}>{String(row.FlareAssetCode || '-')}</Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellFundName]}>
                                    <Text style={styles.tableCellText} numberOfLines={1}>
                                      {String(row.FundName || '-')}
                                    </Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellDate]}>
                                    <Text style={styles.tableCellText}>
                                      {row.Date
                                        ? new Date(row.Date).toLocaleDateString('zh-CN')
                                        : '-'}
                                    </Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellName]}>
                                    <Text style={styles.tableCellText} numberOfLines={1}>
                                      {String(row.name || '-')}
                                    </Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellCost]}>
                                    <Text style={styles.tableCellText}>
                                      {row.cost !== undefined && row.cost !== null
                                        ? `¥${Number(row.cost).toLocaleString('zh-CN', {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2,
                                          })}`
                                        : '-'}
                                    </Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellCategory1]}>
                                    <Text style={styles.tableCellText}>{row.categoryLevel1 || '-'}</Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellCategory2]}>
                                    <Text style={styles.tableCellText}>{row.categoryLevel2 || '-'}</Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellCategory3]}>
                                    <Text style={styles.tableCellText}>{row.categoryLevel3 || '-'}</Text>
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellExpectedAmount]}>
                                    <TextInput
                                      style={styles.tableCellInput}
                                      value={
                                        row.expectedAmount !== undefined && row.expectedAmount !== null
                                          ? Number(row.expectedAmount).toLocaleString('zh-CN', {
                                              minimumFractionDigits: 2,
                                              maximumFractionDigits: 2,
                                            })
                                          : ''
                                      }
                                      onChangeText={(value) => handleAmountChange(index, value)}
                                      keyboardType="numeric"
                                      placeholder="0.00"
                                      placeholderTextColor="#64748B"
                                    />
                                  </View>
                                  <View style={[styles.tableCell, styles.tableCellIncomeStatus]}>
                                    <StatusPicker
                                      value={row.incomeStatus || ''}
                                      onChange={(value) => handleStatusChange(index, value)}
                                      style={styles.statusPickerContainer}
                                    />
                                  </View>
                                </View>
                              )
                            })}
                          </ScrollView>
                        </View>
                      </ScrollView>
                    </View>
                  </View>
                )
              })()}
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
  clearButtonsContainer: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  clearButton: {
    backgroundColor: '#EF4444',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
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
  rawDataContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#1E293B',
    borderRadius: 8,
    gap: 8,
  },
  rawDataTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    flexWrap: 'wrap',
    gap: 8,
  },
  rawDataTitle: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '600',
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 24,
    alignItems: 'center',
  },
  summaryText: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 6,
  },
  tableWrapper: {
    maxHeight: 400,
    borderRadius: 4,
    overflow: 'hidden',
  },
  tableBodyScrollView: {
    maxHeight: 350,
  },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: '#334155',
    borderTopWidth: 1,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: '#475569',
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
  },
  tableHeaderCell: {
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRightWidth: 1,
    borderColor: '#475569',
    justifyContent: 'center',
    alignItems: 'center',
  },
  tableHeaderText: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '600',
  },
  tableRow: {
    flexDirection: 'row',
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#475569',
    backgroundColor: '#0F172A',
  },
  tableRowEven: {
    backgroundColor: '#1E293B',
  },
  tableRowConfirmed: {
    backgroundColor: 'rgba(34, 197, 94, 0.3)', // 绿色背景，更明显
  },
  tableRowUnconfirmed: {
    backgroundColor: 'rgba(249, 115, 22, 0.3)', // 橙色背景，更明显
  },
  tableCell: {
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRightWidth: 1,
    borderColor: '#475569',
    justifyContent: 'center',
  },
  tableCellText: {
    color: '#F8FAFC',
    fontSize: 12,
  },
  tableCellInput: {
    color: '#F8FAFC',
    fontSize: 12,
    padding: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    minWidth: 80,
  },
  statusPickerContainer: {
    flex: 1,
  },
  pickerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    minWidth: 120,
  },
  pickerButtonText: {
    color: '#F8FAFC',
    fontSize: 12,
    flex: 1,
  },
  pickerArrow: {
    color: '#94A3B8',
    fontSize: 10,
    marginLeft: 4,
  },
  pickerModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  pickerModalContent: {
    backgroundColor: '#1E293B',
    borderRadius: 8,
    minWidth: 200,
    maxWidth: 300,
    padding: 8,
  },
  pickerOption: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 4,
    marginBottom: 4,
  },
  pickerOptionSelected: {
    backgroundColor: 'rgba(59, 130, 246, 0.3)',
  },
  pickerOptionText: {
    color: '#F8FAFC',
    fontSize: 14,
  },
  pickerOptionTextSelected: {
    color: '#60A5FA',
    fontWeight: '600',
  },
  tableCellAssetCode: {
    width: 100,
    minWidth: 100,
  },
  tableCellFundName: {
    width: 400,
    minWidth: 400,
  },
  tableCellDate: {
    width: 100,
    minWidth: 100,
  },
  tableCellName: {
    width: 180,
    minWidth: 180,
  },
  tableCellCost: {
    width: 120,
    minWidth: 120,
  },
  tableCellCategory1: {
    width: 100,
    minWidth: 100,
  },
  tableCellCategory2: {
    width: 100,
    minWidth: 100,
  },
  tableCellCategory3: {
    width: 120,
    minWidth: 120,
  },
  tableCellCategory4: {
    width: 300,
    minWidth: 300,
  },
  tableCellExpectedAmount: {
    width: 140,
    minWidth: 140,
  },
  tableCellIncomeStatus: {
    width: 140,
    minWidth: 140,
  },
  confirmImportButton: {
    marginTop: 12,
    backgroundColor: '#22C55E',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  confirmImportButtonDisabled: {
    opacity: 0.7,
  },
  confirmImportButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
})

