import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  TrendingDown, DollarSign, Monitor, Zap,
  Building2, TrendingUp, Shield, Clock,
  FileText, ExternalLink, CheckCircle, Circle, AlertCircle
} from 'lucide-react';

// Source Badge Component
const SourceBadge = ({ source, variant = 'default' }: { source: string; variant?: 'default' | 'blue' | 'red' | 'green' | 'amber' }) => {
  const variants = {
    default: 'bg-primary/10 text-primary border-primary/30',
    blue: 'bg-blue-500/10 text-blue-600 border-blue-500/30',
    red: 'bg-red-500/10 text-red-600 border-red-500/30',
    green: 'bg-green-500/10 text-green-600 border-green-500/30',
    amber: 'bg-amber-500/10 text-amber-700 border-amber-500/30',
  };

  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${variants[variant]}`}>
      {source}
    </span>
  );
};

/**
 * Three Reports Overview Cards - Letta, Draghi, Niinistö
 */
export function ThreeReportsOverview() {
  const reports = [
    {
      name: 'Letta Report',
      subtitle: 'Single Market',
      published: '18 Apr 2024',
      keyFigure: '€300B',
      keyFigureLabel: 'Annual savings drain',
      focus: 'Fifth Freedom',
      footer: '65 cities • 400 meetings',
      color: 'blue',
      icon: Building2,
    },
    {
      name: 'Draghi Report',
      subtitle: 'Competitiveness',
      published: '9 Sep 2024',
      keyFigure: '€800B/yr',
      keyFigureLabel: 'Investment needed',
      focus: 'Investment Gap',
      footer: '400 pages • 383 recommendations',
      color: 'red',
      icon: TrendingUp,
    },
    {
      name: 'Niinistö Report',
      subtitle: 'Defence & Security',
      published: '30 Oct 2024',
      keyFigure: '20% budget',
      keyFigureLabel: 'For security',
      focus: 'Preparedness',
      footer: '165 pages • ~80 recommendations',
      color: 'green',
      icon: Shield,
    },
  ];

  const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
    blue: { bg: 'bg-blue-100', text: 'text-blue-600', border: 'border-t-blue-500' },
    red: { bg: 'bg-red-100', text: 'text-red-600', border: 'border-t-red-500' },
    green: { bg: 'bg-green-100', text: 'text-green-600', border: 'border-t-green-500' },
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {reports.map((report, i) => {
        const Icon = report.icon;
        const colors = colorClasses[report.color];
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className={`h-full border-t-4 ${colors.border}`}>
              <CardContent className="p-5">
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-12 h-12 rounded-full ${colors.bg} flex items-center justify-center`}>
                    <Icon className={`w-6 h-6 ${colors.text}`} />
                  </div>
                  <div>
                    <h3 className="font-bold text-secondary">{report.name}</h3>
                    <p className="text-xs text-muted-foreground">{report.subtitle}</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Published</span>
                    <span className="font-medium text-secondary">{report.published}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Key Figure</span>
                    <span className={`font-bold ${colors.text}`}>{report.keyFigure}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Focus</span>
                    <span className="text-secondary">{report.focus}</span>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t">
                  <span className="text-xs text-muted-foreground">{report.footer}</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}

/**
 * Key Metrics Cards - EU competitiveness gaps
 */
