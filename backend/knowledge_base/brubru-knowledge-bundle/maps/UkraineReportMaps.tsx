import { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Euro, FileWarning, Vote, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EuropeMap, CountryData } from './EuropeMap';

// ============================================
// MAP 1: EU Population Weight with Ukraine
// ============================================

const POPULATION_DATA: CountryData[] = [
  { code: 'DE', value: 84.4, label: '84.4M (17.8%)' },
  { code: 'FR', value: 68.2, label: '68.2M (14.4%)' },
  { code: 'IT', value: 58.9, label: '58.9M (12.4%)' },
  { code: 'ES', value: 48.1, label: '48.1M (10.1%)' },
  { code: 'UA', value: 37.5, label: '37.5M (7.9%)' }, // Ukraine - 5th largest
  { code: 'PL', value: 36.8, label: '36.8M (7.8%)' },
  { code: 'RO', value: 19.0, label: '19.0M (4.0%)' },
  { code: 'NL', value: 17.8, label: '17.8M (3.8%)' },
  { code: 'BE', value: 11.7, label: '11.7M (2.5%)' },
  { code: 'CZ', value: 10.5, label: '10.5M (2.2%)' },
  { code: 'GR', value: 10.4, label: '10.4M (2.2%)' },
  { code: 'PT', value: 10.4, label: '10.4M (2.2%)' },
  { code: 'SE', value: 10.5, label: '10.5M (2.2%)' },
  { code: 'HU', value: 9.7, label: '9.7M (2.0%)' },
  { code: 'AT', value: 9.1, label: '9.1M (1.9%)' },
  { code: 'BG', value: 6.5, label: '6.5M (1.4%)' },
  { code: 'DK', value: 5.9, label: '5.9M (1.2%)' },
  { code: 'FI', value: 5.5, label: '5.5M (1.2%)' },
  { code: 'SK', value: 5.4, label: '5.4M (1.1%)' },
  { code: 'IE', value: 5.1, label: '5.1M (1.1%)' },
  { code: 'HR', value: 3.9, label: '3.9M (0.8%)' },
  { code: 'LT', value: 2.9, label: '2.9M (0.6%)' },
  { code: 'SI', value: 2.1, label: '2.1M (0.4%)' },
  { code: 'LV', value: 1.9, label: '1.9M (0.4%)' },
  { code: 'EE', value: 1.4, label: '1.4M (0.3%)' },
  { code: 'CY', value: 0.9, label: '0.9M (0.2%)' },
  { code: 'LU', value: 0.7, label: '0.7M (0.1%)' },
  { code: 'MT', value: 0.5, label: '0.5M (0.1%)' },
];


