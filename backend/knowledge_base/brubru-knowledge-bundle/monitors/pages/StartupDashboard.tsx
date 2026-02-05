import { useEffect } from 'react';
import { Rocket, Building2, Scale, TrendingUp, ArrowLeft, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { Header } from '@/components/Header';
import { ScrollReveal, StaggerContainer, StaggerItem } from '@/components/animations';
import {
  StartupMetricCard,
  StartupEcosystemMap,
  FundingComparisonChart,
  EUFundingPrograms,
  StartupLegislativePipeline,
  RegimeSpotlight,
  StartupQuickStats,
  StartupDataSources,
} from '@/components/startup';
import { STARTUP_METRICS, DATA_SOURCES } from '@/data/startupFallback';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';

export default function StartupDashboard() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const metrics = STARTUP_METRICS;
  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="EU Startup Monitor - European Startup Ecosystem Tracker"
        description="Track the European startup ecosystem. Real-time data on unicorns, VC funding, EU vs US comparisons, startup legislation, and the 28th Regime proposal."
        keywords="European startups, EU startup ecosystem, unicorns, venture capital, 28th regime, EU-Inc, startup legislation, European Innovation Council, EIC"
        url="/startups"
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
        <RelatedMonitorBanner currentMonitor="startups" className="mb-6" />

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
              <Rocket className="w-6 h-6 text-primary" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              EU Startup Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Tracking the European startup ecosystem, funding landscape, and regulatory environment
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
            <Badge className="bg-primary/10 text-primary border-primary/20">
              {DATA_SOURCES.length} Data Sources
            </Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          <StaggerItem variant="fadeUp">
            <StartupMetricCard
              icon={TrendingUp}
              value={metrics.ecosystemValue}
              label="European Tech Value"
              sources={['Atomico', 'Dealroom']}
              color="primary"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <StartupMetricCard
              icon={Rocket}
              value={metrics.activeUnicorns.toString()}
              label="Active Unicorns"
              trend={`+${metrics.newUnicorns2025} in 2025`}
              trendPositive={true}
              sources={['Dealroom']}
              color="accent"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <StartupMetricCard
              icon={Building2}
              value={metrics.vcFunding2024}
              label="VC Funding (2024)"
              trend={metrics.vcFundingChange}
              trendPositive={false}
              sources={['Crunchbase', 'PitchBook']}
              color="blue"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <StartupMetricCard
              icon={Scale}
              value={metrics.activeStartups}
              label="Active Startups"
              sources={['StartupBlink']}
              color="purple"
            />
          </StaggerItem>
        </StaggerContainer>

        {/* Row 1: Ecosystem Map (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <StartupEcosystemMap />
          </div>
        </ScrollReveal>

        {/* Row 2: EU vs US Comparison + Quick Stats */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <FundingComparisonChart />
            </div>
            <StartupQuickStats />
          </div>
        </ScrollReveal>

        {/* Row 3: EU Funding Programs (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <EUFundingPrograms />
          </div>
        </ScrollReveal>

        {/* Row 4: Legislative Pipeline (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6">
            <StartupLegislativePipeline />
          </div>
        </ScrollReveal>

        {/* Row 5: 28th Regime Spotlight (centered) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="mb-6 max-w-3xl mx-auto">
            <RegimeSpotlight />
          </div>
        </ScrollReveal>

        {/* Row 6: Data Sources (full width) */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <StartupDataSources />
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12 mt-6">
          <RelatedMonitorsSection currentMonitor="startups" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="EU Startup Monitor"
        />
      </main>
    </div>
  );
}
