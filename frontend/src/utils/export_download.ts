// Downloading what a tab is showing, as a spreadsheet.
//
// The export runs server-side: the tab re-issues its own query with
// ?format=xlsx, and TabularExportMiddleware turns the same JSON the tab
// rendered into a sheet. That keeps one source of truth -- the endpoint --
// so the file cannot drift from the screen, and auth, tier gating and rate
// limits apply exactly as they do for the JSON call.

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ExportResult {
  /** Rows actually written. Exports are capped per endpoint. */
  rows: number;
  filename: string;
  /** True when the row count hit the requested cap, so there is likely more. */
  truncated: boolean;
}

const filenameFrom = (disposition: string | undefined, fallback: string): string => {
  const match = /filename="?([^";]+)"?/i.exec(disposition || '');
  return match ? match[1] : fallback;
};

/**
 * Fetch `path` with the caller's own params plus format=xlsx, and hand the
 * browser the file.
 *
 * @param path   API path, e.g. "/api/ep-votes/plenary"
 * @param params The tab's current filters, verbatim
 * @param cap    The limit requested, used only to report truncation
 */
export const downloadExport = async (
  path: string,
  params: Record<string, string | number | boolean | undefined>,
  cap?: number,
): Promise<ExportResult> => {
  const clean: Record<string, string> = {};
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') clean[k] = String(v);
  });
  clean.format = 'xlsx';

  let response;
  try {
    response = await axios.get(`${API_BASE}${path}`, { params: clean, responseType: 'blob' });
  } catch (err: unknown) {
    // Endpoints cap `limit` at different values (mep-watch at 120, questions at
    // 200) and a caller asking for more gets a 422, not a smaller page. Rather
    // than hard-code every cap across 25 tabs, drop the limit and let the
    // endpoint apply its own default.
    const status = (err as { response?: { status?: number } })?.response?.status;
    if (status !== 422) throw err;
    const { limit: _dropped, ...withoutLimit } = clean;
    response = await axios.get(`${API_BASE}${path}`, { params: withoutLimit, responseType: 'blob' });
  }

  // A JSON body here means the middleware declined to transform (no record
  // list, or a serialisation failure it degraded from). Downloading that as
  // .xlsx would hand the user a file Excel refuses to open.
  const type = String(response.headers['content-type'] || '');
  if (type.includes('application/json')) {
    throw new Error('export-unavailable');
  }

  const rows = Number(response.headers['x-export-rows'] || 0);
  const filename = filenameFrom(
    response.headers['content-disposition'] as string | undefined,
    `brubru_export.xlsx`,
  );

  const url = URL.createObjectURL(response.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick: revoking synchronously can cancel the download
  // in Safari before it has read the blob.
  setTimeout(() => URL.revokeObjectURL(url), 1000);

  return { rows, filename, truncated: cap !== undefined && rows >= cap };
};
