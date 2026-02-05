import { useState, useEffect, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Rocket, TrendingUp, Users, Building2, ExternalLink, AlertTriangle, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { SourceBadges } from './SourceBadge';
import type { DataSource } from '@/types/cmu';

interface StartupScaleupSectionProps {
  className?: string;
}

// Startup/Scaleup metrics data
const STARTUP_METRICS = {
  euVCInvestment: 52, // €52B in 2024
  usGapMultiple: 3.2, // US invests 3.2x more relative to GDP
  lateStageGap: 47, // 47% of EU late-stage deals are smaller than US average
  newUnicorns2024: 12,
  totalEUUnicorns: 350,
  avgSeriesCEU: 45, // €45M
  avgSeriesCUS: 92, // €92M
  pensionFundVC: 14, // Only 14% of EU VC from pension funds
  acquisitionExitEU: 89, // 89% of EU exits are acquisitions
  acquisitionExitUS: 62, // 62% in US
};

const FUNDING_BY_STAGE = [
  { stage: 'Seed', eu: 8, us: 15, color: 'hsl(120, 65%, 45%)' },
  { stage: 'Series A', eu: 15, us: 35, color: 'hsl(120, 65%, 50%)' },
  { stage: 'Series B', eu: 12, us: 40, color: 'hsl(120, 65%, 55%)' },
  { stage: 'Late Stage', eu: 17, us: 75, color: 'hsl(120, 65%, 60%)' },
];

const EU_SUPPORT_PROGRAMS = [
  {
    name: 'EIC Accelerator',
    description: 'Grants + equity for breakthrough innovation',
    budget: '€10B',
    url: 'https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en',
  },
  {
    name: 'InvestEU',
    description: 'EU guarantee for SME & startup funding',
    budget: '€26B',
    url: 'https://investeu.europa.eu/',
  },
  {
    name: 'ESCALAR',
    description: 'EIF programme for scaleup financing',
    budget: '€300M',
    url: 'https://www.eif.org/what_we_do/equity/escalar/',
  },
  {
    name: 'Tech Champions Initiative',
    description: 'Fund-of-funds for late-stage European tech',
    budget: '€3.75B',
    url: 'https://www.eif.org/what_we_do/equity/etci/',
  },
];

const SCALEUP_GAP_FACTS = [
  {
    stat: '89%',
    description: 'of EU unicorn exits are acquisitions (vs 62% in US)',
    sources: ['invest_europe', 'dealroom'] as DataSource[],
  },
  {
    stat: '€45M vs €92M',
    description: 'Average Series C round: EU vs US',
    sources: ['pitchbook', 'sifted'] as DataSource[],
  },
  {
    stat: '14%',
    description: 'of EU VC comes from pension funds (vs 35% US)',
    sources: ['invest_europe', 'draghi_report'] as DataSource[],
  },
  {
    stat: '3.2x',
    description: 'US invests more in VC relative to GDP',
    sources: ['eurostat', 'ecb'] as DataSource[],
  },
];

const REFERENCES = [
  {
    title: 'EU-Inc: Pan-European Company Structure',
    source: 'EU-INC',
    url: 'https://www.eu-inc.org/',
  },
  {
    title: 'EU Startup and Scaleup Strategy',
    source: 'European Commission',
    url: 'https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/jobs-and-economy/eu-startup-and-scaleup-strategy_en',
  },
  {
    title: 'Letta Report: Much More Than a Market',
    source: 'Enrico Letta',
    url: 'https://www.consilium.europa.eu/media/ny3j24sm/much-more-than-a-market-report-by-enrico-letta.pdf',
  },
  {
    title: 'Draghi Report: EU Competitiveness',
    source: 'Mario Draghi',
    url: 'https://commission.europa.eu/topics/eu-competitiveness/draghi-report_en',
  },
  {
    title: 'Regime 0: EU-wide incorporation for startups',
    source: 'Bruegel',
    url: 'https://www.bruegel.org/policy-brief/regime-0-europe-wide-incorporation-startups-kickstart-innovative-growth',
  },
  {
    title: 'Scaling EU startups face regulation maze',
    source: 'Forbes',
    url: 'https://www.forbes.com/sites/trevorclawson/2025/10/22/scaling-eu-startups-face-a-regulation-maze-but-change-may-be-coming/',
  },
  {
    title: 'Startups and Scaleups Data',
    source: 'EC Library',
    url: 'https://ec-europa-eu.libguides.com/startups-and-scaleups/data/selected',
  },
  {
    title: 'Scaleups and high-growth entrepreneurship',
    source: 'ScienceDirect',
    url: 'https://www.sciencedirect.com/science/article/pii/S0263237322000950',
  },
];

const CHART_COLORS = {
  eu: 'hsl(120, 65%, 45%)',
  us: 'hsl(45, 85%, 50%)',
  grid: 'hsl(120, 20%, 88%)',
};

// Animated counter hook
function useAnimatedCounter(end: number, duration: number = 2000, startOnView: boolean = true) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  useEffect(() => {
    if (!startOnView || isInView) {
      let startTime: number;
      const animate = (currentTime: number) => {
        if (!startTime) startTime = currentTime;
        const progress = Math.min((currentTime - startTime) / duration, 1);
        // Easing function for smooth deceleration
        const easeOut = 1 - Math.pow(1 - progress, 3);
        setCount(Math.floor(easeOut * end));
        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };
      requestAnimationFrame(animate);
    }
  }, [end, duration, isInView, startOnView]);

  return { count, ref };
}

