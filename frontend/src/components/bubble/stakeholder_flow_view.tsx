/**
 * Stakeholder Mapping - "Map" renderer (React Flow / @xyflow/react).
 * Structured clustered view: institution lanes (EP | Council | File | EC | Stakeholders).
 * Lazy-loaded by the SM tab.
 */
import { useMemo } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { SMGraph, SMNode } from '../../services/stakeholders_service';

const LANES: SMNode['institution'][] = ['ep', 'council', 'file', 'ec', 'stakeholder'];
const COL_W = 440;
const ROW_H = 136;

export default function StakeholderFlowView(
  { graph, colorOf, onPick }: { graph: SMGraph; colorOf: (n: SMNode) => string; onPick: (n: SMNode) => void },
) {
  const { nodes, edges } = useMemo(() => {
    const byLane: Record<string, SMNode[]> = {};
    LANES.forEach((l) => { byLane[l] = []; });
    graph.nodes.forEach((n) => { (byLane[n.institution] || byLane.file).push(n); });

    const rfNodes: any[] = [];
    LANES.forEach((lane, ci) => {
      const list = byLane[lane] || [];
      list.sort((a, b) => (b.relevance || 0) - (a.relevance || 0));
      const h = list.length;
      list.forEach((n, i) => {
        rfNodes.push({
          id: n.id,
          position: { x: ci * COL_W, y: (i - (h - 1) / 2) * ROW_H },
          data: { label: n.sublabel ? `${n.label}\n${n.sublabel}` : n.label, node: n },
          style: {
            background: colorOf(n), color: '#fff', border: 'none', borderRadius: 12,
            padding: '7px 10px', fontSize: 11, fontWeight: 600, width: 178,
            textAlign: 'center', whiteSpace: 'pre-line', lineHeight: 1.25,
            boxShadow: '0 4px 12px rgba(15,23,42,0.12)',
            opacity: n.pi_match === false && graph.pi_active ? 0.82 : 1,
          },
        });
      });
    });

    const ids = new Set(rfNodes.map((n) => n.id));
    // Smooth, low-contrast edges with no per-edge labels (the relationship reads
    // from the lane layout + the detail drawer) so links don't crowd the cards.
    const rfEdges = graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e, i) => ({
        id: `e${i}`, source: e.source, target: e.target, type: 'smoothstep',
        style: {
          stroke: e.source_kind === 'pi_crosswalk' ? '#dbe2ea' : '#9fb3c8',
          strokeWidth: e.source_kind === 'pi_crosswalk' ? 1 : 1.4,
          opacity: 0.65,
        },
      }));
    return { nodes: rfNodes, edges: rfEdges };
  }, [graph, colorOf]);

  return (
    <div className="sm-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.15}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, n: any) => onPick(n.data.node as SMNode)}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#eef2f7" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
