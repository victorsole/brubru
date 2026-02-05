import { Building2, ExternalLink, CheckCircle2, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface RegimeSpotlightProps {
  className?: string;
}

const BENEFITS = [
  'One company form, 27 markets',
  'Employee stock options with deferred tax',
  'Simplified cross-border operations',
  'Harmonised insolvency rules',
];

const TIMELINE = [
  { label: 'VdL announcement', date: 'Jan 2026', completed: true },
  { label: 'Legislative proposal', date: 'Mar 2026', completed: false },
  { label: 'EP first reading', date: 'Q3 2026', completed: false },
  { label: 'Entry into force', date: '2027', completed: false },
];

export function RegimeSpotlight({ className = '' }: RegimeSpotlightProps) {
  return (
    <Card className={`border-border/50 bg-gradient-to-br from-blue-50 to-white ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-600" />
            <CardTitle className="text-xl text-secondary">28th Regime / EU-Inc</CardTitle>
          </div>
          <span className="text-xs px-2 py-1 rounded-full bg-primary/20 text-primary font-medium flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            Announced Davos 2026
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {/* Davos Announcement Highlight */}
        <div className="mb-4 p-3 bg-primary/10 rounded-lg border border-primary/20">
          <p className="text-sm text-secondary font-medium">
            On 20 January 2026, Commission President Ursula von der Leyen announced at the
            World Economic Forum in Davos that the EU will create EU Inc: a truly European
            company structure. Legislative proposal expected March 2026.
          </p>
        </div>

        <p className="text-sm text-muted-foreground mb-4">
          A pan-European company form designed to let startups scale across the single market
          without navigating 27 different legal systems.
        </p>

        {/* Benefits */}
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider mb-2">
            Key Benefits
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {BENEFITS.map((benefit) => (
              <div key={benefit} className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <span className="text-sm text-muted-foreground">{benefit}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider mb-2">
            Expected Timeline
          </h4>
          <div className="flex items-center gap-1">
            {TIMELINE.map((step, idx) => (
              <div key={step.label} className="flex-1">
                <div className="flex items-center">
                  <div className={`w-3 h-3 rounded-full border-2 ${
                    step.completed
                      ? 'bg-primary border-primary'
                      : 'bg-white border-blue-300'
                  }`}>
                    {step.completed && (
                      <CheckCircle2 className="w-full h-full text-white" />
                    )}
                  </div>
                  {idx < TIMELINE.length - 1 && (
                    <div className={`flex-1 h-0.5 ${
                      step.completed ? 'bg-primary' : 'bg-blue-200'
                    }`} />
                  )}
                </div>
                <div className="mt-1">
                  <div className="text-[10px] text-muted-foreground">{step.label}</div>
                  <div className="text-xs font-medium text-secondary">{step.date}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Links */}
        <div className="flex flex-wrap gap-3 pt-3 border-t border-border/50">
          <a
            href="https://www.eu-inc.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            EU-INC.org <ExternalLink className="w-3 h-3" />
          </a>
          <a
            href="https://proposal.eu-inc.org/?v=14d076fd79c58146b048000caeed686a"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Draft proposal <ExternalLink className="w-3 h-3" />
          </a>
          <a
            href="https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/jobs-and-economy/eu-startup-and-scaleup-strategy_en"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            EC Strategy <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Impact quote */}
        <div className="mt-4 p-3 bg-blue-100/50 rounded-lg border border-blue-200/50">
          <p className="text-xs text-blue-800 italic">
            "We will create a new truly European company structure. We call it EU Inc."
            — Ursula von der Leyen, Davos 2026
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
