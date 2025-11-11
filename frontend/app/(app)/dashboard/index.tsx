import { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Dimensions, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native'
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
  expensesMonthly?: Array<{ month: string; amount: number }>
  incomesMonthly?: Array<{ month: string; certain: number; uncertain: number }>
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
  forecastMonthly?: number[]
  forecastTotal?: number
  forecastCertainMonthly?: number[]
  forecastUncertainMonthly?: number[]
  forecastCertainTotal?: number
  forecastUncertainTotal?: number
  children?: RevenueSummaryNode[]
}

type RevenueSummaryTotals = {
  monthly: number[]
  total: number
  forecastMonthly?: number[]
  forecastTotal?: number
  forecastCertainMonthly?: number[]
  forecastUncertainMonthly?: number[]
  forecastCertainTotal?: number
  forecastUncertainTotal?: number
}

type RevenueSummaryResponse = {
  year: number
  companyId?: string | null
  totals: RevenueSummaryTotals
  nodes: RevenueSummaryNode[]
}

const MAX_REVENUE_LEVEL = 6

export default function DashboardScreen() {
  // 动态检测是否为手机端
  const { width } = useWindowDimensions()
  const isMobile = width < 768

  const [data, setData] = useState<FinancialOverviewResponse | null>(null)
  const [companyId, setCompanyId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [revenueSummary, setRevenueSummary] = useState<RevenueSummaryResponse | null>(null)
  const currentYear = new Date().getFullYear()
  const [revenueYear, setRevenueYear] = useState(currentYear)
  const [loadingRevenue, setLoadingRevenue] = useState(false)
  const [availableYears, setAvailableYears] = useState<Set<number>>(new Set([currentYear]))
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const [includeForecast, setIncludeForecast] = useState(true)
  const [includeCertainIncome, setIncludeCertainIncome] = useState(true)
  const [includeUncertainIncome, setIncludeUncertainIncome] = useState(false)
  const [expandedExpenseMonth, setExpandedExpenseMonth] = useState<string | null>(null)
  const [expenseDetails, setExpenseDetails] = useState<Record<string, any>>({})
  const [loadingExpenseDetail, setLoadingExpenseDetail] = useState<string | null>(null)

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
      const params: Record<string, string> = { year: String(revenueYear), maxLevel: String(MAX_REVENUE_LEVEL) }
      if (companyId) {
        params.companyId = companyId
      }
      if (includeForecast) {
        params.includeForecast = 'true'
      }
      const query = new URLSearchParams(params).toString()
      const response = await apiClient.get<RevenueSummaryResponse>(`/api/v1/financial/revenue-summary?${query}`)
      setRevenueSummary(response)
      
      // 检查该年份是否有数据
      const hasData = response.nodes.length > 0 || response.totals.total > 0 || 
                      (includeForecast && (response.totals.forecastCertainTotal ?? 0) > 0) ||
                      (includeForecast && (response.totals.forecastUncertainTotal ?? 0) > 0)
      
      setAvailableYears((prev) => {
        const next = new Set(prev)
        if (hasData) {
          next.add(revenueYear)
        } else {
          // 如果没有数据，从可用年份列表中移除（除非是当前年份）
          if (revenueYear !== currentYear) {
            next.delete(revenueYear)
          }
        }
        return next
      })
    } catch (error) {
      console.error('[DASHBOARD] load revenue summary failed', error)
      setRevenueSummary(null)
    } finally {
      setLoadingRevenue(false)
    }
  }, [companyId, revenueYear, includeForecast, currentYear])

  useEffect(() => {
    loadOverview()
    loadRevenueSummary()
  }, [loadOverview, loadRevenueSummary])

  const makeNodeKey = useCallback((parentKey: string | null, label: string) => {
    return parentKey ? `${parentKey}>${label}` : label
  }, [])

  useEffect(() => {
    if (!revenueSummary) {
      setExpandedKeys(new Set())
      return
    }
    // 默认树形结构是收起来的，不展开任何节点
    setExpandedKeys(new Set())
  }, [revenueSummary, makeNodeKey])

  const toggleNode = useCallback((key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

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

  // 只显示有数据的年份，如果没有数据则默认显示当前年份
  const yearOptions = useMemo(() => {
    const years = Array.from(availableYears).sort((a, b) => b - a)
    // 如果当前年份不在列表中，确保包含当前年份
    if (!years.includes(currentYear)) {
      return [currentYear, ...years].slice(0, 3)
    }
    return years.slice(0, 3)
  }, [availableYears, currentYear])
  
  // 如果当前选择的年份不在可用年份列表中，切换到当前年份
  useEffect(() => {
    if (!availableYears.has(revenueYear) && revenueYear !== currentYear) {
      setRevenueYear(currentYear)
    }
  }, [availableYears, revenueYear, currentYear])

  const revenueRows = useMemo(() => {
    if (!revenueSummary) {
      return []
    }

    type Row = {
      key: string
      label: string
      depth: number
      monthly: number[]
      total: number
      forecastMonthly?: number[]
      forecastTotal?: number
      forecastCertainMonthly?: number[]
      forecastUncertainMonthly?: number[]
      forecastCertainTotal?: number
      forecastUncertainTotal?: number
      hasChildren: boolean
      expanded: boolean
    }

    const rows: Row[] = []

    const traverse = (nodes: RevenueSummaryNode[], parentKey: string | null, depth: number) => {
      nodes.forEach((node) => {
        const key = makeNodeKey(parentKey, node.label)
        const hasChildren = !!(node.children && node.children.length > 0)
        const expanded = expandedKeys.has(key)
        rows.push({
          key,
          label: node.label,
          depth,
          monthly: node.monthly,
          total: node.total,
          forecastMonthly: node.forecastMonthly,
          forecastTotal: node.forecastTotal,
          forecastCertainMonthly: node.forecastCertainMonthly,
          forecastUncertainMonthly: node.forecastUncertainMonthly,
          forecastCertainTotal: node.forecastCertainTotal,
          forecastUncertainTotal: node.forecastUncertainTotal,
          hasChildren,
          expanded,
        })
        if (hasChildren && expanded) {
          traverse(node.children ?? [], key, depth + 1)
        }
      })
    }

    traverse(revenueSummary.nodes, null, 0)
    return rows
  }, [revenueSummary, expandedKeys, makeNodeKey])

  const formatAmount = useCallback((value: number) => {
    if (value === 0) {
      return ''
    }
    // 转换为万元，并四舍五入到2位小数
    const valueInTenThousands = value / 10000
    // 使用 Math.round 确保四舍五入，然后格式化为2位小数
    const rounded = Math.round(valueInTenThousands * 100) / 100
    return rounded.toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  }, [])

  const formatForecastAmount = useCallback(
    (value: number) => {
      const formatted = formatAmount(value)
      if (!formatted) {
        return ''
      }
      return `+${formatted}`
    },
    [formatAmount],
  )

  const formatCurrency = useCallback((value: number) => {
    return (value / 10000).toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  }, [])

  const loadExpenseDetail = useCallback(async (month: string) => {
    setExpenseDetails((prev) => {
      if (prev[month]) {
        // 如果已经加载过，直接切换展开状态
        setExpandedExpenseMonth((current) => (current === month ? null : month))
        return prev
      }
      // 如果没有加载过，开始加载
      setLoadingExpenseDetail(month)
      const params: Record<string, string> = { month }
      if (companyId) {
        params.companyId = companyId
      }
      const query = new URLSearchParams(params).toString()
      apiClient
        .get(`/api/v1/financial/expense-forecast-detail?${query}`)
        .then((response) => {
          setExpenseDetails((p) => ({ ...p, [month]: response }))
          setExpandedExpenseMonth(month)
        })
        .catch((error) => {
          console.error('[DASHBOARD] load expense detail failed', error)
        })
        .finally(() => {
          setLoadingExpenseDetail((current) => (current === month ? null : current))
        })
      return prev
    })
  }, [companyId])

  const cashflowRows = useMemo(() => {
    if (!currentCompany?.forecast || !currentCompany.balances) {
      return []
    }

    const forecast = currentCompany.forecast
    const initialBalance = currentCompany.balances.total

    // 构建支出和收入映射表
    const expenseMap = new Map<string, number>()
    if (forecast.expensesMonthly) {
      forecast.expensesMonthly.forEach((item) => {
        expenseMap.set(item.month, (expenseMap.get(item.month) || 0) + item.amount)
      })
    }

    const incomeCertainMap = new Map<string, number>()
    const incomeUncertainMap = new Map<string, number>()
    if (forecast.incomesMonthly) {
      forecast.incomesMonthly.forEach((item) => {
        if (item.certain > 0) {
          incomeCertainMap.set(item.month, (incomeCertainMap.get(item.month) || 0) + item.certain)
        }
        if (item.uncertain > 0) {
          incomeUncertainMap.set(item.month, (incomeUncertainMap.get(item.month) || 0) + item.uncertain)
        }
      })
    }

    // 找到所有涉及的月份，从本月开始
    const now = new Date()
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    
    const allMonths = new Set<string>()
    allMonths.add(currentMonth)
    expenseMap.forEach((_, month) => {
      if (month >= currentMonth) {
        allMonths.add(month)
      }
    })
    incomeCertainMap.forEach((_, month) => {
      if (month >= currentMonth) {
        allMonths.add(month)
      }
    })
    incomeUncertainMap.forEach((_, month) => {
      if (month >= currentMonth) {
        allMonths.add(month)
      }
    })

    // 排序月份
    const sortedMonths = Array.from(allMonths).sort()
    
    // 如果没有数据，至少显示当前月份
    const monthsToShow = sortedMonths.length > 0 ? sortedMonths : [currentMonth]

    // 计算每月的现金流
    let balance = initialBalance
    const rows: Array<{
      month: string
      openingBalance: number
      certainIncome: number
      uncertainIncome: number
      expense: number
      closingBalance: number
    }> = []

    monthsToShow.forEach((month) => {
      const openingBalance = balance
      const certainIncome = includeCertainIncome ? (incomeCertainMap.get(month) || 0) : 0
      const uncertainIncome = includeUncertainIncome ? (incomeUncertainMap.get(month) || 0) : 0
      const expense = expenseMap.get(month) || 0
      const closingBalance = openingBalance + certainIncome + uncertainIncome - expense

      rows.push({
        month,
        openingBalance,
        certainIncome,
        uncertainIncome,
        expense,
        closingBalance,
      })

      balance = closingBalance
    })

    return rows
  }, [currentCompany?.forecast, currentCompany?.balances, includeCertainIncome, includeUncertainIncome])

  // 动态生成样式
  const dynamicStyles = useMemo(() => createStyles(isMobile), [isMobile])

  return (
    <SafeAreaView style={dynamicStyles.safeArea}>
      <View style={dynamicStyles.container}>
        <View style={dynamicStyles.header}>
          <View>
            <Text style={dynamicStyles.title}>财务概览</Text>
            <Text style={dynamicStyles.subtitle}>{data ? `数据截至 ${data.asOf}` : '加载中...'}</Text>
          </View>
          <View style={dynamicStyles.links}>
            <NavLink href="/(app)/import" label="数据录入" textStyle={dynamicStyles.link} />
            <NavLink href="/(app)/analysis" label="查询分析" textStyle={dynamicStyles.link} />
            <NavLink href="/(app)/history" label="历史记录" textStyle={dynamicStyles.link} />
          </View>
        </View>

        <ScrollView contentContainerStyle={dynamicStyles.scrollContent}>
          {loading && (
            <View style={dynamicStyles.loadingContainer}>
              <ActivityIndicator color="#60A5FA" />
              <Text style={dynamicStyles.loadingText}>正在加载概览数据...</Text>
            </View>
          )}

          {!loading && currentCompany && (
            <>
              <View style={dynamicStyles.cards}>
                <View style={dynamicStyles.card}>
                  <Text style={dynamicStyles.cardTitle}>账户余额</Text>
                  {currentCompany.balances ? (
                    <>
                      <Text style={dynamicStyles.cardMeta}>截至 {currentCompany.balances.reportedAt}</Text>
                      <Text style={dynamicStyles.cardMetric}>{currentCompany.balances.total.toLocaleString()} 元</Text>
                      <Text style={dynamicStyles.cardDetail}>
                        现金 {currentCompany.balances.cash.toLocaleString()} · 理财{' '}
                        {currentCompany.balances.investment.toLocaleString()}
                      </Text>
                    </>
                  ) : (
                    <Text style={dynamicStyles.cardDetail}>暂无余额数据</Text>
                  )}
                  <View style={dynamicStyles.cardFooter}>
                    <Text style={dynamicStyles.cardHint}>当前显示最新数据</Text>
                    <NavLink href="/(app)/dashboard/history" label="查看历史" textStyle={dynamicStyles.cardLink} />
                  </View>
                </View>
              </View>

              <View style={dynamicStyles.cashflowCard}>
                <Text style={dynamicStyles.cardTitle}>预测现金流</Text>
                {currentCompany.forecast ? (
                  <>
                    <View style={dynamicStyles.cashflowCheckboxes}>
                      <TouchableOpacity
                        style={[dynamicStyles.checkbox, includeCertainIncome && dynamicStyles.checkboxChecked]}
                        onPress={() => setIncludeCertainIncome((prev) => !prev)}
                      >
                        <View style={[dynamicStyles.checkboxIndicator, includeCertainIncome && dynamicStyles.checkboxIndicatorChecked]}>
                          {includeCertainIncome && <Text style={dynamicStyles.checkboxCheckmark}>✓</Text>}
                        </View>
                        <Text style={dynamicStyles.checkboxLabel}>预测确定性收入</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[dynamicStyles.checkbox, includeUncertainIncome && dynamicStyles.checkboxChecked]}
                        onPress={() => setIncludeUncertainIncome((prev) => !prev)}
                      >
                        <View style={[dynamicStyles.checkboxIndicator, includeUncertainIncome && dynamicStyles.checkboxIndicatorChecked]}>
                          {includeUncertainIncome && <Text style={dynamicStyles.checkboxCheckmark}>✓</Text>}
                        </View>
                        <Text style={dynamicStyles.checkboxLabel}>预测非确定性收入</Text>
                      </TouchableOpacity>
                    </View>
                    {cashflowRows.length > 0 ? (
                      <ScrollView horizontal style={dynamicStyles.cashflowTableContainer}>
                        <View>
                          <Text style={dynamicStyles.cashflowUnitHint}>单位：万元</Text>
                          <View style={[dynamicStyles.cashflowRow, dynamicStyles.cashflowHeaderRow]}>
                            <Text style={[dynamicStyles.cashflowCell, dynamicStyles.cashflowMonthCell]}>月份</Text>
                            <Text style={dynamicStyles.cashflowCell}>结余</Text>
                            <Text style={dynamicStyles.cashflowCell}>期初余额</Text>
                            <Text style={dynamicStyles.cashflowCell}>支出</Text>
                            {includeCertainIncome && <Text style={dynamicStyles.cashflowCell}>确定性收入</Text>}
                            {includeUncertainIncome && <Text style={dynamicStyles.cashflowCell}>非确定性收入</Text>}
                          </View>
                          {cashflowRows.map((row) => {
                            const isExpanded = expandedExpenseMonth === row.month
                            const detail = expenseDetails[row.month]
                            return (
                              <View key={row.month}>
                                <View style={dynamicStyles.cashflowRow}>
                                  <Text style={[dynamicStyles.cashflowCell, dynamicStyles.cashflowMonthCell]}>
                                    {row.month.replace(/(\d{4})-(\d{2})/, '$1年$2月')}
                                  </Text>
                                  <Text
                                    style={[
                                      dynamicStyles.cashflowCell,
                                      dynamicStyles.cashflowBalanceCell,
                                      row.closingBalance >= 0 ? dynamicStyles.cashflowPositive : dynamicStyles.cashflowNegative,
                                    ]}
                                  >
                                    {formatCurrency(row.closingBalance)}
                                  </Text>
                                  <Text style={dynamicStyles.cashflowCell}>{formatCurrency(row.openingBalance)}</Text>
                                  <TouchableOpacity
                                    onPress={() => loadExpenseDetail(row.month)}
                                    disabled={loadingExpenseDetail === row.month}
                                  >
                                    <View style={dynamicStyles.cashflowCell}>
                                      <View style={dynamicStyles.expenseCellContainer}>
                                        <Text style={dynamicStyles.cashflowCell}>{formatCurrency(row.expense)}</Text>
                                        {row.expense > 0 && (
                                          <Text style={dynamicStyles.expandIcon}>
                                            {isExpanded ? '▼' : '▶'}
                                          </Text>
                                        )}
                                      </View>
                                    </View>
                                  </TouchableOpacity>
                                  {includeCertainIncome && (
                                    <Text style={dynamicStyles.cashflowCell}>{formatCurrency(row.certainIncome)}</Text>
                                  )}
                                  {includeUncertainIncome && (
                                    <Text style={dynamicStyles.cashflowCell}>{formatCurrency(row.uncertainIncome)}</Text>
                                  )}
                                </View>
                                {isExpanded && (
                                  <View style={dynamicStyles.cashflowRow}>
                                    {/* 月份列 - 空 */}
                                    <View style={[dynamicStyles.cashflowCell, dynamicStyles.cashflowMonthCell]} />
                                    {/* 结余列 - 空 */}
                                    <View style={dynamicStyles.cashflowCell} />
                                    {/* 期初余额列 - 空 */}
                                    <View style={dynamicStyles.cashflowCell} />
                                    {/* 支出列 - 详情容器 */}
                                    <View style={dynamicStyles.expenseDetailCell}>
                                      <View style={dynamicStyles.expenseDetailContainer}>
                                        {loadingExpenseDetail === row.month && !detail ? (
                                          <View style={dynamicStyles.expenseDetailLoading}>
                                            <ActivityIndicator size="small" color="#60A5FA" />
                                            <Text style={dynamicStyles.expenseDetailLoadingText}>加载中...</Text>
                                          </View>
                                        ) : detail ? (
                                          <>
                                            {detail.categories && detail.categories.length > 0 ? (
                                              detail.categories.flatMap((category: any) =>
                                                category.items && category.items.length > 0
                                                  ? category.items.map((item: any, itemIdx: number) => (
                                                      <View key={`${category.categoryLabel}-${itemIdx}`} style={dynamicStyles.expenseItemRow}>
                                                        <View style={dynamicStyles.expenseItemInfo}>
                                                          <Text style={dynamicStyles.expenseItemDescription}>
                                                            {[item.description, item.accountName].filter(Boolean).join(' · ')}
                                                          </Text>
                                                        </View>
                                                        <Text style={dynamicStyles.expenseItemAmount}>
                                                          {formatCurrency(item.amount)}
                                                        </Text>
                                                      </View>
                                                    ))
                                                  : []
                                              )
                                            ) : (
                                              <Text style={dynamicStyles.expenseDetailEmpty}>暂无支出详情</Text>
                                            )}
                                          </>
                                        ) : null}
                                      </View>
                                    </View>
                                    {/* 确定性收入列 - 空（如果显示） */}
                                    {includeCertainIncome && <View style={dynamicStyles.cashflowCell} />}
                                    {/* 非确定性收入列 - 空（如果显示） */}
                                    {includeUncertainIncome && <View style={dynamicStyles.cashflowCell} />}
                                  </View>
                                )}
                              </View>
                            )
                          })}
                        </View>
                      </ScrollView>
                    ) : (
                      <Text style={dynamicStyles.cardDetail}>暂无预测数据</Text>
                    )}
                  </>
                ) : (
                  <Text style={dynamicStyles.cardDetail}>暂无预测数据</Text>
                )}
              </View>
            </>
          )}

          <View style={dynamicStyles.revenueSection}>
            <View style={dynamicStyles.revenueHeader}>
              <Text style={dynamicStyles.sectionTitle}>收入汇总</Text>
              <View style={dynamicStyles.revenueControls}>
                <View style={dynamicStyles.yearSelector}>
                  {yearOptions.map((year) => (
                    <TouchableOpacity
                      key={year}
                      style={[dynamicStyles.yearChip, revenueYear === year && dynamicStyles.yearChipActive]}
                      onPress={() => setRevenueYear(year)}
                      disabled={loadingRevenue}
                    >
                      <Text style={revenueYear === year ? dynamicStyles.yearChipTextActive : dynamicStyles.yearChipText}>{year} 年</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <TouchableOpacity
                  style={[dynamicStyles.forecastToggle, includeForecast && dynamicStyles.forecastToggleActive]}
                  onPress={() => setIncludeForecast((prev) => !prev)}
                  disabled={loadingRevenue}
                >
                  <Text style={includeForecast ? dynamicStyles.forecastToggleTextActive : dynamicStyles.forecastToggleText}>
                    {includeForecast ? '已包含预测' : '包含预测'}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
            {includeForecast && (
              <View style={dynamicStyles.legendRow}>
                <View style={dynamicStyles.legendItem}>
                  <View style={[dynamicStyles.legendDot, dynamicStyles.legendDotActual]} />
                  <Text style={dynamicStyles.legendText}>实际收入</Text>
                </View>
                <View style={dynamicStyles.legendItem}>
                  <View style={[dynamicStyles.legendDot, dynamicStyles.legendDotForecastCertain]} />
                  <Text style={dynamicStyles.legendText}>确定预测</Text>
                </View>
                <View style={dynamicStyles.legendItem}>
                  <View style={[dynamicStyles.legendDot, dynamicStyles.legendDotForecastUncertain]} />
                  <Text style={dynamicStyles.legendText}>非确定预测</Text>
                </View>
              </View>
            )}
            {loadingRevenue && (
              <View style={dynamicStyles.loadingContainer}>
                <ActivityIndicator color="#60A5FA" />
                <Text style={dynamicStyles.loadingText}>正在加载收入汇总...</Text>
              </View>
            )}
            {!loadingRevenue && revenueSummary && revenueRows.length > 0 && (
              <View>
                <Text style={dynamicStyles.unitHint}>单位：万元{isMobile ? '（左右滑动查看完整表格）' : ''}</Text>
                <ScrollView 
                  horizontal 
                  style={dynamicStyles.revenueTableContainer}
                  showsHorizontalScrollIndicator={true}
                  contentContainerStyle={isMobile ? { paddingRight: 8 } : undefined}
                >
                  <View>
                  <View style={[dynamicStyles.tableRow, dynamicStyles.tableHeaderRow]}>
                    <Text style={[dynamicStyles.tableHeaderCell, dynamicStyles.labelColumn]}>分类</Text>
                    {Array.from({ length: 12 }, (_, index) => (
                      <Text key={`month-${index}`} style={dynamicStyles.tableHeaderCell}>
                        {index + 1} 月
                      </Text>
                    ))}
                    <Text style={[dynamicStyles.tableHeaderCell, dynamicStyles.totalColumn]}>合计</Text>
                  </View>
                  {revenueRows.map((row) => (
                    <View key={row.key} style={dynamicStyles.tableRow}>
                      <View style={[dynamicStyles.tableCell, dynamicStyles.labelColumn]}>
                        <View style={[dynamicStyles.treeLabelContainer, { paddingLeft: 12 + row.depth * 16 }]}>
                          {row.hasChildren ? (
                            <TouchableOpacity
                              onPress={() => toggleNode(row.key)}
                              style={[
                                dynamicStyles.collapseButton,
                                row.expanded && dynamicStyles.collapseButtonExpanded,
                              ]}
                            >
                              <Text
                                style={[
                                  dynamicStyles.collapseButtonText,
                                  row.expanded && dynamicStyles.collapseButtonTextExpanded,
                                ]}
                              >
                                {row.expanded ? '−' : '+'}
                              </Text>
                            </TouchableOpacity>
                          ) : (
                            <View style={dynamicStyles.collapsePlaceholder} />
                          )}
                          <Text style={dynamicStyles.labelText}>{row.label}</Text>
                        </View>
                      </View>
                      {row.monthly.map((value, idx) => {
                        const certainValue = row.forecastCertainMonthly?.[idx] ?? 0
                        const uncertainValue = row.forecastUncertainMonthly?.[idx] ?? 0
                        const actualText = formatAmount(value)
                        const certainText = includeForecast ? formatForecastAmount(certainValue) : ''
                        const uncertainText = includeForecast ? formatForecastAmount(uncertainValue) : ''
                        const showCertain = includeForecast && !!certainText
                        const showUncertain = includeForecast && !!uncertainText
                        return (
                          <Text key={`${row.key}-m-${idx}`} style={dynamicStyles.tableCell}>
                            {actualText || (showCertain || showUncertain ? ' ' : '')}
                            {showCertain ? '\n' : ''}
                            {showCertain ? <Text style={dynamicStyles.forecastCertainValue}>{certainText}</Text> : null}
                            {showUncertain ? '\n' : ''}
                            {showUncertain ? (
                              <Text style={dynamicStyles.forecastUncertainValue}>{uncertainText}</Text>
                            ) : null}
                          </Text>
                        )
                      })}
                      {(() => {
                        const forecastCertain = row.forecastCertainTotal ?? 0
                        const forecastUncertain = row.forecastUncertainTotal ?? 0
                        const actualText = formatAmount(row.total)
                        const certainText = includeForecast ? formatForecastAmount(forecastCertain) : ''
                        const uncertainText = includeForecast ? formatForecastAmount(forecastUncertain) : ''
                        const showCertain = includeForecast && !!certainText
                        const showUncertain = includeForecast && !!uncertainText
                        return (
                          <Text style={[dynamicStyles.tableCell, dynamicStyles.totalColumn]}>
                            {actualText || (showCertain || showUncertain ? ' ' : '')}
                            {showCertain ? '\n' : ''}
                            {showCertain ? <Text style={dynamicStyles.forecastCertainValue}>{certainText}</Text> : null}
                            {showUncertain ? '\n' : ''}
                            {showUncertain ? (
                              <Text style={dynamicStyles.forecastUncertainValue}>{uncertainText}</Text>
                            ) : null}
                          </Text>
                        )
                      })()}
                    </View>
                  ))}
                  <View style={[dynamicStyles.tableRow, dynamicStyles.tableTotalRow]}>
                    <Text style={[dynamicStyles.tableCell, dynamicStyles.labelColumn]}>合计</Text>
                    {revenueSummary.totals.monthly.map((value, idx) => {
                      const forecastCertain = revenueSummary.totals.forecastCertainMonthly?.[idx] ?? 0
                      const forecastUncertain = revenueSummary.totals.forecastUncertainMonthly?.[idx] ?? 0
                      const actualText = formatAmount(value)
                      const certainText = includeForecast ? formatForecastAmount(forecastCertain) : ''
                      const uncertainText = includeForecast ? formatForecastAmount(forecastUncertain) : ''
                      const showCertain = includeForecast && !!certainText
                      const showUncertain = includeForecast && !!uncertainText
                      return (
                        <Text key={`total-${idx}`} style={dynamicStyles.tableCell}>
                          {actualText || (showCertain || showUncertain ? ' ' : '')}
                          {showCertain ? '\n' : ''}
                          {showCertain ? <Text style={dynamicStyles.forecastCertainValue}>{certainText}</Text> : null}
                          {showUncertain ? '\n' : ''}
                          {showUncertain ? (
                            <Text style={dynamicStyles.forecastUncertainValue}>{uncertainText}</Text>
                          ) : null}
                        </Text>
                      )
                    })}
                    {(() => {
                      const forecastCertain = revenueSummary.totals.forecastCertainTotal ?? 0
                      const forecastUncertain = revenueSummary.totals.forecastUncertainTotal ?? 0
                      const actualText = formatAmount(revenueSummary.totals.total)
                      const certainText = includeForecast ? formatForecastAmount(forecastCertain) : ''
                      const uncertainText = includeForecast ? formatForecastAmount(forecastUncertain) : ''
                      const showCertain = includeForecast && !!certainText
                      const showUncertain = includeForecast && !!uncertainText
                      return (
                        <Text style={[dynamicStyles.tableCell, dynamicStyles.totalColumn]}>
                          {actualText || (showCertain || showUncertain ? ' ' : '')}
                          {showCertain ? '\n' : ''}
                          {showCertain ? <Text style={dynamicStyles.forecastCertainValue}>{certainText}</Text> : null}
                          {showUncertain ? '\n' : ''}
                          {showUncertain ? (
                            <Text style={dynamicStyles.forecastUncertainValue}>{uncertainText}</Text>
                          ) : null}
                        </Text>
                      )
                    })()}
                  </View>
                </View>
                </ScrollView>
              </View>
            )}
            {!loadingRevenue && (!revenueSummary || revenueRows.length === 0) && (
              <Text style={dynamicStyles.loadingText}>暂无收入数据。</Text>
            )}
          </View>
        </ScrollView>
      </View>
    </SafeAreaView>
  )
}

const createStyles = (isMobile: boolean) => StyleSheet.create({
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
    flexDirection: isMobile ? 'column' : 'row',
    justifyContent: isMobile ? 'flex-start' : 'space-between',
    alignItems: isMobile ? 'flex-start' : 'center',
    marginBottom: 12,
    marginTop: 8,
    gap: isMobile ? 12 : 0,
  },
  title: {
    color: '#FFFFFF',
    fontSize: isMobile ? 20 : 24,
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
    flexWrap: 'wrap',
    marginTop: isMobile ? 8 : 0,
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
    width: '100%',
    backgroundColor: '#131A2B',
    padding: isMobile ? 12 : 16,
    borderRadius: 16,
    marginTop: 12,
  },
  cashflowCard: {
    width: '100%',
    backgroundColor: '#131A2B',
    padding: isMobile ? 12 : 16,
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
    fontSize: isMobile ? 16 : 18,
    fontWeight: '600',
  },
  expenseForecastBlock: {
    marginTop: 12,
    gap: 6,
  },
  expenseForecastTitle: {
    color: '#FACC15',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  expenseForecastRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  expenseForecastMonth: {
    color: '#CBD5F5',
    fontSize: 12,
  },
  expenseForecastAmount: {
    color: '#FACC15',
    fontSize: 12,
    fontVariant: ['lining-nums'],
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
    padding: isMobile ? 12 : 16,
    gap: 16,
  },
  revenueHeader: {
    flexDirection: isMobile ? 'column' : 'row',
    justifyContent: isMobile ? 'flex-start' : 'space-between',
    alignItems: isMobile ? 'flex-start' : 'center',
    gap: 12,
  },
  revenueControls: {
    flexDirection: isMobile ? 'column' : 'row',
    alignItems: isMobile ? 'stretch' : 'center',
    gap: 12,
    width: isMobile ? '100%' : 'auto',
    marginTop: isMobile ? 8 : 0,
  },
  sectionTitle: {
    color: '#FFFFFF',
    fontSize: isMobile ? 16 : 18,
    fontWeight: '600',
  },
  yearSelector: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
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
  forecastToggle: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(250, 204, 21, 0.4)',
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  forecastToggleActive: {
    backgroundColor: 'rgba(250, 204, 21, 0.2)',
    borderColor: '#FACC15',
  },
  forecastToggleText: {
    color: '#FACC15',
    fontSize: 12,
  },
  forecastToggleTextActive: {
    color: '#FDE68A',
    fontSize: 12,
    fontWeight: '600',
  },
  revenueTableContainer: {
    borderRadius: 12,
    overflow: 'hidden',
    // 移动端添加阴影提示可以横向滚动
    ...(isMobile && {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 3,
    }),
  },
  unitHint: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 6,
    paddingLeft: 12,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    paddingHorizontal: 12,
    marginBottom: 6,
    flexWrap: 'wrap',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  legendDotActual: {
    backgroundColor: '#60A5FA',
  },
  legendDotForecastCertain: {
    backgroundColor: '#34D399',
  },
  legendDotForecastUncertain: {
    backgroundColor: '#F97316',
  },
  legendText: {
    color: '#CBD5F5',
    fontSize: 12,
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
    fontSize: isMobile ? 12 : 13,
    fontWeight: '600',
    paddingVertical: 10,
    paddingHorizontal: isMobile ? 8 : 12,
    minWidth: isMobile ? 60 : 72,
    textAlign: 'right',
  },
  tableCell: {
    color: '#F8FAFC',
    fontSize: isMobile ? 12 : 13,
    paddingVertical: 8,
    paddingHorizontal: isMobile ? 8 : 12,
    minWidth: isMobile ? 60 : 72,
    textAlign: 'right',
  },
  labelColumn: {
    minWidth: isMobile ? 120 : 180,
    textAlign: 'left',
  },
  treeLabelContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  collapseButton: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#38BDF8',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    backgroundColor: 'transparent',
  },
  collapseButtonExpanded: {
    backgroundColor: '#38BDF8',
  },
  collapseButtonText: {
    color: '#38BDF8',
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 12,
  },
  collapseButtonTextExpanded: {
    color: '#0F172A',
  },
  collapsePlaceholder: {
    width: 22,
    height: 22,
    marginRight: 8,
  },
  labelText: {
    color: '#F8FAFC',
    fontSize: 13,
  },
  totalColumn: {
    minWidth: 96,
  },
  forecastCertainValue: {
    color: '#34D399',
    fontSize: 12,
  },
  forecastUncertainValue: {
    color: '#F97316',
    fontSize: 12,
  },
  cashflowCheckboxes: {
    flexDirection: isMobile ? 'column' : 'row',
    gap: isMobile ? 12 : 16,
    marginTop: 12,
    marginBottom: 12,
  },
  checkbox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  checkboxChecked: {
    // 可以添加选中状态的样式
  },
  checkboxIndicator: {
    width: 18,
    height: 18,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: '#60A5FA',
    backgroundColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxIndicatorChecked: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  checkboxCheckmark: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
    textAlign: 'center',
    lineHeight: 14,
  },
  checkboxLabel: {
    color: '#CBD5F5',
    fontSize: 13,
  },
  cashflowTableContainer: {
    marginTop: 8,
    borderRadius: 8,
    overflow: 'hidden',
  },
  cashflowUnitHint: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 6,
    paddingLeft: 12,
  },
  cashflowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
  },
  cashflowHeaderRow: {
    backgroundColor: 'rgba(30, 64, 175, 0.5)',
  },
  cashflowCell: {
    color: '#F8FAFC',
    fontSize: isMobile ? 11 : 12,
    paddingVertical: 8,
    paddingHorizontal: isMobile ? 8 : 10,
    minWidth: isMobile ? 70 : 80,
    textAlign: 'right',
  },
  cashflowMonthCell: {
    minWidth: isMobile ? 70 : 90,
    textAlign: 'left',
  },
  cashflowBalanceCell: {
    fontSize: isMobile ? 13 : 15,
    fontWeight: '700',
  },
  cashflowPositive: {
    color: '#34D399',
  },
  cashflowNegative: {
    color: '#F87171',
  },
  expenseCellContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  expandIcon: {
    color: '#60A5FA',
    fontSize: 10,
    marginLeft: 4,
  },
  expenseDetailCell: {
    minWidth: isMobile ? 70 : 80,
    paddingHorizontal: isMobile ? 8 : 10,
  },
  expenseDetailContainer: {
    backgroundColor: 'rgba(15, 23, 42, 0.8)',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderLeftWidth: 2,
    borderLeftColor: '#60A5FA',
  },
  expenseDetailLoading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
  },
  expenseDetailLoadingText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  expenseCategoryRow: {
    marginBottom: 12,
  },
  expenseCategoryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  expenseCategoryLabel: {
    color: '#E2E8F0',
    fontSize: 13,
    fontWeight: '600',
  },
  expenseCategoryAmount: {
    color: '#FACC15',
    fontSize: 13,
    fontWeight: '600',
  },
  expenseItemsContainer: {
    paddingLeft: 12,
    gap: 4,
  },
  expenseItemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: 4,
  },
  expenseItemInfo: {
    flex: 1,
  },
  expenseItemDescription: {
    color: '#CBD5F5',
    fontSize: 12,
  },
  expenseItemAmount: {
    color: '#FACC15',
    fontSize: 12,
    marginLeft: 8,
  },
  expenseDetailEmpty: {
    color: '#94A3B8',
    fontSize: 12,
    paddingVertical: 8,
    textAlign: 'center',
  },
})

const styles = createStyles(false) // 默认样式，用于类型检查


