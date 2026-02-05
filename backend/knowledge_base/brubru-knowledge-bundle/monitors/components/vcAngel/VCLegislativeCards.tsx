import { useState } from 'react';
import { FileText, ExternalLink, ChevronDown, ChevronUp, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VC_LEGISLATION } from '@/data/vcAngelFallback';
import type { VCLegislation } from '@/types/vcAngel';

interface VCLegislativeCardsProps {
  legislation?: VCLegislation[];
  className?: string;
}

const statusConfig = {
  in_force: {
    icon: CheckCircle,
    bg: 'bg-green-100',
    border: 'border-green-200',
    badge: 'bg-green-500 text-white',
    iconColour: 'text-green-600',
  },
  under_review: {
    icon: Clock,
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    badge: 'bg-amber-500 text-white',
    iconColour: 'text-amber-600',
  },
  transposition: {
    icon: AlertCircle,
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    badge: 'bg-blue-500 text-white',
    iconColour: 'text-blue-600',
  },
  proposed: {
    icon: FileText,
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    badge: 'bg-purple-500 text-white',
    iconColour: 'text-purple-600',
  },
};

export function VCLegislativeCards({
  legislation = VC_LEGISLATION,
  className = '',
}: VCLegislativeCardsProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-secondary" />
          <CardTitle className="text-xl text-secondary">VC Legislative Framework</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Core regulations shaping the EU venture capital ecosystem
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {legislation.map((leg, index) => {
            const config = statusConfig[leg.status];
            const StatusIcon = config.icon;
            const isExpanded = expandedId === leg.id;

            return (
              <motion.div
                key={leg.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}
              >
                <button
                  onClick={() => toggleExpand(leg.id)}
                  className="w-full p-4 text-left flex items-center justify-between hover:bg-white/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <StatusIcon className={`w-5 h-5 ${config.iconColour}`} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-secondary">{leg.shortName}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${config.badge}`}>
                          {leg.statusLabel}
                        </span>
                        {leg.deadline && (
                          <span className="text-xs text-muted-foreground">
                            Deadline: {leg.deadline}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{leg.name}</p>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-muted-foreground" />
                  )}
                </button>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 pt-0">
                        <div className="border-t border-current/10 pt-3">
                          <p className="text-sm text-muted-foreground mb-3">{leg.description}</p>

                          <div className="mb-3">
                            <span className="text-xs font-medium text-secondary">Key Provisions:</span>
                            <ul className="mt-1 space-y-1">
                              {leg.keyProvisions.map((provision, i) => (
                                <li key={i} className="text-xs text-muted-foreground flex items-start gap-2">
                                  <span className="text-primary mt-1">•</span>
                                  {provision}
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">{leg.legalBasis}</span>
                            {leg.eurLexUrl && (
                              <a
                                href={leg.eurLexUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline flex items-center gap-1"
                              >
                                EUR-Lex <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
