import { memo } from 'react'
import { FlatList, StyleSheet, Text, View } from 'react-native'

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
      return '收入预测'
    default:
      return recordType
  }
}

const ImportPreviewComponent = ({ records }: Props) => {
  if (records.length === 0) {
    return null
  }

  return (
    <View style={styles.wrapper}>
      <Text style={styles.heading}>候选记录</Text>
      <FlatList
        data={records}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{getTitle(item.recordType)}</Text>
              {item.confidence != null && (
                <Text style={styles.badge}>可信度 {(item.confidence * 100).toFixed(0)}%</Text>
              )}
            </View>
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
        )}
      />
    </View>
  )
}

export const ImportPreview = memo(ImportPreviewComponent)

const styles = StyleSheet.create({
  wrapper: {
    marginTop: 24,
    width: '100%',
  },
  heading: {
    color: '#F5F7FF',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 12,
  },
  card: {
    backgroundColor: '#161D2E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  badge: {
    backgroundColor: 'rgba(59, 130, 246, 0.18)',
    color: '#60A5FA',
    fontSize: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  cardContent: {
    color: '#CBD5F5',
    fontSize: 14,
    lineHeight: 20,
  },
  warningBox: {
    marginTop: 12,
    borderLeftColor: '#FBBF24',
    borderLeftWidth: 3,
    paddingLeft: 10,
  },
  warningText: {
    color: '#FDE68A',
    fontSize: 13,
  },
})

