import { useState } from 'react';
import { Briefcase, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ScrollReveal } from '@/components/animations';
import { VCAngelOverview } from './VCAngelOverview';
import { VCLegislativeCards } from './VCLegislativeCards';
import { AngelTaxIncentivesMap } from './AngelTaxIncentivesMap';
import { ELTIFGrowthChart } from './ELTIFGrowthChart';

interface VCAngelSectionProps {
  className?: string;
  defaultExpanded?: boolean;
}

export function VCAngelSection({
  className = '',
  defaultExpanded = true,
}: VCAngelSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className={className}>
      {/* Section Header - Collapsible */}
      <motion.button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-primary/5 to-primary/10 rounded-lg border border-primary/20 hover:border-primary/40 transition-colors mb-4"
        whileHover={{ scale: 1.005 }}
        whileTap={{ scale: 0.995 }}
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <Briefcase className="w-5 h-5 text-primary" />
          </div>
          <div className="text-left">
            <h2 className="text-xl font-bold text-secondary">VC & Angel Ecosystem</h2>
            <p className="text-sm text-muted-foreground">
              EU policy framework for venture capital and business angel funding
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {isExpanded ? 'Click to collapse' : 'Click to expand'}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-5 h-5 text-muted-foreground" />
          )}
        </div>
      </motion.button>

      {/* Collapsible Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div className="space-y-6">
              {/* Row 1: Overview + ELTIF Growth */}
              <ScrollReveal variant="fadeUp" delay={0.1}>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <VCAngelOverview />
                  <ELTIFGrowthChart />
                </div>
              </ScrollReveal>

              {/* Row 2: Legislative Framework (full width) */}
              <ScrollReveal variant="fadeUp" delay={0.1}>
                <VCLegislativeCards />
              </ScrollReveal>

              {/* Row 3: Tax Incentives Map (full width) */}
              <ScrollReveal variant="fadeUp" delay={0.1}>
                <AngelTaxIncentivesMap />
              </ScrollReveal>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