export function PopulationWeightMap({ className = '' }: { className?: string }) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <Users className="w-5 h-5 text-primary" />
          </motion.div>
          <CardTitle className="text-lg text-secondary">
            EU Population Distribution
          </CardTitle>
          <Badge className="bg-amber-500/10 text-amber-700 border-amber-500/20">
            Ukraine: 5th Largest
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Ukraine's 37.5M population would make it the EU's 5th most populous member state
        </p>
      </CardHeader>
      <CardContent>
        <EuropeMap
          data={POPULATION_DATA}
          colorScale={{ min: '#e8f5e9', max: '#1b5e20' }}
          legendTitle="Population (millions)"
          valueFormatter={(v) => `${v.toFixed(1)}M`}
          height="350px"
          showUkraine
          ukraineColor="#fbbf24"
        />

        {/* Map legend for occupied territories */}
        <div className="flex justify-center gap-4 mt-4 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-amber-400 border-2 border-dashed border-amber-700" />
            <span className="text-sm text-muted-foreground">Ukraine (Candidate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-gray-500 border-2 border-red-600" />
            <span className="text-sm text-muted-foreground">Russian-occupied</span>
          </div>
        </div>

        {/* Ukraine annotation overlay */}
        <motion.div
          className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-lg font-bold text-amber-700">Ukraine: 37.5 million</div>
              <p className="text-sm text-amber-600">Would rank between Spain (48.1M) and Poland (36.8M)</p>
              <p className="text-xs text-amber-500 mt-1 italic">
                *Population estimate excludes Russian-occupied territories (Crimea, parts of Donetsk, Luhansk, Zaporizhzhia, Kherson)
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-amber-700">7.9%</div>
              <p className="text-xs text-amber-600">of EU-28 population</p>
            </div>
          </div>
        </motion.div>

        {/* Key insight cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
          <motion.div
            className="bg-muted/30 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <div className="text-lg font-bold text-primary">52-59</div>
            <p className="text-xs text-muted-foreground">Projected MEPs for Ukraine</p>
          </motion.div>
          <motion.div
            className="bg-muted/30 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <div className="text-lg font-bold text-destructive">751 cap</div>
            <p className="text-xs text-muted-foreground">Would be breached (770-775)</p>
          </motion.div>
          <motion.div
            className="bg-muted/30 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <div className="text-lg font-bold text-secondary">QMV shift</div>
            <p className="text-xs text-muted-foreground">Blocking coalitions easier</p>
          </motion.div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================
// MAP 2: Net Budget Transfers
// ============================================

const BUDGET_TRANSFER_DATA: CountryData[] = [
  // Net contributors (negative = pays more than receives)
  { code: 'DE', value: -15.5, label: '-€15.5B/year' },
  { code: 'FR', value: -8.2, label: '-€8.2B/year' },
  { code: 'NL', value: -5.8, label: '-€5.8B/year' },
  { code: 'SE', value: -2.1, label: '-€2.1B/year' },
  { code: 'AT', value: -1.8, label: '-€1.8B/year' },
  { code: 'DK', value: -1.5, label: '-€1.5B/year' },
  { code: 'FI', value: -0.8, label: '-€0.8B/year' },
  { code: 'IE', value: -0.6, label: '-€0.6B/year' },
  { code: 'BE', value: -0.4, label: '-€0.4B/year' },
  { code: 'IT', value: -0.3, label: '-€0.3B/year' },
  { code: 'LU', value: -0.2, label: '-€0.2B/year' },
  // Net recipients (positive = receives more than pays)
  { code: 'UA', value: 18.5, label: '+€18.5B/year' }, // Ukraine - largest projected recipient
  { code: 'PL', value: 12.1, label: '+€12.1B/year' },
  { code: 'RO', value: 5.2, label: '+€5.2B/year' },
  { code: 'HU', value: 4.8, label: '+€4.8B/year' },
  { code: 'GR', value: 4.2, label: '+€4.2B/year' },
  { code: 'CZ', value: 3.8, label: '+€3.8B/year' },
  { code: 'PT', value: 3.1, label: '+€3.1B/year' },
  { code: 'ES', value: 2.8, label: '+€2.8B/year' },
  { code: 'BG', value: 2.1, label: '+€2.1B/year' },
  { code: 'SK', value: 1.8, label: '+€1.8B/year' },
  { code: 'HR', value: 1.5, label: '+€1.5B/year' },
  { code: 'LT', value: 1.4, label: '+€1.4B/year' },
  { code: 'LV', value: 0.9, label: '+€0.9B/year' },
  { code: 'EE', value: 0.7, label: '+€0.7B/year' },
  { code: 'SI', value: 0.6, label: '+€0.6B/year' },
  { code: 'CY', value: 0.3, label: '+€0.3B/year' },
  { code: 'MT', value: 0.2, label: '+€0.2B/year' },
];

export function BudgetTransfersMap({ className = '' }: { className?: string }) {
  // Normalize data for color scale (shift to positive range)
  const normalizedData = BUDGET_TRANSFER_DATA.map(d => ({
    ...d,
    value: d.value + 20, // Shift so all positive for color mapping
  }));

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <Euro className="w-5 h-5 text-primary" />
          </motion.div>
          <CardTitle className="text-lg text-secondary">
            EU Net Budget Transfers
          </CardTitle>
          <Badge className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20">
            Ukraine: €18-19B/year
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Projected annual net transfers - Ukraine would become the largest recipient in EU history
        </p>
      </CardHeader>
      <CardContent>
        <EuropeMap
          data={normalizedData}
          colorScale={{ min: '#ef4444', max: '#22c55e' }}
          legendTitle="Net transfer"
          valueFormatter={(v) => {
            const actual = v - 20;
            return actual >= 0 ? `+€${actual.toFixed(1)}B` : `-€${Math.abs(actual).toFixed(1)}B`;
          }}
          height="350px"
          showUkraine
          ukraineColor="#22c55e"
        />

        {/* Map legend for occupied territories */}
        <div className="flex justify-center gap-4 mt-4 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-emerald-500 border-2 border-dashed border-amber-700" />
            <span className="text-sm text-muted-foreground">Ukraine (Candidate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-gray-500 border-2 border-red-600" />
            <span className="text-sm text-muted-foreground">Russian-occupied</span>
          </div>
        </div>

        {/* Ukraine projection highlight */}
        <motion.div
          className="mt-4 bg-emerald-50 border border-emerald-200 rounded-lg p-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-lg font-bold text-emerald-700">Ukraine: +€18-19 billion/year</div>
              <p className="text-sm text-emerald-600">€136B (full territory) or €110B (20% territory loss) over 7-year MFF</p>
              <p className="text-xs text-emerald-500 mt-1 italic">
                *Bruegel projections based on territorial integrity scenarios
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-emerald-700">0.13%</div>
              <p className="text-xs text-emerald-600">of EU GDP</p>
            </div>
          </div>
        </motion.div>

        {/* Budget breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
          <motion.div
            className="bg-emerald-50 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <div className="text-lg font-bold text-emerald-700">€85B</div>
            <p className="text-xs text-emerald-600">CAP (62%)</p>
          </motion.div>
          <motion.div
            className="bg-blue-50 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <div className="text-lg font-bold text-blue-700">€32B</div>
            <p className="text-xs text-blue-600">Cohesion (24%)</p>
          </motion.div>
          <motion.div
            className="bg-violet-50 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <div className="text-lg font-bold text-violet-700">€7B</div>
            <p className="text-xs text-violet-600">Other (5%)</p>
          </motion.div>
          <motion.div
            className="bg-red-50 rounded-lg p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 }}
          >
            <div className="text-lg font-bold text-red-700">-€14B</div>
            <p className="text-xs text-red-600">Contributions</p>
          </motion.div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================
// MAP 3: Treaty Change Opposition
// ============================================

// Countries opposing treaty changes (13 member states)
const TREATY_OPPOSITION = ['BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 'LV', 'LT', 'MT', 'PL', 'RO', 'SI', 'SE'];
// Countries leading reform (France-Germany + allies)
const TREATY_REFORM_LEADERS = ['FR', 'DE', 'BE', 'ES', 'IT', 'LU'];
// Neutral/undecided
const TREATY_NEUTRAL = ['AT', 'CY', 'GR', 'HU', 'IE', 'NL', 'PT', 'SK'];

const TREATY_POSITION_DATA: CountryData[] = [
  // Opposition (value = 0)
  ...TREATY_OPPOSITION.map(code => ({ code, value: 0, label: 'Opposes treaty change' })),
  // Reform leaders (value = 2)
  ...TREATY_REFORM_LEADERS.map(code => ({ code, value: 2, label: 'Supports reform' })),
  // Neutral (value = 1)
  ...TREATY_NEUTRAL.map(code => ({ code, value: 1, label: 'Neutral/undecided' })),
];

export function TreatyOppositionMap({ className = '' }: { className?: string }) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <Vote className="w-5 h-5 text-primary" />
          </motion.div>
          <CardTitle className="text-lg text-secondary">
            Treaty Change Positions
          </CardTitle>
          <Badge className="bg-red-500/10 text-red-700 border-red-500/20">
            13 States Oppose
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Member state positions on institutional reform required for enlargement
        </p>
      </CardHeader>
      <CardContent>
        <EuropeMap
          data={TREATY_POSITION_DATA}
          colorScale={{ min: '#ef4444', max: '#22c55e' }}
          legendTitle="Position"
          valueFormatter={(v) => {
            if (v === 0) return 'Opposes';
            if (v === 1) return 'Neutral';
            return 'Supports';
          }}
          height="350px"
          showUkraine
          ukraineColor="#fbbf24"
        />

        {/* Legend */}
        <div className="flex justify-center gap-4 mt-4 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-500" />
            <span className="text-sm text-muted-foreground">Opposes (13)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-yellow-500" />
            <span className="text-sm text-muted-foreground">Neutral (8)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-green-500" />
            <span className="text-sm text-muted-foreground">Supports (6)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-amber-400 border-2 border-dashed border-amber-700" />
            <span className="text-sm text-muted-foreground">Ukraine (Candidate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-gray-500 border-2 border-red-600" />
            <span className="text-sm text-muted-foreground">Russian-occupied</span>
          </div>
        </div>

        {/* Key issues */}
        <motion.div
          className="mt-4 bg-muted/30 rounded-lg p-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <h4 className="font-medium text-secondary mb-3">Key Reform Issues</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="flex items-center gap-2 text-green-700 mb-1">
                <TrendingUp className="w-4 h-4" />
                <span className="font-medium">Reform advocates want:</span>
              </div>
              <ul className="text-muted-foreground ml-6 space-y-1">
                <li>Expand QMV to foreign policy</li>
                <li>Raise EP seat cap above 751</li>
                <li>Streamline Commission structure</li>
              </ul>
            </div>
            <div>
              <div className="flex items-center gap-2 text-red-700 mb-1">
                <TrendingDown className="w-4 h-4" />
                <span className="font-medium">Opposition concerns:</span>
              </div>
              <ul className="text-muted-foreground ml-6 space-y-1">
                <li>Small states fear losing vetoes</li>
                <li>Sovereignty protection demands</li>
                <li>"Unconsidered and premature"</li>
              </ul>
            </div>
          </div>
        </motion.div>

        {/* Countries list */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
          <motion.div
            className="bg-red-50 border border-red-200 rounded-lg p-3"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
          >
            <div className="text-sm font-medium text-red-700 mb-2">Opposition bloc (13)</div>
            <p className="text-xs text-red-600">
              Bulgaria, Croatia, Czechia, Denmark, Estonia, Finland, Latvia, Lithuania, Malta, Poland, Romania, Slovenia, Sweden
            </p>
          </motion.div>
          <motion.div
            className="bg-green-50 border border-green-200 rounded-lg p-3"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <div className="text-sm font-medium text-green-700 mb-2">Reform leaders (6)</div>
            <p className="text-xs text-green-600">
              France, Germany, Belgium, Spain, Italy, Luxembourg
            </p>
          </motion.div>
          <motion.div
            className="bg-yellow-50 border border-yellow-200 rounded-lg p-3"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.8 }}
          >
            <div className="text-sm font-medium text-yellow-700 mb-2">Neutral/undecided (8)</div>
            <p className="text-xs text-yellow-600">
              Austria, Cyprus, Greece, Hungary, Ireland, Netherlands, Portugal, Slovakia
            </p>
          </motion.div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================
// Combined Ukraine Maps Section
// ============================================

export function UkraineReportMapsSection({ className = '' }: { className?: string }) {
  const [activeMap, setActiveMap] = useState<'population' | 'budget' | 'treaty'>('population');

  return (
    <div className={`space-y-6 ${className}`}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h2 className="text-2xl font-bold text-secondary mb-2">Interactive Analysis Maps</h2>
        <p className="text-muted-foreground">Explore the data behind Ukraine's EU membership implications</p>
      </motion.div>

      {/* Map selector */}
      <div className="flex justify-center gap-2 flex-wrap">
        <button
          onClick={() => setActiveMap('population')}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            activeMap === 'population'
              ? 'bg-primary text-white'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          <Users className="w-4 h-4 inline mr-2" />
          Population Weight
        </button>
        <button
          onClick={() => setActiveMap('budget')}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            activeMap === 'budget'
              ? 'bg-primary text-white'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          <Euro className="w-4 h-4 inline mr-2" />
          Budget Transfers
        </button>
        <button
          onClick={() => setActiveMap('treaty')}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            activeMap === 'treaty'
              ? 'bg-primary text-white'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          <Vote className="w-4 h-4 inline mr-2" />
          Treaty Positions
        </button>
      </div>

      {/* Active map */}
      <motion.div
        key={activeMap}
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
      >
        {activeMap === 'population' && <PopulationWeightMap />}
        {activeMap === 'budget' && <BudgetTransfersMap />}
        {activeMap === 'treaty' && <TreatyOppositionMap />}
      </motion.div>
    </div>
  );
}