export function CompetitivenessMetrics() {
  const metrics = [
    {
      icon: TrendingDown,
      value: '30%',
      label: 'EU-US GDP Gap',
      subtext: 'Up from 15% in 2002',
      badge: 'Widening',
      color: 'red'
    },
    {
      icon: DollarSign,
      value: '€800B',
      label: 'Annual Investment Needed',
      subtext: '4.5-5% of EU GDP',
      badge: 'Per Year',
      color: 'amber'
    },
    {
      icon: Monitor,
      value: '4/50',
      label: 'EU Tech Companies',
      subtext: 'In global top 50',
      badge: 'US: 30+',
      color: 'blue'
    },
    {
      icon: Zap,
      value: '2-3x',
      label: 'Energy Cost Gap',
      subtext: 'vs United States',
      badge: 'Gas: 4-5x',
      color: 'orange'
    }
  ];

  const colorClasses: Record<string, { bg: string; text: string; badge: string }> = {
    red: { bg: 'bg-red-100', text: 'text-red-600', badge: 'bg-red-100 text-red-600 border-red-200' },
    amber: { bg: 'bg-amber-100', text: 'text-amber-600', badge: 'bg-amber-100 text-amber-600 border-amber-200' },
    blue: { bg: 'bg-blue-100', text: 'text-blue-600', badge: 'bg-blue-100 text-blue-600 border-blue-200' },
    orange: { bg: 'bg-orange-100', text: 'text-orange-600', badge: 'bg-orange-100 text-orange-600 border-orange-200' }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {metrics.map((metric, i) => {
        const Icon = metric.icon;
        const colors = colorClasses[metric.color];
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className="h-full hover:shadow-lg transition-all hover:-translate-y-1">
              <CardContent className="p-5 text-center">
                <div className={`w-14 h-14 mx-auto rounded-full ${colors.bg} flex items-center justify-center mb-3`}>
                  <Icon className={`w-7 h-7 ${colors.text}`} />
                </div>
                <div className="text-3xl font-bold text-secondary mb-1">{metric.value}</div>
                <div className="text-sm text-muted-foreground">{metric.label}</div>
                <div className={`text-xs ${colors.text} font-medium mt-1`}>{metric.subtext}</div>
                <div className="mt-2">
                  <span className={`text-xs px-3 py-1 rounded-full border ${colors.badge}`}>
                    {metric.badge}
                  </span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}

/**
 * Defence Fragmentation Visual
 */
export function DefenceFragmentationCard() {
  return (
    <Card className="mb-8 bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-200 flex items-center justify-center">
            <Shield className="w-5 h-5 text-green-700" />
          </div>
          <div>
            <CardTitle>EU Defence Fragmentation</CardTitle>
            <p className="text-sm text-muted-foreground">The cost of not integrating European defence</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SourceBadge source="Letta" variant="green" />
          <SourceBadge source="Draghi" variant="green" />
          <SourceBadge source="Niinistö" variant="green" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Tank Types Comparison */}
          <Card className="bg-white">
            <CardContent className="p-4 text-center">
              <div className="text-sm text-muted-foreground mb-2">Battle Tank Types</div>
              <div className="flex items-end justify-center gap-8">
                <div>
                  <div className="text-4xl font-bold text-red-600">12</div>
                  <div className="text-xs text-muted-foreground">EU</div>
                </div>
                <div className="text-2xl text-muted-foreground/30">vs</div>
                <div>
                  <div className="text-4xl font-bold text-green-600">1</div>
                  <div className="text-xs text-muted-foreground">USA</div>
                </div>
              </div>
              <div className="text-xs text-center text-muted-foreground pt-3 mt-3 border-t">
                Source: Draghi Report
              </div>
            </CardContent>
          </Card>

          {/* National Allocation */}
          <Card className="bg-white">
            <CardContent className="p-4 text-center">
              <div className="text-sm text-muted-foreground mb-2">National vs Joint Funding</div>
              <div className="relative w-32 h-32 mx-auto">
                <svg className="w-full h-full" viewBox="0 0 36 36">
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="hsl(var(--border))"
                    strokeWidth="3"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="3"
                    strokeDasharray="82, 100"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">82%</div>
                    <div className="text-xs text-muted-foreground">National</div>
                  </div>
                </div>
              </div>
              <div className="text-xs text-center text-muted-foreground pt-3 mt-3 border-t">
                Only 18% joint investment
              </div>
            </CardContent>
          </Card>

          {/* Annual Cost */}
          <Card className="bg-white">
            <CardContent className="p-4 text-center">
              <div className="text-sm text-muted-foreground mb-2">Annual Fragmentation Cost</div>
              <div className="text-4xl font-bold text-amber-600 mb-2">€100B</div>
              <div className="text-sm text-muted-foreground">Lost to inefficiency</div>
              <div className="mt-2">
                <span className="text-xs px-3 py-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                  EP Estimate
                </span>
              </div>
              <div className="text-xs text-center text-muted-foreground pt-3 mt-3 border-t">
                Potential savings: €57B+
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-6 pt-4 border-t border-green-200 flex flex-wrap items-center justify-between gap-4">
          <div className="text-xs text-green-700">
            <strong>All three reports agree:</strong> 78-80% of recent European procurement went to non-EU suppliers
          </div>
          <Link
            to="/defence"
            className="inline-flex items-center gap-2 px-4 py-2 bg-green-700 hover:bg-green-800 text-sm font-medium rounded-lg transition-colors shadow-md"
            style={{ color: '#ffffff' }}
          >
            <Shield className="w-4 h-4" />
            <span style={{ color: '#ffffff' }}>EU Defence Monitor</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Investment Requirements Chart
 */
export function InvestmentRequirementsChart() {
  const investments = [
    { label: 'Clean Energy Transition', amount: '€300B/yr', percentage: 37.5, color: 'bg-green-500' },
    { label: 'R&D / Framework Programme 10', amount: '€200B total', percentage: 25, color: 'bg-blue-500' },
    { label: 'Electric Mobility', amount: '€150B/yr', percentage: 18.75, color: 'bg-purple-500' },
    { label: 'Defence (over decade)', amount: '€500B total', percentage: 62.5, color: 'bg-red-500' },
    { label: 'Security & Preparedness (20% MFF)', amount: '€200B MFF', percentage: 25, color: 'bg-amber-500' },
  ];

  return (
    <Card className="mb-8">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-5 h-5 text-amber-600" />
            <CardTitle>Investment Requirements by Sector</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">Draghi Report: €750-800B additional annual investment needed</p>
        </div>
        <SourceBadge source="Draghi Report" variant="red" />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {investments.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium text-foreground">{item.label}</span>
                <span className="text-secondary font-bold">{item.amount}</span>
              </div>
              <div className="h-6 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full ${item.color} rounded-full transition-all duration-500`}
                  style={{ width: `${item.percentage}%` }}
                />
              </div>
            </motion.div>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t flex flex-wrap items-center justify-between text-xs text-muted-foreground">
          <span>Note: Some figures are annual, others span the MFF/decade period</span>
          <span>Marshall Plan: 1-2% GDP/yr</span>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Implementation Progress Grid
 */
export function ImplementationProgress() {
  const progress = [
    { label: 'Fully Implemented', percentage: '11.2%', count: '43 recommendations', color: 'green', icon: CheckCircle },
    { label: 'Partially Done', percentage: '20.1%', count: '77 recommendations', color: 'blue', icon: Circle },
    { label: 'In Progress', percentage: '46.0%', count: '176 recommendations', color: 'amber', icon: Clock },
    { label: 'Untouched', percentage: '22.7%', count: '87 recommendations', color: 'red', icon: AlertCircle },
  ];

  const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
    green: { bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-200' },
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-200' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-200' },
    red: { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-200' },
  };

  return (
    <Card className="mb-8">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-secondary" />
            <CardTitle>Implementation Reality Check</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">Draghi Observatory assessment (September 2025) - One year after publication</p>
        </div>
        <SourceBadge source="Draghi Observatory" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {progress.map((item, i) => {
            const Icon = item.icon;
            const colors = colorClasses[item.color];
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={`text-center p-4 rounded-lg border ${colors.bg} ${colors.border}`}
              >
                <div className={`text-3xl font-bold ${colors.text} mb-1`}>{item.percentage}</div>
                <div className={`text-sm font-medium ${colors.text}`}>{item.label}</div>
                <div className="text-xs text-muted-foreground mt-1">{item.count}</div>
              </motion.div>
            );
          })}
        </div>

        <div className="bg-muted/50 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center shrink-0 mt-0.5">
              <AlertCircle className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-foreground">
                <strong>Draghi's assessment (Sep 2025):</strong> "Every challenge he had pointed out had worsened."
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Best sectors: Critical raw materials (33.3%), Transport (26.8%) | Worst: Pharmaceuticals (0% full implementation)
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Related Reports Banner
 */
export function RelatedReportsBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="rounded-xl p-6 mb-8"
      style={{
        background: 'linear-gradient(135deg, #003399 0%, #002266 100%)',
        border: '2px solid #FFCC00'
      }}
    >
      <div className="flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center shrink-0"
            style={{ background: '#1e3a8a', border: '2px solid #FFCC00' }}
          >
            <FileText className="w-8 h-8" style={{ color: '#FFCC00' }} />
          </div>
          <div>
            <h3 className="text-xl font-bold mb-1" style={{ color: '#ffffff' }}>
              Explore More EU Policy Analysis
            </h3>
            <p style={{ color: '#ffffff' }}>
              Deep-dive reports on Capital Markets Union, Defence spending, Trade policy, and more.
            </p>
          </div>
        </div>
        <Link
          to="/public-affairs"
          className="shrink-0 inline-flex items-center gap-2 px-6 py-3 font-semibold rounded-lg transition-colors shadow-lg"
          style={{ background: '#FFCC00', color: '#000000' }}
        >
          <span style={{ color: '#000000' }}>View All Reports</span>
          <svg className="w-4 h-4" fill="none" stroke="#000000" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </Link>
      </div>
    </motion.div>
  );
}
