/**
 * Stakeholder Mapping - "Web" renderer (react-force-graph-2d).
 * Organic force-directed view of the actor graph. Lazy-loaded by the SM tab.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { SMGraph, SMNode } from '../../services/stakeholders_service';

export default function StakeholderForceView(
  { graph, colorOf, onPick }: { graph: SMGraph; colorOf: (n: SMNode) => string; onPick: (n: SMNode) => void },
) {
  const wrap = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [w, setW] = useState(800);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Spread the graph out: stronger node repulsion + longer links so the dots
  // do not clump together. Scaled down a touch for very large graphs.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    const n = graph.nodes.length || 1;
    try {
      fg.d3Force('charge')?.strength(n > 40 ? -380 : -650).distanceMax(900);
      fg.d3Force('link')?.distance((l: any) => (l.source_kind === 'pi_crosswalk' ? 120 : 170)).strength(0.35);
      fg.d3Force('center')?.strength(0.025);
      fg.d3ReheatSimulation?.();
    } catch { /* force config is best-effort */ }
  }, [graph]);

  const data = useMemo(() => ({
    nodes: graph.nodes.map((n) => ({ ...n })),
    links: graph.edges.map((e) => ({ source: e.source, target: e.target, rel: e.rel, source_kind: e.source_kind })),
  }), [graph]);

  return (
    <div ref={wrap} className="sm-canvas">
      <ForceGraph2D
        ref={fgRef}
        width={w}
        height={620}
        graphData={data as any}
        nodeId="id"
        nodeLabel={(n: any) => `${n.label}${n.sublabel ? ' — ' + n.sublabel : ''}`}
        nodeRelSize={6}
        d3VelocityDecay={0.32}
        cooldownTicks={160}
        warmupTicks={40}
        linkColor={(l: any) => (l.source_kind === 'pi_crosswalk' ? 'rgba(203,213,225,0.5)' : 'rgba(148,163,184,0.5)')}
        linkWidth={(l: any) => (l.source_kind === 'pi_crosswalk' ? 0.6 : 1.2)}
        onNodeClick={(n: any) => onPick(n as SMNode)}
        nodePointerAreaPaint={(n: any, color: string, ctx: any) => {
          const r = 4 + (n.relevance || 0.4) * 6;
          ctx.fillStyle = color;
          ctx.beginPath(); ctx.arc(n.x, n.y, r + 2, 0, 2 * Math.PI); ctx.fill();
        }}
        nodeCanvasObject={(n: any, ctx: any, scale: number) => {
          const r = 4 + (n.relevance || 0.4) * 6;
          ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = colorOf(n as SMNode); ctx.fill();
          if (scale > 1.3 || (n.relevance || 0) >= 0.7) {
            ctx.font = `${Math.max(8, 11 / scale)}px Inter, system-ui, sans-serif`;
            ctx.fillStyle = '#334155';
            ctx.textBaseline = 'middle';
            ctx.fillText(String(n.label).slice(0, 26), n.x + r + 3, n.y + 3);
          }
        }}
      />
    </div>
  );
}
