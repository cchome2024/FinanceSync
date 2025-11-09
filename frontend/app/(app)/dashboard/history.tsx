import { useEffect, useState } from 'react'
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { apiClient } from '@/src/services/apiClient'

type BalanceRecord = {
  companyId: string
  reportedAt: string
  totalBalance: number
  cashBalance: number
  investmentBalance: number
  currency: string
}

export default function BalanceHistoryScreen() {
  const [records, setRecords] = useState<BalanceRecord[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      try {
        const response = await apiClient.get<BalanceRecord[]>('/api/v1/financial/balances')
        setRecords(response)
      } catch (error) {
        console.error('[DASHBOARD] load balance history failed', error)
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.title}>账户余额历史</Text>
        <Text style={styles.subtitle}>展示各公司按时间排序的历史余额记录。</Text>

        {loading && (
          <View style={styles.loading}>
            <ActivityIndicator color="#60A5FA" />
            <Text style={styles.loadingText}>正在加载历史数据...</Text>
          </View>
        )}

        {!loading && (
          <FlatList
            data={records}
            keyExtractor={(item, index) => `${item.companyId}-${item.reportedAt}-${index}`}
            renderItem={({ item }) => (
              <View style={styles.record}>
                <Text style={styles.recordTitle}>{item.companyId || '未指定公司'}</Text>
                <Text style={styles.recordMeta}>{new Date(item.reportedAt).toLocaleString()}</Text>
                <Text style={styles.recordValue}>
                  总余额 {item.totalBalance.toLocaleString()} {item.currency}
                </Text>
                <Text style={styles.recordDetail}>
                  现金 {item.cashBalance.toLocaleString()} · 理财 {item.investmentBalance.toLocaleString()}
                </Text>
              </View>
            )}
            ListEmptyComponent={<Text style={styles.empty}>暂时没有历史记录。</Text>}
          />
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
    paddingBottom: 16,
  },
  title: {
    color: '#FFFFFF',
    fontSize: 24,
    fontWeight: '700',
    marginTop: 12,
  },
  subtitle: {
    color: '#94A3B8',
    fontSize: 14,
    marginTop: 6,
    marginBottom: 16,
  },
  loading: {
    marginTop: 32,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 8,
    color: '#CBD5F5',
  },
  record: {
    backgroundColor: '#131A2B',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  recordTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '600',
  },
  recordMeta: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 4,
  },
  recordValue: {
    color: '#60A5FA',
    fontSize: 16,
    fontWeight: '600',
    marginTop: 10,
  },
  recordDetail: {
    color: '#CBD5F5',
    marginTop: 4,
  },
  empty: {
    color: '#94A3B8',
    marginTop: 32,
    textAlign: 'center',
  },
})


