import { useEffect } from 'react';
import { Coins, BarChart3, Building2, Zap, ArrowLeft, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { Header } from '@/components/Header';
import { ScrollReveal, StaggerContainer, StaggerItem } from '@/components/animations';
import {
  GoldMetricCard,
  GoldPriceChart,
  GoldMarketOverview,
  CentralBankReservesMap,
  GoldETFsTable,
  TokenizedGoldSection,
  GoldRegulationsSection,
  GoldMiningProduction,
  GoldDataSources,
} from '@/components/gold';
import { GOLD_METRICS, GOLD_DATA_SOURCES } from '@/data/goldFallback';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';

export default function GoldDashboard() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const metrics = GOLD_METRICS;
  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="EU Gold Trading Monitor - Gold Market Intelligence"
        description="Track gold spot prices (XAU/USD, XAU/EUR), ETF performance, tokenised gold (PAXG, XAUT), central bank reserves, and EU regulatory landscape for precious metals."
        keywords="gold trading, XAU/USD, XAU/EUR, gold ETF, PAXG, XAUT, tokenised gold, central bank gold reserves, MiCA, gold investment"
        url="/gold"
      />
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Back navigation */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Link
            to="/public-affairs"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Public Affairs
          </Link>
        </motion.div>

        {/* Related Monitor Banner */}
        <RelatedMonitorBanner currentMonitor="gold" className="mb-6" />

        {/* Page Header */}
        <motion.header
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <motion.div
              className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Coins className="w-6 h-6 text-amber-500" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              EU Gold Trading Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time tracking of gold spot prices, ETFs, tokenised gold, and EU regulatory landscape
          </p>
          <motion.div
            className="flex items-center justify-center gap-4 mt-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <RefreshCw className="w-3 h-3" />
              Data updated: {lastUpdated}
            </p>
            <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">
              {GOLD_DATA_SOURCES.length} Data Sources
            </Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          <StaggerItem variant="fadeUp">
            <GoldMetricCard
              icon={Coins}
              value={`$${metrics.xauUsd.toLocaleString()}`}
              label="XAU/USD Spot Price"
              trend={metrics.xauUsdYtd}
              trendPositive={true}
              sources={['LBMA', 'Metals-API']}
              color="gold"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <GoldMetricCard
              icon={BarChart3}
              value={metrics.globalEtfAum}
              label="Global ETF AUM"
              trend={metrics.etfHoldings}
              sources={['WGC']}
              color="blue"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <GoldMetricCard
              icon={Zap}
              value={metrics.tokenisedGoldCap}
              label="Tokenised Gold Cap"
              sources={['CoinGecko']}
              color="purple"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <GoldMetricCard
              icon={Building2}
              value={`${metrics.centralBankBuying} T`}
              label={`Central Bank Net Buying (${metrics.centralBankYear})`}
              sources={['WGC']}
              color="green"
            />
          </StaggerItem>
        </StaggerContainer>

        {/* Row 1: Price Chart + Quick Stats */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <GoldPriceChart />
            </div>
            <GoldMarketOverview />
          </div>
        </ScrollReveal>

        {/* Row 2: Central Bank Reserves Map (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <CentralBankReservesMap />
          </div>
        </ScrollReveal>

        {/* Row 3: ETFs Table (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <GoldETFsTable />
          </div>
        </ScrollReveal>

        {/* Row 4: Tokenized Gold + Regulations */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <TokenizedGoldSection />
            <GoldRegulationsSection />
          </div>
        </ScrollReveal>

        {/* Row 5: Mining Production (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <GoldMiningProduction />
          </div>
        </ScrollReveal>

        {/* Row 6: Data Sources (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <GoldDataSources />
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12 mt-6">
          <RelatedMonitorsSection currentMonitor="gold" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="EU Gold Trading Monitor"
        />
      </main>
    </div>
  );
}
