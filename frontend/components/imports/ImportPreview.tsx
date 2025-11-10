import { memo, useMemo, useState } from 'react'
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import type { ImportPreviewRecord } from '@/src/state/financeStore'

type Props = {
  records: ImportPreviewRecord[]
}

function formatRecord(record: Record<string, unknown>): string {
  return Object.entries(record)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join('\n')
}

function getTitle(recordType: ImportPreviewRecord['recordType']): string {
  switch (recordType) {
    case 'account_balance':
      return '账户余额'
    case 'revenue':
      return '收入记录'
    case 'expense':
      return '支出记录'
    case 'income_forecast':
    case 'revenue_forecast':
      return '收入预测'
    default:
      return recordType
  }
}

const ImportPreviewComponent = ({ records }: Props) => {
  if (records.length === 0) {
    return null
  }

  const grouped = useMemo(() => {
    const map = new Map<ImportPreviewRecord['recordType'], ImportPreviewRecord[]>()
    records.forEach((record) => {
      const list = map.get(record.recordType) ?? []
      list.push(record)
      map.set(record.recordType, list)
    })
    return Array.from(map.entries())
  }, [records])

  const [expandedTypes, setExpandedTypes] = useState<Record<ImportPreviewRecord['recordType'], boolean>>({
    account_balance: false,
    revenue: false,
    expense: false,
    income_forecast: false,
    revenue_forecast: false,
  })

  const toggleType = (type: ImportPreviewRecord['recordType']) => {
    setExpandedTypes((prev) => ({ ...prev, [type]: !prev[type] }))
  }

  return (
    <View style={styles.wrapper}>
      <Text style={styles.heading}>候选记录概览（共 {records.length} 条）</Text>
      {grouped.map(([type, items]) => {
        const expanded = expandedTypes[type]
        const limited = items.slice(0, 3)
        return (
          <View key={type} style={styles.groupCard}>
            <View style={styles.groupHeader}>
              <View>
                <Text style={styles.groupTitle}>{getTitle(type)}</Text>
                <Text style={styles.groupSubTitle}>共 {items.length} 条</Text>
              </View>
              <TouchableOpacity onPress={() => toggleType(type)}>
                <Text style={styles.groupAction}>{expanded ? '收起详情' : '查看详情'}</Text>
              </TouchableOpacity>
            </View>
            {expanded && (
              <View style={styles.groupContent}>
                {limited.map((item) => (
                  <View key={item.id} style={styles.detailCard}>
                    {item.confidence != null && (
                      <Text style={styles.badge}>可信度 {(item.confidence * 100).toFixed(0)}%</Text>
                    )}
                    <Text style={styles.cardContent}>{formatRecord(item.payload)}</Text>
                    {!!item.warnings?.length && (
                      <View style={styles.warningBox}>
                        {item.warnings.map((warning) => (
                          <Text key={warning} style={styles.warningText}>
                            ⚠ {warning}
                          </Text>
                        ))}
                      </View>
                    )}
                  </View>
                ))}
                {items.length > limited.length && (
                  <Text style={styles.moreHint}>仅展示前 {limited.length} 条，其余请确认后保存。</Text>
                )}
              </View>
            )}
          </View>
        )
      })}
    </View>
  )
}

export const ImportPreview = memo(ImportPreviewComponent)

const styles = StyleSheet.create({
  wrapper: {
    marginTop: 24,
    width: '100%',
    gap: 12,
  },
  heading: {
    color: '#F5F7FF',
    fontSize: 18,
    fontWeight: '700',
  },
  groupCard: {
    backgroundColor: '#161D2E',
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  groupHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  groupTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  groupSubTitle: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 4,
  },
  groupAction: {
    color: '#60A5FA',
    fontSize: 13,
  },
  groupContent: {
    gap: 12,
  },
  detailCard: {
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    borderRadius: 12,
    padding: 12,
    gap: 6,
  },
  badge: {
    backgroundColor: 'rgba(59, 130, 246, 0.18)',
    color: '#60A5FA',
    fontSize: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    alignSelf: 'flex-start',
  },
  cardContent: {
    color: '#CBD5F5',
    fontSize: 14,
    lineHeight: 20,
  },
  warningBox: {
    marginTop: 8,
    borderLeftColor: '#FBBF24',
    borderLeftWidth: 3,
    paddingLeft: 10,
  },
  warningText: {
    color: '#FDE68A',
    fontSize: 13,
  },
  moreHint: {
    color: '#94A3B8',
    fontSize: 12,
  },
})