// Animated Metric Card with counter
function AnimatedMetricCard({
  icon: Icon,
  value,
  numericValue,
  prefix = '',
  suffix = '',
  label,
  trend,
  color = 'primary',
  index,
}: {
  icon: React.ElementType;
  value: string;
  numericValue?: number;
  prefix?: string;
  suffix?: string;
  label: string;
  trend?: string;
  color?: 'primary' | 'secondary' | 'accent' | 'destructive';
  index: number;
}) {
  const colorClasses = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-secondary/10',
    accent: 'text-accent bg-accent/10',
    destructive: 'text-destructive bg-destructive/10',
  };

  const { count, ref } = useAnimatedCounter(numericValue || 0, 1500);
  const displayValue = numericValue ? `${prefix}${count}${suffix}` : value;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30, scale: 0.9 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: '-30px' }}
      transition={{
        duration: 0.5,
        delay: index * 0.1,
        type: 'spring',
        stiffness: 100,
      }}
      whileHover={{
        scale: 1.05,
        y: -5,
        transition: { duration: 0.2 },
      }}
      className="bg-muted/30 rounded-lg p-4 text-center cursor-default"
    >
      <motion.div
        className={`w-10 h-10 rounded-full ${colorClasses[color]} flex items-center justify-center mx-auto mb-2`}
        initial={{ scale: 0, rotate: -180 }}
        whileInView={{ scale: 1, rotate: 0 }}
        viewport={{ once: true }}
        transition={{
          delay: 0.2 + index * 0.1,
          type: 'spring',
          stiffness: 200,
          damping: 15,
        }}
        whileHover={{ rotate: 360 }}
      >
        <Icon className="w-5 h-5" />
      </motion.div>
      <motion.div
        className="text-2xl font-bold text-secondary"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.3 + index * 0.1 }}
      >
        {displayValue}
      </motion.div>
      <motion.div
        className="text-sm text-muted-foreground"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.4 + index * 0.1 }}
      >
        {label}
      </motion.div>
      {trend && (
        <motion.div
          className="text-xs text-muted-foreground mt-1"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 + index * 0.1 }}
        >
          {trend}
        </motion.div>
      )}
    </motion.div>
  );
}

// Animated Program Card
function AnimatedProgramCard({
  program,
  index,
}: {
  program: typeof EU_SUPPORT_PROGRAMS[0];
  index: number;
}) {
  return (
    <motion.a
      href={program.url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, x: 50 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: '-20px' }}
      transition={{
        duration: 0.4,
        delay: index * 0.1,
        type: 'spring',
        stiffness: 100,
      }}
      whileHover={{
        scale: 1.02,
        x: 5,
        backgroundColor: 'hsl(var(--background))',
        transition: { duration: 0.2 },
      }}
      className="flex items-start justify-between p-3 bg-background/50 rounded-lg group"
    >
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-secondary group-hover:text-primary transition-colors">
            {program.name}
          </span>
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            whileHover={{ opacity: 1, x: 0 }}
          >
            <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </motion.div>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{program.description}</p>
      </div>
      <motion.div whileHover={{ scale: 1.1 }}>
        <Badge variant="outline" className="text-xs bg-primary/5 text-primary border-primary/20 shrink-0">
          {program.budget}
        </Badge>
      </motion.div>
    </motion.a>
  );
}

