import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Train, AlertTriangle, Euro, TrendingDown, MapPin, ChevronRight } from 'lucide-react';
import { motion, useInView } from 'framer-motion';

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.1,
    },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring',
      stiffness: 100,
      damping: 15,
    },
  },
};

const slideInLeft = {
  hidden: { opacity: 0, x: -50 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: 'spring',
      stiffness: 80,
      damping: 20,
    },
  },
};

const slideInRight = {
  hidden: { opacity: 0, x: 50 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: 'spring',
      stiffness: 80,
      damping: 20,
    },
  },
};

const fadeInUp = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
    },
  },
};

// Animated counter hook
function useAnimatedCounter(end: number, duration: number = 2000, startOnView: boolean = true) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!startOnView || !isInView || hasAnimated.current) return;
    hasAnimated.current = true;

    let startTime: number;
    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const progress = Math.min((currentTime - startTime) / duration, 1);
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      setCount(Math.floor(easeOutQuart * end));
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };
    requestAnimationFrame(animate);
  }, [end, duration, isInView, startOnView]);

  return { count, ref };
}

// Railway incidents data
const incidentsData = [
  {
    id: 1,
    date: '20/11/2018',
    location: 'Vacarisses',
    line: 'R4',
    incident: 'Esllavissada talús sota C-58',
    casualties: '1 mort, 49 ferits',
    coordinates: [1.8847, 41.5514],
    severity: 'fatal'
  },
  {
    id: 2,
    date: '08/02/2019',
    location: 'Castellgalí',
    line: 'R4',
    incident: 'Xoc frontal (error senyalització)',
    casualties: '1 mort, 100+ ferits',
    coordinates: [1.8547, 41.6764],
    severity: 'fatal'
  },
  {
    id: 3,
    date: '03/03/2024',
    location: 'Vacarisses',
    line: 'R4',
    incident: 'Esllavissada (3 km del 2018)',
    casualties: 'Sense ferits',
    coordinates: [1.8917, 41.5484],
    severity: 'minor'
  },
  {
    id: 4,
    date: '20/01/2026',
    location: 'Gelida',
    line: 'R4',
    incident: 'Despreniment mur AP-7',
    casualties: '1 mort, 37 ferits',
    coordinates: [1.8647, 41.4364],
    severity: 'fatal'
  },
  {
    id: 5,
    date: '20/01/2026',
    location: 'Tordera-Maçanet',
    line: 'R1',
    incident: 'Roca a la via',
    casualties: 'Sense ferits',
    coordinates: [2.7147, 41.6964],
    severity: 'minor'
  },
  {
    id: 6,
    date: '23/01/2026',
    location: 'Tordera',
    line: 'R1',
    incident: 'Esllavissada (dia represa)',
    casualties: 'Sense ferits',
    coordinates: [2.7247, 41.6864],
    severity: 'minor'
  }
];

// Budget execution data
const budgetExecutionData = [
  { name: 'Pressupostat', value: 6194, fill: '#3b82f6' },
  { name: 'Executat', value: 2171, fill: '#ef4444' }
];

// Regional comparison data
const regionalComparisonData = [
  { region: 'Madrid', execution: 45.8, fill: '#22c55e' },
  { region: 'Mitjana estatal', execution: 41.0, fill: '#f59e0b' },
  { region: 'Catalunya', execution: 35.1, fill: '#ef4444' }
];

// Resource distribution data (1990-2018)
const resourceDistributionData = [
  { name: 'Madrid', value: 47, fill: '#3b82f6' },
  { name: 'Catalunya', value: 17, fill: '#ef4444' },
  { name: 'Altres', value: 36, fill: '#94a3b8' }
];

