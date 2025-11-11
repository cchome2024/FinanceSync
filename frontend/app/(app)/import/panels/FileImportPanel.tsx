import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native'
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

const generateId = () => Math.random().toString(36).slice(2)

type FileImportConfig = {
  watch_path: string
  path_exists: boolean
  file_count: number
}

export function FileImportPanel() {
  const [selectedFiles, setSelectedFiles] = useState<DocumentPicker.DocumentPickerAsset[]>([])
  const [isPickingFile, setIsPickingFile] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [config, setConfig] = useState<FileImportConfig>({ watch_path: '', path_exists: false, file_count: 0 })
  const [configPath, setConfigPath] = useState('')
  const [savingConfig, setSavingConfig] = useState(false)

  const { addImportMessage, setImportPreview, setCurrentJobId } = useFinanceStore()

  // 加载配置
  const loadConfig = useCallback(async () => {
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/file-import/config`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      })
      if (response.ok) {
        const data: FileImportConfig = await response.json()
        setConfig(data)
        setConfigPath(data.watch_path)
      }
    } catch (error) {
      console.error('[FILE IMPORT] load config error', error)
    }
  }, [])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const handlePickFiles = useCallback(async () => {
    try {
      setIsPickingFile(true)
      const result = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true,
        multiple: true,
      })
      if (!('canceled' in result && result.canceled) && result.assets && result.assets.length > 0) {
        setSelectedFiles((prev) => [...prev, ...result.assets])
      }
    } catch (error) {
      console.error('[FILE IMPORT] pick file failed', error)
      Alert.alert('选择文件失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setIsPickingFile(false)
    }
  }, [])

  const handleRemoveFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleScanPath = useCallback(async () => {
    if (!config.watch_path) {
      Alert.alert('提示', '请先配置文件路径')
      return
    }

    if (!config.path_exists) {
      Alert.alert('错误', '配置的路径不存在')
      return
    }
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/file-import/scan`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
        },
      })

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = `扫描失败: ${response.status}`
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.detail || errorMessage
        } catch {
          errorMessage = errorText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const result: ParseJobResponse = await response.json()
      console.log('[FILE IMPORT] Scan response:', result)
      setCurrentJobId(result.jobId)
      const previewRecords = result.preview.map((record, index) => ({
        id: `${result.jobId}-${index}`,
        recordType: record.recordType,
        payload: record.payload,
        confidence: record.confidence,
        warnings: record.warnings ?? [],
      }))
      setImportPreview(previewRecords)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `扫描路径完成，识别到 ${result.preview.length} 条记录。请在下方候选记录列表中确认内容。`,
        createdAt: new Date().toISOString(),
      })

      if (result.preview.length === 0) {
        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: '没有识别到结构化记录，请检查文件格式和内容。Excel文件需要包含"总收入"工作表。',
          createdAt: new Date().toISOString(),
        })
      }

      // 刷新配置以更新文件数量
      await loadConfig()
    } catch (error) {
      console.error('[FILE IMPORT] scan error', error)
      Alert.alert('扫描失败', error instanceof Error ? error.message : '未知错误')
      throw error // 重新抛出错误，让调用者处理
    }
  }, [config, addImportMessage, setImportPreview, setCurrentJobId, loadConfig])

  const handleParse = useCallback(async () => {
    // 如果有手动选择的文件，优先解析手动选择的文件
    if (selectedFiles.length > 0) {
      console.log('[FILE IMPORT] Starting parse, files:', selectedFiles.length)
    } else if (config.path_exists && config.file_count > 0) {
      // 如果没有手动选择的文件，但配置了路径且有文件，则扫描路径
      console.log('[FILE IMPORT] No files selected, scanning configured path')
      setParsing(true)
      try {
        await handleScanPath()
      } finally {
        setParsing(false)
      }
      return
    } else {
      Alert.alert('提示', '请先选择文件或配置固定文件路径')
      return
    }

    setParsing(true)
    try {
      const formData = new FormData()
      for (const file of selectedFiles) {
        console.log('[FILE IMPORT] Processing file:', file.name, 'Platform:', Platform.OS)
        // 根据平台选择不同的文件格式
        if (Platform.OS === 'web') {
          // Web环境：需要读取文件内容
          if (file.file) {
            console.log('[FILE IMPORT] Using file.file for web')
            formData.append('files', file.file, file.name ?? 'upload')
          } else if (file.uri) {
            // 如果没有file对象，尝试从URI读取
            console.log('[FILE IMPORT] Fetching file from URI:', file.uri)
            try {
              const response = await fetch(file.uri)
              const blob = await response.blob()
              formData.append('files', blob, file.name ?? 'upload')
            } catch (fetchError) {
              console.error('[FILE IMPORT] Failed to fetch file from URI:', fetchError)
              throw new Error(`无法读取文件 ${file.name}: ${fetchError instanceof Error ? fetchError.message : '未知错误'}`)
            }
          } else {
            throw new Error(`文件 ${file.name} 缺少必要的文件数据`)
          }
        } else {
          // React Native环境：使用uri格式
          console.log('[FILE IMPORT] Using uri format for React Native')
          const fileData = {
            uri: file.uri,
            name: file.name ?? 'upload',
            type: file.mimeType ?? 'application/octet-stream',
          } as unknown as Blob
          formData.append('files', fileData)
        }
      }

      console.log('[FILE IMPORT] FormData created, sending request...')

      // 直接使用fetch，因为apiClient可能不支持FormData的复杂格式
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const url = `${baseURL}/api/v1/parse/file`
      console.log('[FILE IMPORT] Sending request to:', url)
      
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        // 不要手动设置Content-Type，让浏览器自动设置multipart/form-data边界
        headers: {
          Accept: 'application/json',
        },
      })

      console.log('[FILE IMPORT] Response status:', response.status, response.statusText)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('[FILE IMPORT] Error response:', errorText)
        let errorMessage = `解析失败: ${response.status}`
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.detail || errorMessage
        } catch {
          errorMessage = errorText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const result: ParseJobResponse = await response.json()
      console.log('[FILE IMPORT] Success response:', result)
      setCurrentJobId(result.jobId)
      const previewRecords = result.preview.map((record, index) => ({
        id: `${result.jobId}-${index}`,
        recordType: record.recordType,
        payload: record.payload,
        confidence: record.confidence,
        warnings: record.warnings ?? [],
      }))
      setImportPreview(previewRecords)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `文件解析完成，识别到 ${result.preview.length} 条记录。请在下方候选记录列表中确认内容。`,
        createdAt: new Date().toISOString(),
      })

      if (result.preview.length === 0) {
        addImportMessage({
          id: generateId(),
          role: 'assistant',
          content: '没有识别到结构化记录，请检查文件格式和内容。Excel文件需要包含"总收入"工作表。',
          createdAt: new Date().toISOString(),
        })
      }
    } catch (error) {
      console.error('[FILE IMPORT] parse error', error)
      Alert.alert('解析失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setParsing(false)
    }
  }, [selectedFiles, config, handleScanPath, addImportMessage, setImportPreview, setCurrentJobId])

  const handleClearRevenueConfirm = useCallback(async () => {
    setClearing(true)
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/revenue-details`, {
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
      console.log('[FILE IMPORT] Clear revenue response:', result)

      addImportMessage({
        id: generateId(),
        role: 'assistant',
        content: `已清空 ${result.deleted_count} 条收入明细记录。`,
        createdAt: new Date().toISOString(),
      })

      Alert.alert('清空成功', `已清空 ${result.deleted_count} 条收入明细记录。`)
    } catch (error) {
      console.error('[FILE IMPORT] clear revenue error', error)
      Alert.alert('清空失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setClearing(false)
    }
  }, [addImportMessage])

  const handleClearRevenue = useCallback(() => {
    if (Platform.OS === 'web') {
      if (window.confirm('确定要清空所有收入明细记录吗？此操作不可恢复！')) {
        void handleClearRevenueConfirm()
      }
    } else {
      Alert.alert('确认清空', '确定要清空所有收入明细记录吗？此操作不可恢复！', [
        { text: '取消', style: 'cancel' },
        { text: '确认', style: 'destructive', onPress: () => void handleClearRevenueConfirm() },
      ])
    }
  }, [handleClearRevenueConfirm])

  const handleScanPathDirect = useCallback(async () => {
    setScanning(true)
    try {
      await handleScanPath()
    } catch (error) {
      // 错误已在handleScanPath中处理
    } finally {
      setScanning(false)
    }
  }, [handleScanPath])

  const handleSaveConfig = useCallback(async () => {
    setSavingConfig(true)
    try {
      const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
      const response = await fetch(`${baseURL}/api/v1/file-import/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ watch_path: configPath }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = `保存失败: ${response.status}`
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.detail || errorMessage
        } catch {
          errorMessage = errorText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const data: FileImportConfig = await response.json()
      console.log('[FILE IMPORT] Config saved:', data)
      setConfig(data)
      setConfigPath(data.watch_path) // 确保输入框也更新
      console.log('[FILE IMPORT] Config state updated, path_exists:', data.path_exists, 'file_count:', data.file_count)
      Alert.alert('保存成功', `已保存文件路径配置${data.path_exists ? `，找到 ${data.file_count} 个文件` : ''}`)
    } catch (error) {
      console.error('[FILE IMPORT] save config error', error)
      Alert.alert('保存失败', error instanceof Error ? error.message : '未知错误')
    } finally {
      setSavingConfig(false)
    }
  }, [configPath])

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <View style={styles.container}>
      <View style={styles.description}>
        <View style={styles.descriptionHeader}>
          <Text style={styles.descriptionText}>上传 Excel 格式的收入数据文件</Text>
          <TouchableOpacity
            style={[styles.clearButton, clearing && styles.clearButtonDisabled]}
            onPress={handleClearRevenue}
            disabled={clearing}
          >
            {clearing ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <Text style={styles.clearButtonText}>清空收入表</Text>
            )}
          </TouchableOpacity>
        </View>
        <Text style={styles.descriptionHint}>
          • Excel文件需包含"总收入"工作表{'\n'}
          • 支持列：公司、发生日期、收入金额、款项内容、对方名称、到账账户、大类、二类、费用类型、月份、收入(万){'\n'}
          • 支持格式：.xlsx, .xls
        </Text>
      </View>

      {/* 固定路径配置区域 */}
      <View style={styles.configSection}>
        <View style={styles.configTitleRow}>
          <Text style={styles.configTitle}>固定文件路径配置</Text>
        </View>
        <Text style={styles.configHintText}>
          💡 可以配置文件路径（如：/Users/mac/Desktop/1.xlsx）或目录路径（如：/Users/mac/Desktop）。配置文件路径时直接读取该文件，配置目录路径时扫描目录下所有Excel文件。
        </Text>
        <View style={styles.configInputRow}>
          <TextInput
            style={styles.configInput}
            placeholder="输入文件路径或目录路径，例如：/Users/mac/Desktop/1.xlsx 或 /Users/mac/Desktop"
            placeholderTextColor="#6B7280"
            value={configPath}
            onChangeText={setConfigPath}
            editable={!savingConfig}
          />
          <TouchableOpacity
            style={[styles.saveConfigButton, savingConfig && styles.saveConfigButtonDisabled]}
            onPress={handleSaveConfig}
            disabled={savingConfig}
          >
            {savingConfig ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <Text style={styles.saveConfigButtonText}>保存</Text>
            )}
          </TouchableOpacity>
        </View>
        {config.watch_path && (
          <View style={styles.configStatus}>
            <Text style={styles.configStatusText}>
              路径：{config.watch_path}
            </Text>
            <Text
              style={[
                styles.configStatusText,
                config.path_exists ? styles.configStatusSuccess : styles.configStatusError,
              ]}
            >
              {config.path_exists ? `✓ 路径存在，找到 ${config.file_count} 个文件` : '✗ 路径不存在'}
            </Text>
          </View>
        )}
        {config.path_exists && config.file_count > 0 && (
          <View style={styles.configHint}>
            <Text style={styles.configHintText}>
              💡 已配置路径，找到 {config.file_count} 个文件。可以直接点击"开始解析"按钮导入，无需手动选择文件。
            </Text>
          </View>
        )}
      </View>

      <View style={styles.divider} />

      <View style={styles.filePickerSection}>
        {/* 并排显示两个按钮 */}
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.filePickerButton, (parsing || isPickingFile) && styles.filePickerButtonDisabled]}
            onPress={handlePickFiles}
            disabled={parsing || isPickingFile}
          >
            {isPickingFile ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.filePickerButtonText}>📁 选择文件</Text>
            )}
          </TouchableOpacity>

          {(() => {
            const canParse = selectedFiles.length > 0 || (config.path_exists && config.file_count > 0)
            return (
              <TouchableOpacity
                style={[
                  styles.parseButton,
                  (!canParse || parsing || scanning) && styles.parseButtonDisabled,
                ]}
                onPress={handleParse}
                disabled={!canParse || parsing || scanning}
              >
                {parsing || scanning ? (
                  <>
                    <ActivityIndicator color="#FFFFFF" />
                    <Text style={styles.parseButtonText}>解析中...</Text>
                  </>
                ) : (
                  <Text style={styles.parseButtonText}>
                    {selectedFiles.length > 0
                      ? `开始解析 (${selectedFiles.length} 个文件)`
                      : config.path_exists && config.file_count > 0
                      ? `开始解析 (路径: ${config.file_count} 个文件)`
                      : '开始解析'}
                  </Text>
                )}
              </TouchableOpacity>
            )
          })()}
        </View>

        {selectedFiles.length > 0 && (
          <View style={styles.fileList}>
            {selectedFiles.map((file, index) => (
              <View key={index} style={styles.fileItem}>
                <View style={styles.fileItemInfo}>
                  <Text style={styles.fileItemName} numberOfLines={1}>
                    {file.name ?? '未命名文件'}
                  </Text>
                  <Text style={styles.fileItemSize}>{formatFileSize(file.size)}</Text>
                </View>
                <TouchableOpacity
                  style={styles.fileItemRemove}
                  onPress={() => handleRemoveFile(index)}
                  disabled={parsing}
                >
                  <Text style={styles.fileItemRemoveText}>移除</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    gap: 16,
  },
  description: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  descriptionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  descriptionText: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
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
  filePickerSection: {
    gap: 16,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'stretch',
  },
  filePickerButton: {
    flex: 1,
    backgroundColor: '#3B82F6',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  filePickerButtonDisabled: {
    opacity: 0.7,
  },
  filePickerButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  fileList: {
    gap: 12,
  },
  fileItem: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  fileItemInfo: {
    flex: 1,
    gap: 4,
  },
  fileItemName: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '500',
  },
  fileItemSize: {
    color: '#94A3B8',
    fontSize: 12,
  },
  fileItemRemove: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  fileItemRemoveText: {
    color: '#F87171',
    fontSize: 13,
    fontWeight: '500',
  },
  parseButton: {
    flex: 1,
    backgroundColor: '#22C55E',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  parseButtonDisabled: {
    backgroundColor: '#475569',
    opacity: 0.6,
  },
  parseButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  configSection: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  configTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  configTitle: {
    color: '#E2E8F0',
    fontSize: 14,
    fontWeight: '600',
  },
  configHintText: {
    color: '#94A3B8',
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 4,
  },
  configInputRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  configInput: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#E2E8F0',
    fontSize: 14,
  },
  saveConfigButton: {
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  saveConfigButtonDisabled: {
    opacity: 0.7,
  },
  saveConfigButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  configStatus: {
    gap: 4,
  },
  configStatusText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  configStatusSuccess: {
    color: '#22C55E',
  },
  configStatusError: {
    color: '#EF4444',
  },
  scanButton: {
    backgroundColor: '#22C55E',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  scanButtonDisabled: {
    opacity: 0.7,
  },
  configHint: {
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.2)',
  },
  configHintText: {
    color: '#60A5FA',
    fontSize: 12,
    lineHeight: 18,
  },
  divider: {
    height: 1,
    backgroundColor: 'rgba(148, 163, 184, 0.1)',
    marginVertical: 8,
  },
})

