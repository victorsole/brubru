import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const data = [
  { date: 'Oct 1', euAI: 100, stoxx: 100, sp500: 100 },
  { date: 'Oct 15', euAI: 103.2, stoxx: 101.5, sp500: 105.2 },
  { date: 'Nov 1', euAI: 106.8, stoxx: 103.8, sp500: 110.4 },
  { date: 'Nov 15', euAI: 109.1, stoxx: 102.1, sp500: 115.8 },
  { date: 'Dec 1', euAI: 112.4, stoxx: 105.2, sp500: 121.2 },
  { date: 'Dec 15', euAI: 115.8, stoxx: 107.4, sp500: 128.5 },
  { date: 'Jan 1', euAI: 118.3, stoxx: 108.1, sp500: 132.1 },
];

export function StockPerformanceChart() {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(120 20% 88%)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: 'hsl(170 30% 40%)' }}
          axisLine={{ stroke: 'hsl(120 20% 88%)' }}
        />
        <YAxis
          domain={[95, 140]}
          tick={{ fontSize: 12, fill: 'hsl(170 30% 40%)' }}
          axisLine={{ stroke: 'hsl(120 20% 88%)' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'white',
            border: '1px solid hsl(120 20% 88%)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          }}
          formatter={(value: number) => [value.toFixed(1), '']}
        />
        <Line
          type="monotone"
          dataKey="euAI"
          name="EU AI Index"
          stroke="hsl(120, 65%, 45%)"
          strokeWidth={2}
          dot={{ fill: 'hsl(120, 65%, 45%)', r: 4 }}
          activeDot={{ r: 6 }}
        />
        <Line
          type="monotone"
          dataKey="stoxx"
          name="STOXX 600 Tech"
          stroke="hsl(45, 85%, 50%)"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={{ fill: 'hsl(45, 85%, 50%)', r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="sp500"
          name="S&P 500 Tech"
          stroke="rgba(100, 100, 100, 0.6)"
          strokeWidth={2}
          dot={{ fill: 'rgba(100, 100, 100, 0.6)', r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
