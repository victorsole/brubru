// One download control for every My EU Bubble sub-tab.
//
// A tab supplies the endpoint it already reads and the filters it is already
// applying; this asks the same question again with format=xlsx. Nothing about
// the data is decided here, which is why it can be dropped into 25 tabs
// without each one growing its own export logic.

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiFileExcelOutline, mdiLoading, mdiAlertCircleOutline } from '@mdi/js';
import { downloadExport } from '../../utils/export_download';
import './export_button.css';

interface ExportButtonProps {
  /** API path the tab reads, e.g. "/api/ep-votes/plenary". */
  path: string;
  /** The tab's current filters, passed through verbatim. */
  params?: Record<string, string | number | boolean | undefined>;
  /** Rows to request. Endpoints cap this; the label reports what arrived. */
  limit?: number;
  /** Optional label override; defaults to "Excel". */
  label?: string;
  className?: string;
}

type State = { kind: 'idle' | 'busy' | 'error' } | { kind: 'done'; rows: number; truncated: boolean };

export const ExportButton = ({ path, params = {}, limit = 200, label, className = '' }: ExportButtonProps) => {
  const { t } = useTranslation();
  const [state, setState] = useState<State>({ kind: 'idle' });

  const run = async () => {
    setState({ kind: 'busy' });
    try {
      const result = await downloadExport(path, { ...params, limit }, limit);
      setState({ kind: 'done', rows: result.rows, truncated: result.truncated });
      setTimeout(() => setState({ kind: 'idle' }), 6000);
    } catch {
      setState({ kind: 'error' });
      setTimeout(() => setState({ kind: 'idle' }), 6000);
    }
  };

  const busy = state.kind === 'busy';

  return (
    <span className={`export-button__wrap ${className}`}>
      <button
        type="button"
        className="export-button"
        onClick={run}
        disabled={busy}
        title={t('export.title', 'Download what you are seeing as an Excel file')}
      >
        <Icon path={busy ? mdiLoading : mdiFileExcelOutline} size={0.7} spin={busy} />
        {label || t('export.label', 'Excel')}
      </button>
      {state.kind === 'done' && (
        <span className="export-button__note" role="status">
          {state.truncated
            ? t('export.doneCapped', 'Downloaded the first {{n}} rows', { n: state.rows })
            : t('export.done', 'Downloaded {{n}} rows', { n: state.rows })}
        </span>
      )}
      {state.kind === 'error' && (
        <span className="export-button__note export-button__note--error" role="status">
          <Icon path={mdiAlertCircleOutline} size={0.6} />
          {t('export.failed', 'Nothing to export here yet')}
        </span>
      )}
    </span>
  );
};
