import { useEffect } from 'react';
import { Atom, Euro, Globe, TrendingUp, Calendar, Building, ArrowLeft, ExternalLink, Rocket, FileText, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';

import { Header } from '@/components/Header';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollReveal, StaggerContainer, StaggerItem } from '@/components/animations';

export default function QuantumDashboard() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  const keyMetrics = [
    { icon: Euro, value: '€11B', label: 'Public Funding Since 2018', color: 'primary' },
    { icon: Globe, value: '32%', label: 'Global Quantum Companies', color: 'secondary' },
    { icon: TrendingUp, value: '29-33%', label: 'Market CAGR', color: 'accent' },
    { icon: Building, value: '140+', label: 'QuIC Members', color: 'primary' },
  ];

  const timeline = [
    { date: 'July 2025', event: 'Quantum Europe Strategy', status: 'completed', description: 'COM(2025) 363 - First comprehensive EU policy framework' },
    { date: 'Dec 2025', event: 'Call for Evidence Closed', status: 'completed', description: 'Input gathered for upcoming Quantum Act' },
    { date: 'Q2 2026', event: 'Quantum Act Proposal', status: 'upcoming', description: 'Legislative framework for governance and investments' },
    { date: '2026', event: 'Eagle-1 Satellite Launch', status: 'upcoming', description: 'ESA QKD satellite for EuroQCI infrastructure' },
    { date: 'End 2026', event: 'PQC Transition Begins', status: 'upcoming', description: 'Post-Quantum Cryptography migration deadline' },
    { date: '2030', event: 'Critical Infrastructure PQC', status: 'future', description: 'Full PQC implementation for critical systems' },
    { date: '2035', event: 'Full PQC Transition', status: 'future', description: 'Complete quantum-safe cryptography deployment' },
  ];

  const topCompanies = [
    { name: 'IQM Quantum Computers', country: 'Finland', funding: '€558M+', tech: 'Superconducting Qubits', highlight: "Europe's best-funded quantum startup" },
    { name: 'Quantinuum', country: 'UK', funding: '$600M+', tech: 'Trapped Ions', highlight: '$10B valuation, Helios computer' },
    { name: 'Pasqal', country: 'France', funding: '€145M+', tech: 'Neutral Atoms', highlight: 'Founded by Nobel laureate' },
    { name: 'Alice & Bob', country: 'France', funding: '€130M+', tech: 'Cat Qubits', highlight: '200x error reduction' },
    { name: 'Quandela', country: 'France', funding: '€50M+', tech: 'Photonics', highlight: "Europe's first quantum factory" },
  ];

  const nationalStrategies = [
    { country: 'Germany', investment: '€3B', period: '2020-2026', focus: '2 error-corrected computers by 2030' },
    { country: 'France', investment: '€1.8B', period: '2021-2025', focus: '128 logical qubits by 2030' },
    { country: 'Netherlands', investment: '€900M', period: '2021-2026', focus: 'Quantum Delta NL ecosystem' },
    { country: 'Spain', investment: '€808M', period: '2025-2030', focus: 'New strategy launch' },
    { country: 'Italy', investment: '€227M', period: '2021-2024', focus: 'EuroHPC integration' },
  ];

  const colorClasses = {
    primary: 'bg-primary/10 text-primary',
    secondary: 'bg-cyan-500/10 text-cyan-600',
    accent: 'bg-green-500/10 text-green-600',
  };

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="EU Quantum Monitor - European Quantum Computing Policy Tracker"
        description="Track EU quantum computing policy, funding, and market developments. Monitor the Quantum Act, EuroQCI infrastructure, and European quantum startups."
        keywords="EU quantum computing, Quantum Act, quantum policy, IQM, Pasqal, EuroQCI, quantum investment, European quantum"
        url="/quantum"
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
            Back to EU Public Affairs
          </Link>
        </motion.div>

        {/* Related Monitor Banner */}
        <RelatedMonitorBanner currentMonitor="quantum" className="mb-6" />

        {/* Page Header */}
        <motion.header
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <motion.div
              className="w-12 h-12 rounded-full bg-cyan-500/10 flex items-center justify-center"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Atom className="w-6 h-6 text-cyan-600" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              EU Quantum Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Track EU quantum policy, funding, and the upcoming Quantum Act
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
            <Badge className="bg-cyan-500/10 text-cyan-600 border-cyan-500/20">New</Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          {keyMetrics.map((metric) => {
            const IconComponent = metric.icon;
            return (
              <StaggerItem key={metric.label} variant="fadeUp">
                <Card className="shadow-soft border-border/50 hover:shadow-lg transition-all h-full">
                  <CardContent className="p-6 text-center">
                    <div className={`w-12 h-12 rounded-full ${colorClasses[metric.color]} flex items-center justify-center mx-auto mb-4`}>
                      <IconComponent className="w-6 h-6" />
                    </div>
                    <p className={`text-3xl font-bold ${metric.color === 'primary' ? 'text-primary' : metric.color === 'secondary' ? 'text-cyan-600' : 'text-green-600'}`}>
                      {metric.value}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">{metric.label}</p>
                  </CardContent>
                </Card>
              </StaggerItem>
            );
          })}
        </StaggerContainer>

        {/* Row 1: Policy Timeline + National Strategies */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Policy Timeline */}
            <Card className="shadow-soft border-border/50 h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-secondary">
                  <Calendar className="w-5 h-5 text-cyan-600" />
                  Policy Timeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {timeline.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div className={`w-3 h-3 rounded-full ${
                          item.status === 'completed' ? 'bg-green-500' :
                          item.status === 'upcoming' ? 'bg-amber-500' : 'bg-gray-300'
                        }`} />
                        {idx < timeline.length - 1 && <div className="w-0.5 h-full bg-border mt-1" />}
                      </div>
                      <div className="flex-1 pb-4">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-secondary">{item.date}</span>
                          <Badge className={`text-xs ${
                            item.status === 'completed' ? 'bg-green-100 text-green-700' :
                            item.status === 'upcoming' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {item.status}
                          </Badge>
                        </div>
                        <p className="text-cyan-600 font-medium">{item.event}</p>
                        <p className="text-sm text-muted-foreground">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* National Strategies */}
            <Card className="shadow-soft border-border/50 h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-secondary">
                  <Globe className="w-5 h-5 text-cyan-600" />
                  National Strategies
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs text-muted-foreground uppercase border-b border-border">
                        <th className="pb-3">Country</th>
                        <th className="pb-3">Investment</th>
                        <th className="pb-3">Period</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nationalStrategies.map((strategy) => (
                        <tr key={strategy.country} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
                          <td className="py-3 font-medium text-secondary">{strategy.country}</td>
                          <td className="py-3 text-cyan-600 font-semibold">{strategy.investment}</td>
                          <td className="py-3 text-muted-foreground text-sm">{strategy.period}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-muted-foreground mt-4">
                  Source: National quantum strategies and JRC reports
                </p>
              </CardContent>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 2: Top Companies */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="shadow-soft border-border/50 mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-secondary">
                <Rocket className="w-5 h-5 text-cyan-600" />
                Top European Quantum Companies
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                {topCompanies.map((company) => (
                  <div
                    key={company.name}
                    className="p-4 rounded-lg border border-border/50 hover:border-cyan-500/30 hover:bg-cyan-50/50 transition-all"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h3 className="font-semibold text-secondary text-sm">{company.name}</h3>
                        <p className="text-xs text-muted-foreground">{company.country}</p>
                      </div>
                    </div>
                    <Badge className="bg-cyan-100 text-cyan-700 mb-2">{company.funding}</Badge>
                    <p className="text-xs text-cyan-600 font-medium mb-1">{company.tech}</p>
                    <p className="text-xs text-muted-foreground">{company.highlight}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 3: Key Documents */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="shadow-soft border-border/50 mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-secondary">
                <FileText className="w-5 h-5 text-cyan-600" />
                Key Documents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <a
                  href="https://digital-strategy.ec.europa.eu/en/policies/quantum"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:border-cyan-500/30 hover:bg-cyan-50/50 transition-all group"
                >
                  <div>
                    <p className="font-medium text-secondary group-hover:text-cyan-600 transition-colors">Quantum Europe Strategy 2025</p>
                    <p className="text-sm text-muted-foreground">COM(2025) 363</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-cyan-600" />
                </a>
                <a
                  href="https://digital-strategy.ec.europa.eu/en/policies/european-quantum-communication-infrastructure-euroqci"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:border-cyan-500/30 hover:bg-cyan-50/50 transition-all group"
                >
                  <div>
                    <p className="font-medium text-secondary group-hover:text-cyan-600 transition-colors">EuroQCI Initiative</p>
                    <p className="text-sm text-muted-foreground">Quantum Communication Infrastructure</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-cyan-600" />
                </a>
                <a
                  href="https://digital-strategy.ec.europa.eu/en/policies/quantum-technologies-flagship"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:border-cyan-500/30 hover:bg-cyan-50/50 transition-all group"
                >
                  <div>
                    <p className="font-medium text-secondary group-hover:text-cyan-600 transition-colors">Quantum Flagship</p>
                    <p className="text-sm text-muted-foreground">€1B research initiative (2018-2028)</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-cyan-600" />
                </a>
                <a
                  href="https://eurohpc-ju.europa.eu/selection-six-sites-host-first-european-quantum-computers_en"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:border-cyan-500/30 hover:bg-cyan-50/50 transition-all group"
                >
                  <div>
                    <p className="font-medium text-secondary group-hover:text-cyan-600 transition-colors">EuroHPC Quantum Computers</p>
                    <p className="text-sm text-muted-foreground">6 EU quantum computer sites</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-cyan-600" />
                </a>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12">
          <RelatedMonitorsSection currentMonitor="quantum" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="EU Quantum Monitor"
        />

        {/* Footer Attribution */}
        <footer className="text-center py-8 border-t border-border/50 mt-8">
          <p className="text-sm text-muted-foreground">
            Data sources: European Commission, JRC, EPRS, QuIC
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Market data from industry reports and public filings
          </p>
        </footer>
      </main>
    </div>
  );
}
