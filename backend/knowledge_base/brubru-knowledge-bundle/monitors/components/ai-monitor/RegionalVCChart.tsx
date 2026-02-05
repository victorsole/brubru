import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const data = [
  { name: 'France', value: 1300, color: 'hsl(120, 65%, 45%)' },
  { name: 'CEE', value: 1400, color: 'hsl(120, 55%, 35%)' },
  { name: 'Germany', value: 910, color: 'hsl(120, 65%, 45%)' },
  { name: 'UK', value: 645, color: 'rgba(100, 100, 100, 0.6)' },
  { name: 'Spain', value: 180, color: 'hsl(120, 55%, 55%)' },
  { name: 'Italy', value: 150, color: 'hsl(120, 45%, 65%)' },
  { name: 'Rest of EU', value: 350, color: 'rgba(150, 150, 150, 0.6)' },
];

export function RegionalVCChart() {
  return (
    <ResponsiveContainer width="100%" height={256}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(120 20% 88%)" horizontal={true} vertical={false} />
        <XAxis
          type="number"
          domain={[0, 1600]}
          tick={{ fontSize: 12, fill: 'hsl(170 30% 40%)' }}
          axisLine={{ stroke: 'hsl(120 20% 88%)' }}
          tickFormatter={(value) => `€${value}M`}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 12, fill: 'hsl(170 30% 40%)' }}
          axisLine={{ stroke: 'hsl(120 20% 88%)' }}
          width={75}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'white',
            border: '1px solid hsl(120 20% 88%)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          }}
          formatter={(value: number) => [`€${value}M`, 'AI VC Funding']}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
