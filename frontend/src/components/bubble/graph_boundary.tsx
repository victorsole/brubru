/**
 * Small error boundary for the graph renderers. A throw inside a graph library
 * (e.g. react-force-graph under React 18 StrictMode) is caught here and shown as
 * a friendly fallback, instead of crashing the whole MEUB page to a blank screen.
 * Reset it by giving it a new `key` (the SM tab keys it by view + focus).
 */
import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { err: Error | null }

export class GraphBoundary extends Component<Props, State> {
  state: State = { err: null };
  static getDerivedStateFromError(err: Error): State { return { err }; }
  componentDidCatch(err: Error) { console.error('[stakeholder-map] graph render error', err); }
  render() {
    if (this.state.err) {
      return this.props.fallback ?? (
        <div className="db-note"><span>This view could not be rendered.</span></div>
      );
    }
    return this.props.children;
  }
}

export default GraphBoundary;
