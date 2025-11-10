import { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useFocusEffect } from 'expo-router'

import { apiClient } from '@/src/services/apiClient'
import { NavLink } from '@/components/common/NavLink'

type BalanceSummary = {
  cash: number
  investment: number
  total: number
  reportedAt: string
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

type RevenueSummaryNode = {
  label: string
  level: number
  monthly: number[]
  total: number
  children?: RevenueSummaryNode[]
}

type RevenueSummaryResponse = {
  year: number
  companyId?: string | null
  totals: {
    monthly: number[]
    total: number
  }
  nodes: RevenueSummaryNode[]
}

export default function DashboardScreen() {
  const [data, setData] = useState<FinancialOverviewResponse | null>(null)
  const [companyId, setCompanyId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [revenueSummary, setRevenueSummary] = useState<RevenueSummaryResponse | null>(null)
  const [revenueYear, setRevenueYear] = useState(new Date().getFullYear())
  const [revenueLevel, setRevenueLevel] = useState(2)
  const [loadingRevenue, setLoadingRevenue] = useState(false)

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

  const loadRevenueSummary = useCallback(async () => {
    setLoadingRevenue(true)
    try {
      const params: Record<string, string> = { year: String(revenueYear), maxLevel: String(revenueLevel) }
      if (companyId) {
        params.companyId = companyId
      }
      const query = new URLSearchParams(params).toString()
      const response = await apiClient.get<RevenueSummaryResponse>(`/api/v1/financial/revenue-summary?${query}`)
      setRevenueSummary(response)
    } catch (error) {
      console.error('[DASHBOARD] load revenue summary failed', error)
      setRevenueSummary(null)
    } finally {
      setLoadingRevenue(false)
    }
  }, [companyId, revenueYear, revenueLevel])

  useEffect(() => {
    loadOverview()
    loadRevenueSummary()
  }, [loadOverview, loadRevenueSummary])

useFocusEffect(
  useCallback(() => {
    loadOverview()
    loadRevenueSummary()
  }, [loadOverview, loadRevenueSummary])
)

  const companies = data?.companies ?? []

  const currentCompany = useMemo(() => {
    if (!companyId) {
      return companies[0]
    }
    return companies.find((item) => item.companyId === companyId) ?? companies[0]
  }, [companies, companyId])

  const currentYear = useMemo(() => new Date().getFullYear(), [])
  const yearOptions = useMemo(() => [currentYear, currentYear - 1, currentYear - 2], [currentYear])

  const revenueRows = useMemo(() => {
    if (!revenueSummary) {
      return []
    }

    const rows: Array<{ key: string; label: string; depth: number; monthly: number[]; total: number }> = []

    const traverse = (nodes: RevenueSummaryNode[], parentKey = '') => {
      nodes.forEach((node, index) => {
        const key = `${parentKey}${node.label}-${index}`
        const depth = Math.max(0, node.level - 1)
        rows.push({ key, label: node.label, depth, monthly: node.monthly, total: node.total })
        if (node.children && node.children.length > 0) {
          traverse(node.children, `${key}>`)
        }
      })
    }

    traverse(revenueSummary.nodes)
    return rows
  }, [revenueSummary])

  const formatAmount = useCallback((value: number) => {
    if (value === 0) {
      return ''
    }
    return (value / 10000).toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  }, [])

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>财务概览</Text>
            <Text style={styles.subtitle}>{data ? `数据截至 ${data.asOf}` : '加载中...'}</Text>
          </View>
          <View style={styles.links}>
            <NavLink href="/(app)/ai-chat" label="数据录入" textStyle={styles.link} />
            <NavLink href="/(app)/analysis" label="查询分析" textStyle={styles.link} />
            <NavLink href="/(app)/history" label="历史记录" textStyle={styles.link} />
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
                    <Text style={styles.cardMeta}>截至 {currentCompany.balances.reportedAt}</Text>
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
                  <NavLink href="/(app)/dashboard/history" label="查看历史" textStyle={styles.cardLink} />
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

          <View style={styles.revenueSection}>
            <View style={styles.revenueHeader}>
              <Text style={styles.sectionTitle}>收入汇总</Text>
              <View style={styles.revenueControls}>
                <View style={styles.yearSelector}>
                  {yearOptions.map((year) => (
                    <TouchableOpacity
                      key={year}
                      style={[styles.yearChip, revenueYear === year && styles.yearChipActive]}
                      onPress={() => setRevenueYear(year)}
                      disabled={loadingRevenue}
                    >
                      <Text style={revenueYear === year ? styles.yearChipTextActive : styles.yearChipText}>{year} 年</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <View style={styles.levelSelector}>
                  {[1, 2, 3].map((level) => (
                    <TouchableOpacity
                      key={level}
                      style={[styles.levelChip, revenueLevel === level && styles.levelChipActive]}
                      onPress={() => setRevenueLevel(level)}
                      disabled={loadingRevenue}
                    >
                      <Text style={revenueLevel === level ? styles.levelChipTextActive : styles.levelChipText}>{`${level} 级`}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
            {loadingRevenue && (
              <View style={styles.loadingContainer}>
                <ActivityIndicator color="#60A5FA" />
                <Text style={styles.loadingText}>正在加载收入汇总...</Text>
              </View>
            )}
            {!loadingRevenue && revenueSummary && revenueRows.length > 0 && (
              <ScrollView horizontal style={styles.revenueTableContainer}>
                <View>
                  <Text style={styles.unitHint}>单位：万元</Text>
                  <View style={[styles.tableRow, styles.tableHeaderRow]}>
                    <Text style={[styles.tableHeaderCell, styles.labelColumn]}>分类</Text>
                    {Array.from({ length: 12 }, (_, index) => (
                      <Text key={`month-${index}`} style={styles.tableHeaderCell}>
                        {index + 1} 月
                      </Text>
                    ))}
                    <Text style={[styles.tableHeaderCell, styles.totalColumn]}>合计</Text>
                  </View>
                  {revenueRows.map((row) => (
                    <View key={row.key} style={styles.tableRow}>
                      <Text style={[styles.tableCell, styles.labelColumn, { paddingLeft: 16 + row.depth * 16 }]}>
                        {row.label}
                      </Text>
                      {row.monthly.map((value, idx) => (
                        <Text key={`${row.key}-m-${idx}`} style={styles.tableCell}>
                          {formatAmount(value)}
                        </Text>
                      ))}
                      <Text style={[styles.tableCell, styles.totalColumn]}>{formatAmount(row.total)}</Text>
                    </View>
                  ))}
                  <View style={[styles.tableRow, styles.tableTotalRow]}>
                    <Text style={[styles.tableCell, styles.labelColumn]}>合计</Text>
                    {revenueSummary.totals.monthly.map((value, idx) => (
                      <Text key={`total-${idx}`} style={styles.tableCell}>
                        {formatAmount(value)}
                      </Text>
                    ))}
                    <Text style={[styles.tableCell, styles.totalColumn]}>{formatAmount(revenueSummary.totals.total)}</Text>
                  </View>
                </View>
              </ScrollView>
            )}
            {!loadingRevenue && (!revenueSummary || revenueRows.length === 0) && (
              <Text style={styles.loadingText}>暂无收入数据。</Text>
            )}
          </View>
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
  cardMeta: {
    color: '#CBD5F5',
    fontSize: 12,
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
  revenueSection: {
    marginTop: 24,
    backgroundColor: '#131A2B',
    borderRadius: 16,
    padding: 16,
    gap: 16,
  },
  revenueHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  revenueControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
  },
  yearSelector: {
    flexDirection: 'row',
    gap: 8,
  },
  yearChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(96, 165, 250, 0.35)',
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  yearChipActive: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  yearChipText: {
    color: '#60A5FA',
    fontSize: 13,
  },
  yearChipTextActive: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  levelSelector: {
    flexDirection: 'row',
    gap: 8,
  },
  levelChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.4)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: 'rgba(148, 163, 184, 0.12)',
  },
  levelChipActive: {
    backgroundColor: '#38BDF8',
    borderColor: '#38BDF8',
  },
  levelChipText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  levelChipTextActive: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  revenueTableContainer: {
    borderRadius: 12,
    overflow: 'hidden',
  },
  unitHint: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 6,
    paddingLeft: 12,
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
  },
  tableHeaderRow: {
    backgroundColor: 'rgba(30, 64, 175, 0.5)',
  },
  tableTotalRow: {
    backgroundColor: 'rgba(30, 64, 175, 0.35)',
  },
  tableHeaderCell: {
    color: '#E2E8F0',
    fontSize: 13,
    fontWeight: '600',
    paddingVertical: 10,
    paddingHorizontal: 12,
    minWidth: 72,
    textAlign: 'right',
  },
  tableCell: {
    color: '#F8FAFC',
    fontSize: 13,
    paddingVertical: 8,
    paddingHorizontal: 12,
    minWidth: 72,
    textAlign: 'right',
  },
  labelColumn: {
    minWidth: 180,
    textAlign: 'left',
  },
  totalColumn: {
    minWidth: 96,
  },
})


