import { memo } from 'react'
import { StyleSheet, Text, View } from 'react-native'
import { VictoryAxis, VictoryBar, VictoryChart, VictoryTheme } from 'victory-native'

export type TrendDatum = {
  label: string
  value: number
}

type FinancialTrendsProps = {
  title: string
  data: TrendDatum[]
}

const FinancialTrends = ({ title, data }: FinancialTrendsProps) => {
  if (data.length === 0) {
    return null
  }

  return (
    <View style={styles.wrapper}>
      <Text style={styles.title}>{title}</Text>
      <VictoryChart theme={VictoryTheme.material} domainPadding={20} height={240}>
        <VictoryAxis style={{ tickLabels: { fill: '#CBD5F5', fontSize: 12 } }} />
        <VictoryAxis dependentAxis style={{ tickLabels: { fill: '#CBD5F5', fontSize: 12 } }} />
        <VictoryBar
          data={data}
          x="label"
          y="value"
          style={{
            data: { fill: '#60A5FA', width: 22 },
          }}
          labels={({ datum }) => datum.value.toLocaleString()}
          animate={{
            duration: 500,
            onLoad: { duration: 300 },
          }}
        />
      </VictoryChart>
    </View>
  )
}

export default memo(FinancialTrends)

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor: '#131A2B',
    borderRadius: 16,
    padding: 16,
    marginTop: 16,
  },
  title: {
    color: '#E2E8F0',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
})


