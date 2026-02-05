import { useEffect } from 'react';
import { Target, FileText, CheckCircle, Globe, ArrowLeft, TrendingUp, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { Header } from '@/components/Header';
import { ScrollReveal, StaggerContainer, StaggerItem } from '@/components/animations';
import {
  CMUMetricCard,
  CMUProgressIndex,
  QuickStats,
  LegislativePipeline,
  KeyDates,
  EUvsUSComparison,
  StartupScaleupSection,
  CMUIntegrationMap,
  CMUNewsFeed,
  ResearchFeed,
  DataSourcesGrid,
} from '@/components/cmu';
import { VCAngelSection } from '@/components/vcAngel';
import { FALLBACK_METRICS, getInForceLegislationCount } from '@/data/cmuFallback';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';

export default function CMUDashboard() {
  // Scroll to top on mount
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const metrics = FALLBACK_METRICS;
  const legislationCount = getInForceLegislationCount();
  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="EU Capital Markets Union Monitor - CMU Progress Tracker"
        description="Track the progress of the EU Capital Markets Union. Real-time monitoring of CMU legislation, cross-border investment flows, market integration, and financial services harmonization."
        keywords="Capital Markets Union, CMU, EU financial markets, cross-border investment, EU securities, financial services regulation, European Commission, single market"
        url="/cmu"
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
            to="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </motion.div>

        {/* Related Monitor Banner */}
        <RelatedMonitorBanner currentMonitor="cmu" className="mb-6" />

        {/* Page Header */}
        <motion.header
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <motion.div
              className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <TrendingUp className="w-6 h-6 text-primary" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              EU Capital Markets Union Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time tracking of CMU/SIU progress, legislation, and financial integration metrics
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
            <Badge className="bg-primary/10 text-primary border-primary/20">14 Data Sources</Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          <StaggerItem variant="fadeUp">
            <CMUMetricCard
              icon={Target}
              value={`${metrics.overallProgress}%`}
              label="CMU Progress Index"
              sources={['european_commission', 'ecb']}
              color="primary"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <CMUMetricCard
              icon={FileText}
              value={`${legislationCount}+`}
              label="Legislation In Force"
              trend="+3 in 2024"
              sources={['eur_lex']}
              color="secondary"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <CMUMetricCard
              icon={CheckCircle}
              value={metrics.actionPlanProgress}
              label="Action Plan 2020"
              trend="31% complete"
              sources={['european_commission']}
              color="accent"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <CMUMetricCard
              icon={Globe}
              value={metrics.integrationIndex.toFixed(3)}
              label="Integration Index"
              trend="-0.002 from 2019"
              sources={['ecb']}
              color="primary"
            />
          </StaggerItem>
        </StaggerContainer>

        {/* Row 1: CMU Progress Index + Quick Stats (aligned h-[320px]) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <CMUProgressIndex />
            </div>
            <QuickStats />
          </div>
        </ScrollReveal>

        {/* Row 2: Legislative Pipeline + Key Dates (aligned h-[420px]) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <LegislativePipeline />
            </div>
            <KeyDates />
          </div>
        </ScrollReveal>

        {/* Row 3: EU vs US Comparison (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <EUvsUSComparison />
          </div>
        </ScrollReveal>

        {/* Row 4: Startups & Scaleups (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <StartupScaleupSection />
          </div>
        </ScrollReveal>

        {/* Row 5: VC & Angel Ecosystem (collapsible section) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <VCAngelSection defaultExpanded={true} />
          </div>
        </ScrollReveal>

        {/* Row 6: Financial Integration Map (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <CMUIntegrationMap />
          </div>
        </ScrollReveal>

        {/* Row 7: News + Research (aligned h-[420px]) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <CMUNewsFeed />
            <ResearchFeed />
          </div>
        </ScrollReveal>

        {/* Row 8: Data Sources (full width card) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <DataSourcesGrid />
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12 mt-6">
          <RelatedMonitorsSection currentMonitor="cmu" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="EU Capital Markets Union Monitor"
        />
      </main>
    </div>
  );
}
