import { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Link, useFocusEffect } from 'expo-router'

import FinancialTrends, { TrendDatum } from '@/components/charts/FinancialTrends'
import { apiClient } from '@/src/services/apiClient'

type BalanceSummary = {
  cash: number
  investment: number
  total: number
}

type FlowSummary = {
  period: string
  amount: number
  currency: string
}

type ForecastSummary = {
  certain: number
  uncertain: number
}

type CompanyOverview = {
  companyId: string
  companyName: string
  balances?: BalanceSummary | null
  revenue?: FlowSummary | null
  expense?: FlowSummary | null
  forecast?: ForecastSummary | null
}

type FinancialOverviewResponse = {
  asOf: string
  companies: CompanyOverview[]
}

export default function DashboardScreen() {
  const [data, setData] = useState<FinancialOverviewResponse | null>(null)
  const [companyId, setCompanyId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (companyId) {
        params.companyId = companyId
      }
      const query = new URLSearchParams(params).toString()
      const path = query ? `/api/v1/financial/overview?${query}` : '/api/v1/financial/overview'
      const response = await apiClient.get<FinancialOverviewResponse>(path)
      setData(response)
    } catch (error) {
      console.error('[DASHBOARD] load overview failed', error)
    } finally {
      setLoading(false)
    }
  }, [companyId])

useEffect(() => {
  loadOverview()
}, [loadOverview])

useFocusEffect(
  useCallback(() => {
    loadOverview()
  }, [loadOverview])
)

  const companies = data?.companies ?? []

  const currentCompany = useMemo(() => {
    if (!companyId) {
      return companies[0]
    }
    return companies.find((item) => item.companyId === companyId) ?? companies[0]
  }, [companies, companyId])

  const revenueVsExpense: TrendDatum[] = useMemo(() => {
    if (!currentCompany) {
      return []
    }
    const values: TrendDatum[] = []
    if (currentCompany.revenue) {
      values.push({ label: `收入(${currentCompany.revenue.period})`, value: currentCompany.revenue.amount })
    }
    if (currentCompany.expense) {
      values.push({ label: `支出(${currentCompany.expense.period})`, value: currentCompany.expense.amount })
    }
    if (currentCompany.forecast) {
      values.push({ label: '确定预期', value: currentCompany.forecast.certain })
      values.push({ label: '非确定预期', value: currentCompany.forecast.uncertain })
    }
    return values
  }, [currentCompany])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>财务概览</Text>
            <Text style={styles.subtitle}>{data ? `数据截至 ${data.asOf}` : '加载中...'}</Text>
          </View>
          <View style={styles.links}>
            <Link href="/(app)/ai-chat" style={styles.link}>
              数据录入
            </Link>
            <Link href="/(app)/analysis" style={styles.link}>
              查询分析
            </Link>
            <Link href="/(app)/history" style={styles.link}>
              历史记录
            </Link>
          </View>
        </View>

        <ScrollView contentContainerStyle={styles.scrollContent}>
          <View style={styles.filterBar}>
            {companies.map((company) => (
              <TouchableOpacity
                key={company.companyId}
                style={[
                  styles.filterChip,
                  company.companyId === (currentCompany?.companyId ?? null) ? styles.filterChipActive : null,
                ]}
                onPress={() => setCompanyId(company.companyId)}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    company.companyId === (currentCompany?.companyId ?? null) ? styles.filterChipTextActive : null,
                  ]}
                >
                  {company.companyName}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator color="#60A5FA" />
              <Text style={styles.loadingText}>正在加载概览数据...</Text>
            </View>
          )}

          {!loading && currentCompany && (
            <View style={styles.cards}>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>账户余额</Text>
                {currentCompany.balances ? (
                  <>
                    <Text style={styles.cardMetric}>{currentCompany.balances.total.toLocaleString()} 元</Text>
                    <Text style={styles.cardDetail}>
                      现金 {currentCompany.balances.cash.toLocaleString()} · 理财{' '}
                      {currentCompany.balances.investment.toLocaleString()}
                    </Text>
                  </>
                ) : (
                  <Text style={styles.cardDetail}>暂无余额数据</Text>
                )}
                <View style={styles.cardFooter}>
                  <Text style={styles.cardHint}>当前显示最新数据</Text>
                  <Link href="/(app)/dashboard/history" style={styles.cardLink}>
                    查看历史
                  </Link>
                </View>
              </View>

              <View style={styles.card}>
                <Text style={styles.cardTitle}>预测现金流</Text>
                {currentCompany.forecast ? (
                  <>
                    <Text style={styles.cardMetric}>
                      确定 {currentCompany.forecast.certain.toLocaleString()} 元 · 非确定{' '}
                      {currentCompany.forecast.uncertain.toLocaleString()} 元
                    </Text>
                  </>
                ) : (
                  <Text style={styles.cardDetail}>暂无预测数据</Text>
                )}
              </View>
            </View>
          )}

          {!loading && <FinancialTrends title="收入 / 支出 / 预期对比" data={revenueVsExpense} />}
        </ScrollView>
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
    marginBottom: 12,
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
  scrollContent: {
    paddingBottom: 32,
  },
  filterBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 12,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: 'rgba(96, 165, 250, 0.12)',
  },
  filterChipActive: {
    backgroundColor: '#3B82F6',
  },
  filterChipText: {
    color: '#60A5FA',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  loadingContainer: {
    marginTop: 32,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 8,
    color: '#CBD5F5',
  },
  cards: {
    flexDirection: 'row',
    gap: 16,
    flexWrap: 'wrap',
  },
  card: {
    flexBasis: '48%',
    backgroundColor: '#131A2B',
    padding: 16,
    borderRadius: 16,
    marginTop: 12,
  },
  cardTitle: {
    color: '#94A3B8',
    fontSize: 14,
    marginBottom: 6,
  },
  cardMetric: {
    color: '#F8FAFC',
    fontSize: 18,
    fontWeight: '600',
  },
  cardDetail: {
    color: '#CBD5F5',
    marginTop: 6,
  },
  cardFooter: {
    marginTop: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardHint: {
    color: '#94A3B8',
    fontSize: 12,
  },
  cardLink: {
    color: '#60A5FA',
    fontSize: 12,
  },
})