// Animated Scaleup Gap Fact Card
function AnimatedGapFact({
  fact,
  index,
}: {
  fact: typeof SCALEUP_GAP_FACTS[0];
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, rotateY: -90 }}
      whileInView={{ opacity: 1, scale: 1, rotateY: 0 }}
      viewport={{ once: true, margin: '-20px' }}
      transition={{
        duration: 0.5,
        delay: index * 0.15,
        type: 'spring',
        stiffness: 100,
      }}
      whileHover={{
        scale: 1.05,
        boxShadow: '0 10px 30px rgba(239, 68, 68, 0.2)',
        transition: { duration: 0.2 },
      }}
      className="bg-background/50 rounded-lg p-3"
    >
      <motion.div
        className="text-lg font-bold text-destructive"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.3 + index * 0.15 }}
      >
        {fact.stat}
      </motion.div>
      <p className="text-xs text-muted-foreground mt-1">{fact.description}</p>
      <div className="mt-2">
        <SourceBadges sources={fact.sources} size="sm" />
      </div>
    </motion.div>
  );
}

// Animated Reference Link
function AnimatedReference({
  reference,
  index,
}: {
  reference: typeof REFERENCES[0];
  index: number;
}) {
  return (
    <motion.a
      href={reference.url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      whileHover={{
        x: 5,
        color: 'hsl(var(--primary))',
        transition: { duration: 0.2 },
      }}
      className="flex items-center gap-2 text-xs text-muted-foreground hover:text-primary transition-colors group"
    >
      <motion.div
        whileHover={{ rotate: 45 }}
        transition={{ duration: 0.2 }}
      >
        <ExternalLink className="w-3 h-3 shrink-0" />
      </motion.div>
      <span className="truncate">
        <span className="font-medium">{reference.source}:</span> {reference.title}
      </span>
    </motion.a>
  );
}

export function StartupScaleupSection({ className = '' }: StartupScaleupSectionProps) {
  const [chartVisible, setChartVisible] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const isChartInView = useInView(chartRef, { once: true, margin: '-50px' });

  useEffect(() => {
    if (isChartInView) {
      const timer = setTimeout(() => setChartVisible(true), 300);
      return () => clearTimeout(timer);
    }
  }, [isChartInView]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.6 }}
    >
      <Card className={`border-border/50 overflow-hidden ${className}`}>
        <CardHeader className="pb-2">
          <motion.div
            className="flex items-center justify-between flex-wrap gap-4"
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-center gap-2">
              <motion.div
                initial={{ scale: 0, rotate: -180 }}
                whileInView={{ scale: 1, rotate: 0 }}
                viewport={{ once: true }}
                transition={{
                  type: 'spring',
                  stiffness: 200,
                  damping: 15,
                  delay: 0.2,
                }}
                whileHover={{
                  y: -5,
                  rotate: 15,
                  transition: { duration: 0.3 },
                }}
                className="relative"
              >
                <Rocket className="w-5 h-5 text-primary" />
                <motion.div
                  className="absolute -top-1 -right-1"
                  initial={{ scale: 0 }}
                  whileInView={{ scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.5 }}
                >
                  <Sparkles className="w-3 h-3 text-accent" />
                </motion.div>
              </motion.div>
              <CardTitle className="text-xl text-secondary">
                EU Startups & Scaleups Financing
              </CardTitle>
            </div>
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <SourceBadges
                sources={['eurostat', 'invest_europe', 'dealroom', 'sifted', 'letta_report', 'draghi_report', 'bruegel']}
                size="sm"
              />
            </motion.div>
          </motion.div>
          <motion.p
            className="text-sm text-muted-foreground mt-2"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 }}
          >
            Tracking venture capital, growth funding, and exit markets — a key CMU objective
          </motion.p>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Top Metrics Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <AnimatedMetricCard
              icon={TrendingUp}
              value={`€${STARTUP_METRICS.euVCInvestment}B`}
              numericValue={STARTUP_METRICS.euVCInvestment}
              prefix="€"
              suffix="B"
              label="EU VC Investment 2024"
              color="primary"
              index={0}
            />
            <AnimatedMetricCard
              icon={AlertTriangle}
              value={`${STARTUP_METRICS.usGapMultiple}x`}
              label="US Funding Gap"
              trend="relative to GDP"
              color="destructive"
              index={1}
            />
            <AnimatedMetricCard
              icon={Building2}
              value={`${STARTUP_METRICS.newUnicorns2024}`}
              numericValue={STARTUP_METRICS.newUnicorns2024}
              label="New Unicorns (2024)"
              trend={`${STARTUP_METRICS.totalEUUnicorns} total`}
              color="accent"
              index={2}
            />
            <AnimatedMetricCard
              icon={Users}
              value={`${STARTUP_METRICS.pensionFundVC}%`}
              numericValue={STARTUP_METRICS.pensionFundVC}
              suffix="%"
              label="Pension Fund VC"
              trend="vs 35% in US"
              color="secondary"
              index={3}
            />
          </div>

          {/* Two Column Layout: Chart + Programs */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Funding by Stage Chart */}
            <motion.div
              ref={chartRef}
              className="bg-muted/20 rounded-lg p-4"
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-30px' }}
              transition={{ duration: 0.5 }}
            >
              <motion.h3
                className="text-sm font-medium text-secondary mb-4"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                VC Funding by Stage (€B) — EU vs US
              </motion.h3>
              <div className="h-56">
                <AnimatePresence>
                  {chartVisible && (
                    <motion.div
                      initial={{ opacity: 0, scaleY: 0 }}
                      animate={{ opacity: 1, scaleY: 1 }}
                      transition={{ duration: 0.5, ease: 'easeOut' }}
                      style={{ height: '100%', originY: 1 }}
                    >
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={FUNDING_BY_STAGE}
                          margin={{ top: 10, right: 10, left: 0, bottom: 10 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                          <XAxis dataKey="stage" fontSize={11} tickLine={false} axisLine={false} />
                          <YAxis fontSize={10} tickLine={false} axisLine={false} tickFormatter={(v) => `€${v}B`} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: 'white',
                              border: `1px solid ${CHART_COLORS.grid}`,
                              borderRadius: '8px',
                              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                            }}
                            formatter={(value: number, name: string) => [`€${value}B`, name === 'eu' ? 'EU' : 'US']}
                          />
                          <Bar
                            dataKey="eu"
                            name="EU"
                            fill={CHART_COLORS.eu}
                            radius={[4, 4, 0, 0]}
                            animationBegin={0}
                            animationDuration={800}
                          />
                          <Bar
                            dataKey="us"
                            name="US"
                            fill={CHART_COLORS.us}
                            radius={[4, 4, 0, 0]}
                            animationBegin={200}
                            animationDuration={800}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <motion.div
                className="flex justify-center gap-6 mt-2"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.6 }}
              >
                <motion.div
                  className="flex items-center gap-2"
                  whileHover={{ scale: 1.1 }}
                >
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: CHART_COLORS.eu }} />
                  <span className="text-xs text-muted-foreground">EU</span>
                </motion.div>
                <motion.div
                  className="flex items-center gap-2"
                  whileHover={{ scale: 1.1 }}
                >
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: CHART_COLORS.us }} />
                  <span className="text-xs text-muted-foreground">US</span>
                </motion.div>
              </motion.div>
            </motion.div>

            {/* EU Support Programs */}
            <motion.div
              className="bg-muted/20 rounded-lg p-4"
              initial={{ opacity: 0, x: 50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-30px' }}
              transition={{ duration: 0.5 }}
            >
              <motion.h3
                className="text-sm font-medium text-secondary mb-4"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                EU Support Programs for Startups & Scaleups
              </motion.h3>
              <div className="space-y-3">
                {EU_SUPPORT_PROGRAMS.map((program, index) => (
                  <AnimatedProgramCard key={program.name} program={program} index={index} />
                ))}
              </div>
            </motion.div>
          </div>

          {/* The Scaleup Gap */}
          <motion.div
            className="bg-destructive/5 border border-destructive/20 rounded-lg p-4 overflow-hidden"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-30px' }}
            transition={{ duration: 0.5 }}
          >
            <motion.h3
              className="text-sm font-medium text-secondary mb-4 flex items-center gap-2"
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
            >
              <motion.div
                animate={{
                  scale: [1, 1.2, 1],
                  rotate: [0, 10, -10, 0],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  repeatDelay: 3,
                }}
              >
                <AlertTriangle className="w-4 h-4 text-destructive" />
              </motion.div>
              The Scaleup Gap: Why EU startups struggle to grow
            </motion.h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {SCALEUP_GAP_FACTS.map((fact, index) => (
                <AnimatedGapFact key={index} fact={fact} index={index} />
              ))}
            </div>
          </motion.div>

          {/* References & Sources */}
          <motion.div
            className="border-t border-border/50 pt-4"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <motion.h4
              className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wider"
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              Key References & Data Sources
            </motion.h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {REFERENCES.map((ref, index) => (
                <AnimatedReference key={index} reference={ref} index={index} />
              ))}
            </div>
          </motion.div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
