import {
  Shield,
  TrendingUp,
  Globe,
  Bot,
  Atom,
  Rocket,
  Coins,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type MonitorId = 'defence' | 'cmu' | 'tariffs' | 'ai' | 'quantum' | 'startups' | 'gold';

export interface MonitorInfo {
  id: MonitorId;
  name: string;
  shortName: string;
  path: string;
  icon: LucideIcon;
  colour: string;
  colourClasses: {
    bg: string;
    text: string;
    border: string;
  };
}

export interface MonitorRelationship {
  targetMonitor: MonitorId;
  reason: string;
  strength: 'high' | 'medium' | 'low';
}

// Monitor definitions
export const MONITORS: Record<MonitorId, MonitorInfo> = {
  defence: {
    id: 'defence',
    name: 'EU Defence Monitor',
    shortName: 'Defence',
    path: '/defence',
    icon: Shield,
    colour: 'red',
    colourClasses: {
      bg: 'bg-red-500/10',
      text: 'text-red-500',
      border: 'border-red-500/20',
    },
  },
  cmu: {
    id: 'cmu',
    name: 'Capital Markets Union Monitor',
    shortName: 'CMU',
    path: '/cmu',
    icon: TrendingUp,
    colour: 'primary',
    colourClasses: {
      bg: 'bg-primary/10',
      text: 'text-primary',
      border: 'border-primary/20',
    },
  },
  tariffs: {
    id: 'tariffs',
    name: 'Tariff & Trade War Monitor',
    shortName: 'Tariffs',
    path: '/tariffs',
    icon: Globe,
    colour: 'amber',
    colourClasses: {
      bg: 'bg-amber-500/10',
      text: 'text-amber-600',
      border: 'border-amber-500/20',
    },
  },
  ai: {
    id: 'ai',
    name: 'AI Market Monitor',
    shortName: 'AI',
    path: '/ai-monitor',
    icon: Bot,
    colour: 'purple',
    colourClasses: {
      bg: 'bg-purple-500/10',
      text: 'text-purple-500',
      border: 'border-purple-500/20',
    },
  },
  quantum: {
    id: 'quantum',
    name: 'EU Quantum Monitor',
    shortName: 'Quantum',
    path: '/quantum',
    icon: Atom,
    colour: 'cyan',
    colourClasses: {
      bg: 'bg-cyan-500/10',
      text: 'text-cyan-500',
      border: 'border-cyan-500/20',
    },
  },
  startups: {
    id: 'startups',
    name: 'EU Startup Monitor',
    shortName: 'Startups',
    path: '/startups',
    icon: Rocket,
    colour: 'emerald',
    colourClasses: {
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-500',
      border: 'border-emerald-500/20',
    },
  },
  gold: {
    id: 'gold',
    name: 'Gold Trading Monitor',
    shortName: 'Gold',
    path: '/gold',
    icon: Coins,
    colour: 'yellow',
    colourClasses: {
      bg: 'bg-yellow-500/10',
      text: 'text-yellow-600',
      border: 'border-yellow-500/20',
    },
  },
};

// Define relationships for each monitor
// Primary = shown in top banner, Related = shown in bottom section
export const MONITOR_RELATIONSHIPS: Record<MonitorId, {
  primary?: { target: MonitorId; reason: string };
  related: MonitorRelationship[];
}> = {
  defence: {
    primary: {
      target: 'tariffs',
      reason: 'Defence procurement affected by trade barriers and dual-use goods restrictions',
    },
    related: [
      { targetMonitor: 'tariffs', reason: 'Strategic autonomy and trade policy', strength: 'high' },
      { targetMonitor: 'ai', reason: 'Defence AI and autonomous systems', strength: 'medium' },
      { targetMonitor: 'quantum', reason: 'Quantum computing for defence applications', strength: 'low' },
    ],
  },
  cmu: {
    primary: {
      target: 'startups',
      reason: 'Startup financing is a key pillar of the CMU/SIU agenda',
    },
    related: [
      { targetMonitor: 'startups', reason: 'VC funding and capital access', strength: 'high' },
      { targetMonitor: 'gold', reason: 'Tokenised assets under MiCA regulation', strength: 'high' },
      { targetMonitor: 'ai', reason: 'AI investment and fintech innovation', strength: 'medium' },
    ],
  },
  tariffs: {
    primary: {
      target: 'defence',
      reason: 'Trade tensions impact defence supply chains and strategic autonomy',
    },
    related: [
      { targetMonitor: 'defence', reason: 'Steel/aluminium tariffs affect defence', strength: 'high' },
      { targetMonitor: 'ai', reason: 'Chip export controls and AI supply chains', strength: 'high' },
      { targetMonitor: 'gold', reason: 'Commodity prices during trade tensions', strength: 'medium' },
    ],
  },
  ai: {
    primary: {
      target: 'quantum',
      reason: 'Both are central to EU technological sovereignty strategy',
    },
    related: [
      { targetMonitor: 'quantum', reason: 'Quantum AI and post-quantum security', strength: 'high' },
      { targetMonitor: 'startups', reason: 'AI startups and VC investment', strength: 'high' },
      { targetMonitor: 'tariffs', reason: 'Chip supply chains and export controls', strength: 'medium' },
    ],
  },
  quantum: {
    primary: {
      target: 'ai',
      reason: 'Quantum computing accelerates AI capabilities and requires new security standards',
    },
    related: [
      { targetMonitor: 'ai', reason: 'Quantum AI applications', strength: 'high' },
      { targetMonitor: 'defence', reason: 'Quantum for defence and PQC', strength: 'medium' },
      { targetMonitor: 'cmu', reason: 'Quantum-safe financial infrastructure', strength: 'low' },
    ],
  },
  startups: {
    primary: {
      target: 'cmu',
      reason: 'Capital Markets Union is critical for startup funding access',
    },
    related: [
      { targetMonitor: 'cmu', reason: 'VC/Angel ecosystem and SIU', strength: 'high' },
      { targetMonitor: 'ai', reason: 'AI startups lead European tech', strength: 'high' },
      { targetMonitor: 'quantum', reason: 'Deep tech and quantum startups', strength: 'medium' },
    ],
  },
  gold: {
    primary: {
      target: 'cmu',
      reason: 'Tokenised gold (PAXG, XAUT) regulated under MiCA within CMU framework',
    },
    related: [
      { targetMonitor: 'cmu', reason: 'MiCA and financial market integration', strength: 'high' },
      { targetMonitor: 'tariffs', reason: 'Safe-haven asset during trade tensions', strength: 'medium' },
      { targetMonitor: 'defence', reason: 'Central bank reserves and sovereignty', strength: 'low' },
    ],
  },
};

// Helper functions
export function getMonitorInfo(id: MonitorId): MonitorInfo {
  return MONITORS[id];
}

export function getPrimaryRelationship(monitorId: MonitorId) {
  const relationship = MONITOR_RELATIONSHIPS[monitorId].primary;
  if (!relationship) return null;
  return {
    monitor: MONITORS[relationship.target],
    reason: relationship.reason,
  };
}

export function getRelatedMonitors(monitorId: MonitorId, limit = 3) {
  return MONITOR_RELATIONSHIPS[monitorId].related
    .slice(0, limit)
    .map(rel => ({
      monitor: MONITORS[rel.targetMonitor],
      reason: rel.reason,
      strength: rel.strength,
    }));
}