// Interactive Map Component
export function RodaliesIncidentsMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sectionRef, { once: true, margin: '-100px' });
  const [selectedIncident, setSelectedIncident] = useState<typeof incidentsData[0] | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [2.1, 41.6],
      zoom: 8
    });

    map.current.on('load', () => {
      // Add CSS animation styles once
      if (!document.getElementById('marker-animation-style')) {
        const style = document.createElement('style');
        style.id = 'marker-animation-style';
        style.textContent = `
          @keyframes markerFadeIn {
            0% { opacity: 0; }
            100% { opacity: 1; }
          }
          @keyframes markerPulse {
            0%, 100% { box-shadow: 0 2px 8px rgba(0,0,0,0.3), 0 0 0 0 rgba(220, 38, 38, 0.4); }
            50% { box-shadow: 0 2px 8px rgba(0,0,0,0.3), 0 0 0 8px rgba(220, 38, 38, 0); }
          }
          .incident-marker-fatal {
            animation: markerPulse 2s infinite;
          }
        `;
        document.head.appendChild(style);
      }

      incidentsData.forEach((incident, index) => {
        const el = document.createElement('div');
        el.className = `incident-marker ${incident.severity === 'fatal' ? 'incident-marker-fatal' : ''}`;

        const size = incident.severity === 'fatal' ? 24 : 16;
        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.backgroundColor = incident.severity === 'fatal' ? '#dc2626' : '#f59e0b';
        el.style.border = '2px solid white';
        el.style.borderRadius = '50%';
        el.style.cursor = 'pointer';
        el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
        el.style.opacity = '0';
        el.style.animation = `markerFadeIn 0.4s ease-out ${index * 0.15}s forwards`;

        el.addEventListener('click', () => setSelectedIncident(incident));

        const popup = new maplibregl.Popup({ offset: 25 }).setHTML(`
          <div style="padding: 8px; max-width: 250px;">
            <div style="font-weight: bold; margin-bottom: 4px; color: #1e293b;">${incident.location} (${incident.line})</div>
            <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">${incident.date}</div>
            <div style="font-size: 13px; margin-bottom: 4px;">${incident.incident}</div>
            <div style="font-size: 12px; color: ${incident.severity === 'fatal' ? '#dc2626' : '#f59e0b'}; font-weight: 500;">
              ${incident.casualties}
            </div>
          </div>
        `);

        new maplibregl.Marker({ element: el })
          .setLngLat(incident.coordinates as [number, number])
          .setPopup(popup)
          .addTo(map.current!);
      });
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  return (
    <motion.div
      ref={sectionRef}
      initial="hidden"
      animate={isInView ? 'visible' : 'hidden'}
      variants={fadeInUp}
    >
      <Card className="overflow-hidden border-violet-200 shadow-lg">
        <CardHeader className="pb-2 bg-gradient-to-r from-violet-50 to-transparent">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <motion.div variants={slideInLeft}>
              <CardTitle className="text-lg flex items-center gap-2">
                <motion.div
                  animate={{ rotate: [0, -10, 10, -10, 0] }}
                  transition={{ duration: 0.5, delay: 0.5 }}
                >
                  <Train className="w-5 h-5 text-violet-600" />
                </motion.div>
                Mapa d'incidents ferroviaris (2018-2026)
              </CardTitle>
            </motion.div>
            <motion.div variants={slideInRight} className="flex gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <motion.span
                  className="w-3 h-3 rounded-full bg-red-600"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="font-medium">Accident mortal</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="font-medium">Incident menor</span>
              </div>
            </motion.div>
          </div>
        </CardHeader>
        <CardContent className="p-0 relative">
          <div ref={mapContainer} className="w-full h-[400px]" />

          {/* Incident Navigator */}
          <motion.div
            className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-72"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1 }}
          >
            <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
              <CardContent className="p-3">
                <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> Navegació ràpida
                </p>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {incidentsData.map((incident, idx) => (
                    <motion.button
                      key={incident.id}
                      className={`w-full text-left text-xs p-1.5 rounded flex items-center gap-2 transition-colors ${
                        selectedIncident?.id === incident.id
                          ? 'bg-violet-100 text-violet-800'
                          : 'hover:bg-slate-100'
                      }`}
                      onClick={() => {
                        setSelectedIncident(incident);
                        map.current?.flyTo({
                          center: incident.coordinates as [number, number],
                          zoom: 12,
                          duration: 1500,
                        });
                      }}
                      whileHover={{ x: 3 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <span className={`w-2 h-2 rounded-full ${incident.severity === 'fatal' ? 'bg-red-500' : 'bg-amber-500'}`} />
                      <span className="flex-1 truncate">{incident.location}</span>
                      <ChevronRight className="w-3 h-3 text-muted-foreground" />
                    </motion.button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// Animated Stat Card Component
function AnimatedStatCard({
  icon: Icon,
  label,
  value,
  suffix,
  colorClass,
  delay = 0,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  suffix: string;
  colorClass: { bg: string; border: string; iconBg: string; text: string; valueText: string };
  delay?: number;
}) {
  const { count, ref } = useAnimatedCounter(value, 2000);
  const cardRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(cardRef, { once: true, margin: '-50px' });

  return (
    <motion.div
      ref={cardRef}
      variants={cardVariants}
      initial="hidden"
      animate={isInView ? 'visible' : 'hidden'}
      transition={{ delay }}
      whileHover={{ scale: 1.02, y: -4 }}
    >
      <Card className={`${colorClass.bg} ${colorClass.border} shadow-md hover:shadow-lg transition-shadow`}>
        <CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <motion.div
              className={`p-2 ${colorClass.iconBg} rounded-lg`}
              whileHover={{ rotate: [0, -10, 10, 0] }}
              transition={{ duration: 0.4 }}
            >
              <Icon className={`w-5 h-5 ${colorClass.text}`} />
            </motion.div>
            <div>
              <p className={`text-sm ${colorClass.text}`}>{label}</p>
              <p className={`text-2xl font-bold ${colorClass.valueText}`}>
                <span ref={ref}>{count.toLocaleString('ca-ES')}</span>{suffix}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// Investment Gap Charts Component
export function InvestmentGapCharts() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<HTMLDivElement>(null);
  const pieRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sectionRef, { once: true, margin: '-50px' });
  const chartsInView = useInView(chartsRef, { once: true, margin: '-50px' });
  const pieInView = useInView(pieRef, { once: true, margin: '-50px' });

  return (
    <div className="space-y-6" ref={sectionRef}>
      {/* Summary Cards */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate={isInView ? 'visible' : 'hidden'}
      >
        <AnimatedStatCard
          icon={TrendingDown}
          label="Taxa d'execució Catalunya"
          value={35}
          suffix=",1%"
          colorClass={{
            bg: 'bg-red-50',
            border: 'border-red-200',
            iconBg: 'bg-red-100',
            text: 'text-red-600',
            valueText: 'text-red-800',
          }}
          delay={0}
        />
        <AnimatedStatCard
          icon={Euro}
          label="Dèficit acumulat"
          value={50900}
          suffix=" M€"
          colorClass={{
            bg: 'bg-amber-50',
            border: 'border-amber-200',
            iconBg: 'bg-amber-100',
            text: 'text-amber-600',
            valueText: 'text-amber-800',
          }}
          delay={0.1}
        />
        <AnimatedStatCard
          icon={AlertTriangle}
          label="Gap Pla Rodalies 2020-25"
          value={956}
          suffix=" M€"
          colorClass={{
            bg: 'bg-violet-50',
            border: 'border-violet-200',
            iconBg: 'bg-violet-100',
            text: 'text-violet-600',
            valueText: 'text-violet-800',
          }}
          delay={0.2}
        />
      </motion.div>

      {/* Charts Grid */}
      <motion.div
        ref={chartsRef}
        className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        variants={containerVariants}
        initial="hidden"
        animate={chartsInView ? 'visible' : 'hidden'}
      >
        {/* Budget Execution Chart */}
        <motion.div variants={slideInLeft}>
          <Card className="shadow-md hover:shadow-lg transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <motion.span
                  className="inline-block w-3 h-3 rounded-full bg-blue-500"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                Inversió ferroviària Catalunya (2015-2022)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={budgetExecutionData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" domain={[0, 7000]} tickFormatter={(v) => `${v}M€`} />
                  <YAxis type="category" dataKey="name" width={100} />
                  <Tooltip
                    formatter={(value: number) => [`${value.toLocaleString()} M€`, '']}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} animationDuration={1500} animationBegin={300}>
                    {budgetExecutionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <motion.p
                className="text-xs text-muted-foreground mt-2 text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.5 }}
              >
                Només el 35,1% del pressupostat va ser executat
              </motion.p>
            </CardContent>
          </Card>
        </motion.div>

        {/* Regional Comparison */}
        <motion.div variants={slideInRight}>
          <Card className="shadow-md hover:shadow-lg transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <motion.span
                  className="inline-block w-3 h-3 rounded-full bg-emerald-500"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
                />
                % Execució 2015-2022 per territori
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={regionalComparisonData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="region" />
                  <YAxis domain={[0, 50]} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Execució']}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }}
                  />
                  <Bar dataKey="execution" radius={[4, 4, 0, 0]} animationDuration={1500} animationBegin={500}>
                    {regionalComparisonData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <motion.p
                className="text-xs text-muted-foreground mt-2 text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.8 }}
              >
                Catalunya per sota de la mitjana estatal i molt lluny de Madrid
              </motion.p>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>

      {/* Distribution Pie Chart */}
      <motion.div
        ref={pieRef}
        variants={fadeInUp}
        initial="hidden"
        animate={pieInView ? 'visible' : 'hidden'}
      >
        <Card className="shadow-md hover:shadow-lg transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <motion.span
                className="inline-block w-3 h-3 rounded-full bg-blue-500"
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
              />
              Distribució recursos Rodalies (1990-2018)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col md:flex-row items-center justify-center gap-8">
              <ResponsiveContainer width={250} height={250}>
                <PieChart>
                  <Pie
                    data={resourceDistributionData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}%`}
                    animationDuration={1500}
                    animationBegin={200}
                  >
                    {resourceDistributionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Quota']}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <motion.div
                className="space-y-3"
                variants={containerVariants}
                initial="hidden"
                animate={pieInView ? 'visible' : 'hidden'}
              >
                {[
                  { label: 'Madrid: 47%', className: 'bg-blue-100 text-blue-700 border-blue-300' },
                  { label: 'Catalunya: 17%', className: 'bg-red-100 text-red-700 border-red-300' },
                  { label: 'Altres: 36%', className: 'bg-slate-100 text-slate-700 border-slate-300' },
                ].map((item, idx) => (
                  <motion.div key={item.label} variants={cardVariants} className="flex items-center gap-2">
                    <Badge variant="outline" className={`${item.className} cursor-default`}>
                      {item.label}
                    </Badge>
                  </motion.div>
                ))}
                <motion.p
                  className="text-sm text-muted-foreground max-w-xs"
                  variants={fadeInUp}
                >
                  Durant quasi tres dècades, Catalunya va rebre menys d'una cinquena part dels recursos destinats a trens de proximitat.
                </motion.p>
              </motion.div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

// Combined Section Component
export function CrisiFerroviariaSection() {
  return (
    <div className="space-y-8">
      <RodaliesIncidentsMap />
      <InvestmentGapCharts />
    </div>
  );
}
