/**
 * Comparator tab — sub-tab of My EU Bubble, between Position Analysis and My EU Calendar.
 *
 * UX: rather than asking users to type CELEX or OEIL refs from memory, the
 * picker is an autocomplete combobox over Brubru's alias resolver (GDPR, AI Act,
 * Data Act, …) + eu_laws + legislative_carriages. Professional-tier users also
 * get a "Pick from My Files" button that pulls their tracked files in one click.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { mdiCompareHorizontal } from '@mdi/js';
import { MeubHeader } from './meub_header';
import './comparator_tab.css';
import {
  comparatorService,
  type Cell,
  type ColumnDef,
  type GridDetail,
  type GridSummary,
  type SearchHit,
  type TierLimits,
} from '../../services/comparator_service';

type View = 'list' | 'editor';

export const ComparatorTab = () => {
  const { t } = useTranslation();

  const [view, setView] = useState<View>('list');
  const [grids, setGrids] = useState<GridSummary[]>([]);
  const [tierLimits, setTierLimits] = useState<TierLimits>({ max_grids: 1, max_rows: 3, max_cols: 3 });
  const [catalog, setCatalog] = useState<ColumnDef[]>([]);
  const [activeGrid, setActiveGrid] = useState<GridDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);

  const [draftName, setDraftName] = useState<string>('');
  const [draftRefs, setDraftRefs] = useState<string[]>([]);
  const [draftCols, setDraftCols] = useState<ColumnDef[]>([]);
  const [refMetadata, setRefMetadata] = useState<Record<string, SearchHit>>({});

  // Picker (autocomplete combobox)
  const [pickerInput, setPickerInput] = useState<string>('');
  const [pickerHits, setPickerHits] = useState<SearchHit[]>([]);
  const [pickerOpen, setPickerOpen] = useState<boolean>(false);
  const [pickerLoading, setPickerLoading] = useState<boolean>(false);

  // My Tracked Files modal
  const [myFilesOpen, setMyFilesOpen] = useState<boolean>(false);
  const [myFilesHits, setMyFilesHits] = useState<SearchHit[] | null>(null);
  const [myFilesLoading, setMyFilesLoading] = useState<boolean>(false);

  // PI on-ramp: suggested files from the user's interest committees.
  const [suggested, setSuggested] = useState<SearchHit[]>([]);
  const [suggestCommittees, setSuggestCommittees] = useState<string[]>([]);
  const [suggestChips, setSuggestChips] = useState<string[]>([]);

  const pickerDebounceRef = useRef<number | null>(null);

  // ---- Mount ----
  useEffect(() => {
    void refreshList();
    void loadCatalog();
  }, []);

  async function loadCatalog() {
    try {
      const c = await comparatorService.getCatalog();
      setCatalog(c.columns);
    } catch (e) {
      console.warn('Comparator catalog fetch failed:', e);
    }
  }

  async function refreshList() {
    try {
      const list = await comparatorService.listGrids();
      setGrids(list.grids);
      setTierLimits(list.tier_limits);
      setError(null);
    } catch (e: any) {
      setError(extractErr(e));
    }
  }

  function startNewGrid() {
    setDraftName('');
    setDraftRefs([]);
    setDraftCols(catalog.slice(0, Math.min(catalog.length, tierLimits.max_cols)));
    setRefMetadata({});
    setPickerInput('');
    setPickerHits([]);
    setActiveGrid(null);
    setView('editor');
    setError(null);
    setSuccess(null);
  }

  async function openGrid(gridId: string) {
    setBusy(true);
    setError(null);
    try {
      const g = await comparatorService.getGrid(gridId);
      setActiveGrid(g);
      setDraftName(g.name);
      setDraftRefs(g.file_refs);
      setDraftCols(g.columns);
      setRefMetadata(g.file_metadata || {});
      setView('editor');
    } catch (e) {
      setError(extractErr(e));
    } finally {
      setBusy(false);
    }
  }

  function backToList() {
    setView('list');
    setActiveGrid(null);
    setError(null);
    setSuccess(null);
  }

  // ---- Picker (debounced search) ----
  useEffect(() => {
    if (pickerDebounceRef.current) {
      window.clearTimeout(pickerDebounceRef.current);
    }
    const q = pickerInput.trim();
    if (q.length < 2) {
      setPickerHits([]);
      setPickerLoading(false);
      return;
    }
    setPickerLoading(true);
    pickerDebounceRef.current = window.setTimeout(async () => {
      try {
        const res = await comparatorService.search(q, 12);
        setPickerHits(res.hits);
      } catch (e) {
        console.warn('search failed', e);
        setPickerHits([]);
      } finally {
        setPickerLoading(false);
      }
    }, 200);
    return () => {
      if (pickerDebounceRef.current) {
        window.clearTimeout(pickerDebounceRef.current);
      }
    };
  }, [pickerInput]);

  function addHit(hit: SearchHit) {
    if (draftRefs.includes(hit.file_ref)) {
      setError(t('comparator.errAlreadyInGrid', { label: hit.label }));
      return;
    }
    if (draftRefs.length >= tierLimits.max_rows) {
      setError(t('comparator.errTierRows', { max: tierLimits.max_rows }));
      return;
    }
    setDraftRefs([...draftRefs, hit.file_ref]);
    setRefMetadata({ ...refMetadata, [hit.file_ref]: hit });
    maybeAutoName(hit);
    setPickerInput('');
    setPickerHits([]);
    setPickerOpen(false);
    setError(null);
  }

  // Auto-name a new grid from its first file so the Save button isn't blocked
  // by an empty name (a common dead-end: pick a file, can't save). Never
  // overwrites a name the user typed or an existing grid's name.
  function maybeAutoName(hit: SearchHit) {
    if (activeGrid?.id) return;
    if (draftName.trim()) return;
    const base = (hit.deep_dive_short_title || hit.label || '').trim();
    if (base) setDraftName(base.slice(0, 80));
  }

  function removeRef(ref: string) {
    setDraftRefs(draftRefs.filter((r) => r !== ref));
    const next = { ...refMetadata };
    delete next[ref];
    setRefMetadata(next);
  }

  // ---- My Files modal ----
  async function openMyFiles() {
    setMyFilesOpen(true);
    if (myFilesHits === null) {
      setMyFilesLoading(true);
      try {
        const hits = await comparatorService.myFiles();
        setMyFilesHits(hits);
      } catch (e) {
        console.warn('my-files failed', e);
        setMyFilesHits([]);
      } finally {
        setMyFilesLoading(false);
      }
    }
  }

  function addAllMyFiles() {
    if (!myFilesHits) return;
    const room = tierLimits.max_rows - draftRefs.length;
    const toAdd = myFilesHits.filter((h) => !draftRefs.includes(h.file_ref)).slice(0, room);
    if (toAdd.length === 0) {
      setError(t('comparator.errAllTracked'));
      return;
    }
    setDraftRefs([...draftRefs, ...toAdd.map((h) => h.file_ref)]);
    const nextMd = { ...refMetadata };
    for (const h of toAdd) nextMd[h.file_ref] = h;
    setRefMetadata(nextMd);
    maybeAutoName(toAdd[0]);
    setMyFilesOpen(false);
    setError(null);
  }

  // ---- PI suggestions (on-ramp) ----
  useEffect(() => {
    (async () => {
      try {
        const res = await comparatorService.suggested();
        setSuggested(res.files || []);
        setSuggestCommittees(res.my_committees || []);
        setSuggestChips(res.my_committees || []);
      } catch (e) {
        console.warn('suggested failed', e);
      }
    })();
  }, []);

  const toggleSuggestChip = (code: string) =>
    setSuggestChips((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));

  // Suggestions not already in the draft, filtered by the active committee chips,
  // grouped by committee (the PI on-ramp + committee filter, mirroring MTF).
  const suggestGroups = useMemo(() => {
    const active = new Set(suggestChips);
    const items = suggested.filter(
      (h) => !draftRefs.includes(h.file_ref) && (active.size === 0 || (h.committee != null && active.has(h.committee))),
    );
    const byCode = new Map<string, SearchHit[]>();
    for (const h of items) {
      const code = h.committee || 'OTHER';
      const list = byCode.get(code) || [];
      list.push(h);
      byCode.set(code, list);
    }
    return Array.from(byCode.entries())
      .map(([code, hits]) => ({ code, hits }))
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [suggested, suggestChips, draftRefs]);

  const suggestVisibleCount = suggestGroups.reduce((n, g) => n + g.hits.length, 0);

  function addFromInterests() {
    const room = tierLimits.max_rows - draftRefs.length;
    const pool = suggestGroups.flatMap((g) => g.hits);
    const toAdd = pool.slice(0, room);
    if (toAdd.length === 0) {
      setError(t('comparator.noInterestsToAdd'));
      return;
    }
    setDraftRefs([...draftRefs, ...toAdd.map((h) => h.file_ref)]);
    const nextMd = { ...refMetadata };
    for (const h of toAdd) nextMd[h.file_ref] = h;
    setRefMetadata(nextMd);
    maybeAutoName(toAdd[0]);
    setError(null);
  }

  function toggleColumn(c: ColumnDef) {
    const exists = draftCols.find((x) => x.key === c.key);
    if (exists) {
      setDraftCols(draftCols.filter((x) => x.key !== c.key));
    } else {
      if (draftCols.length >= tierLimits.max_cols) {
        setError(t('comparator.errTierCols', { max: tierLimits.max_cols }));
        return;
      }
      setDraftCols([...draftCols, c]);
      setError(null);
    }
  }

  // ---- Save / compute / delete ----
  // Returns the saved grid on success, or null on validation failure / error,
  // so callers can chain a compute (the merged "Save & compute" action).
  async function saveGrid(): Promise<GridDetail | null> {
    setError(null);
    setSuccess(null);
    if (!draftName.trim()) {
      setError(t('comparator.errGridName'));
      return null;
    }
    if (draftRefs.length === 0) {
      setError(t('comparator.errorAddOneFile'));
      return null;
    }
    if (draftCols.length === 0) {
      setError(t('comparator.errPickColumn'));
      return null;
    }
    setBusy(true);
    try {
      let saved: GridDetail;
      if (activeGrid?.id) {
        saved = await comparatorService.patchGrid(activeGrid.id, {
          name: draftName,
          file_refs: draftRefs,
          columns: draftCols,
        });
      } else {
        saved = await comparatorService.createGrid({
          name: draftName,
          file_refs: draftRefs,
          columns: draftCols,
        });
      }
      setActiveGrid(saved);
      setRefMetadata(saved.file_metadata || refMetadata);
      setSuccess(t('comparator.gridSaved'));
      void refreshList();
      return saved;
    } catch (e) {
      setError(extractErr(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function runCompute(gridId?: string) {
    const id = gridId ?? activeGrid?.id;
    if (!id) {
      setError(t('comparator.errSaveFirst'));
      return;
    }
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await comparatorService.computeGrid(id);
      const refreshed = await comparatorService.getGrid(id);
      setActiveGrid(refreshed);
      setRefMetadata(refreshed.file_metadata || refMetadata);
      setSuccess(t('comparator.computeSummary', {
        computed: res.cells_computed,
        failed: res.cells_failed,
        seconds: res.duration_seconds,
      }));
      void refreshList();
    } catch (e) {
      setError(extractErr(e));
    } finally {
      setBusy(false);
    }
  }

  // Merged primary action: save (create or update) then immediately compute.
  async function saveAndCompute() {
    const saved = await saveGrid();
    if (saved?.id) {
      await runCompute(saved.id);
    }
  }

  async function deleteActiveGrid() {
    if (!activeGrid?.id) return;
    if (!window.confirm(t('comparator.confirmDelete', { name: activeGrid.name }))) return;
    setBusy(true);
    try {
      await comparatorService.deleteGrid(activeGrid.id);
      backToList();
      void refreshList();
    } catch (e) {
      setError(extractErr(e));
    } finally {
      setBusy(false);
    }
  }

  const cellsByKey = useMemo(() => {
    const map: Record<string, Cell> = {};
    if (activeGrid) {
      for (const c of activeGrid.cells) {
        map[`${c.file_ref}|${c.column_key}`] = c;
      }
    }
    return map;
  }, [activeGrid]);

  function labelFor(ref: string): string {
    return refMetadata[ref]?.label || ref;
  }
  function subtitleFor(ref: string): string | null {
    return refMetadata[ref]?.subtitle || null;
  }

  return (
    <div className="comparator-tab">
      <MeubHeader
        icon={mdiCompareHorizontal}
        accent="#7b3fc6"
        title={t('comparator.title')}
        titleClassName="meub-head__title--gradient"
        subtitle={t('comparator.subtitle')}
        aside={
          <span className="comparator-tier-badge">
            {t('comparator.tierLimits', {
              grids: tierLimits.max_grids === 9999 ? t('comparator.unlimited') : tierLimits.max_grids,
              rows: tierLimits.max_rows,
              cols: tierLimits.max_cols,
            })}
          </span>
        }
      />

      {error && <div className="comparator-error-banner">{error}</div>}
      {success && <div className="comparator-success-banner">{success}</div>}

      {view === 'list' && (
        <>
          <div className="comparator-toolbar">
            <button className="comparator-btn comparator-btn-primary" onClick={startNewGrid} disabled={busy}>
              {t('comparator.newGrid')}
            </button>
            <span className="comparator-muted">{t('comparator.savedGrids', { count: grids.length })}</span>
          </div>
          <div className="comparator-grid-list">
            {grids.length === 0 && (
              <p className="comparator-muted">{t('comparator.noGridsYet')}</p>
            )}
            {grids.map((g) => (
              <div key={g.id} className="comparator-grid-item" onClick={() => openGrid(g.id)}>
                <div>
                  <h3>{g.name}</h3>
                  <p className="comparator-grid-meta">
                    {t('comparator.filesAndColumns', { files: g.file_refs.length, cols: g.columns.length, cells: g.cell_count })}
                  </p>
                </div>
                <span className="comparator-muted">
                  {t('comparator.updated', { date: new Date(g.updated_at).toLocaleString() })}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {view === 'editor' && (
        <>
          <div className="comparator-toolbar">
            <button className="comparator-btn" onClick={backToList} disabled={busy}>
              ← {t('comparator.back')}
            </button>
            <input
              className="comparator-input"
              placeholder={t('comparator.gridNamePlaceholder')}
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              style={{ flex: 1, maxWidth: 360 }}
            />
            {activeGrid?.id && (
              <button className="comparator-btn comparator-btn-danger" onClick={deleteActiveGrid} disabled={busy}>
                {t('comparator.delete')}
              </button>
            )}
          </div>

          <div className="comparator-editor-pane">
            {/* Files section */}
            <section className="comparator-editor-section">
              <h3 className="comparator-editor-section-title">
                {t('comparator.filesSectionTitle', { current: draftRefs.length, max: tierLimits.max_rows })}
              </h3>
              <p className="comparator-muted">{t('comparator.filesHelp')}</p>

              <div className="comparator-picker-row">
                <div className="comparator-picker-wrap">
                  <input
                    className="comparator-input"
                    placeholder={t('comparator.searchPlaceholder')}
                    value={pickerInput}
                    onChange={(e) => {
                      setPickerInput(e.target.value);
                      setPickerOpen(true);
                    }}
                    onFocus={() => setPickerOpen(true)}
                    onBlur={() => {
                      // Delay so clicks on results register before close
                      window.setTimeout(() => setPickerOpen(false), 180);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') {
                        setPickerOpen(false);
                      } else if (e.key === 'Enter' && pickerHits.length > 0) {
                        e.preventDefault();
                        addHit(pickerHits[0]);
                      }
                    }}
                  />
                  {pickerOpen && pickerInput.trim().length >= 2 && (
                    <div className="comparator-picker-dropdown">
                      {pickerLoading && (
                        <div className="comparator-picker-empty">{t('comparator.searching')}</div>
                      )}
                      {!pickerLoading && pickerHits.length === 0 && (
                        <div className="comparator-picker-empty">{t('comparator.noMatches')}</div>
                      )}
                      {!pickerLoading &&
                        pickerHits.map((h) => (
                          <button
                            key={h.file_ref + '|' + h.source}
                            className="comparator-picker-hit"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              addHit(h);
                            }}
                          >
                            <div className="comparator-picker-hit-label">
                              {h.label}
                              <span className="comparator-picker-hit-tag">{h.source}</span>
                              {h.deep_dive_url && (
                                <span className="comparator-deepdive-pill" title={t('comparator.deepDiveTooltip')}>
                                  {t('comparator.deepDive')}
                                </span>
                              )}
                            </div>
                            {h.subtitle && (
                              <div className="comparator-picker-hit-subtitle">{h.subtitle}</div>
                            )}
                          </button>
                        ))}
                    </div>
                  )}
                </div>

                <button
                  className="comparator-btn comparator-btn-secondary"
                  onClick={openMyFiles}
                  disabled={busy}
                  title={t('comparator.pickFromFiles')}
                >
                  {t('comparator.pickFromFiles')}
                </button>
              </div>

              {/* PI on-ramp: suggested files from the user's interest committees */}
              {suggestCommittees.length > 0 && draftRefs.length < tierLimits.max_rows && (
                <div className="comparator-suggested">
                  <div className="comparator-suggested-head">
                    <h4 className="comparator-suggested-title">{t('comparator.suggestedTitle')}</h4>
                    <button
                      className="comparator-btn comparator-btn-secondary comparator-btn-sm"
                      onClick={addFromInterests}
                      disabled={busy || suggestVisibleCount === 0}
                    >
                      {t('comparator.addFromInterests')}
                    </button>
                  </div>
                  <p className="comparator-muted">{t('comparator.suggestedHelp')}</p>
                  <div className="comparator-suggest-chips">
                    {suggestCommittees.map((code) => (
                      <button
                        key={code}
                        type="button"
                        className={`comparator-chip ${suggestChips.includes(code) ? 'comparator-chip--active' : ''}`}
                        onClick={() => toggleSuggestChip(code)}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                  {suggestVisibleCount === 0 ? (
                    <p className="comparator-muted">{t('comparator.noSuggestions')}</p>
                  ) : (
                    suggestGroups.map((g) => (
                      <div key={g.code} className="comparator-suggest-group">
                        <div className="comparator-suggest-group-title">{g.code}</div>
                        <div className="comparator-suggest-list">
                          {g.hits.slice(0, 6).map((h) => (
                            <button
                              key={h.file_ref}
                              type="button"
                              className="comparator-suggest-hit"
                              onMouseDown={(e) => { e.preventDefault(); addHit(h); }}
                              title={h.subtitle || h.file_ref}
                            >
                              <span className="comparator-suggest-hit-label">{h.label}</span>
                              <span className="comparator-suggest-hit-ref">{h.file_ref}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              <div className="comparator-tag-list" style={{ marginTop: 12 }}>
                {draftRefs.map((r) => {
                  const md = refMetadata[r];
                  return (
                    <span key={r} className="comparator-file-pill" title={r}>
                      <span className="comparator-file-pill-label">{labelFor(r)}</span>
                      {md?.deep_dive_url && (
                        <a
                          className="comparator-deepdive-pill"
                          href={md.deep_dive_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={`Brubru deep-dive: ${md.deep_dive_short_title ?? 'open'}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {t('comparator.deepDive')}
                        </a>
                      )}
                      {subtitleFor(r) && (
                        <span className="comparator-file-pill-sub">{subtitleFor(r)}</span>
                      )}
                      <button
                        className="comparator-tag-remove"
                        onClick={() => removeRef(r)}
                        aria-label={t('comparator.removeRef', { label: labelFor(r) })}
                      >
                        ×
                      </button>
                    </span>
                  );
                })}
              </div>
            </section>

            {/* Columns section */}
            <section className="comparator-editor-section">
              <h3 className="comparator-editor-section-title">
                {t('comparator.columnsSectionTitle', { current: draftCols.length, max: tierLimits.max_cols })}
              </h3>
              <div className="comparator-column-checkboxes">
                {catalog.map((c) => {
                  const selected = !!draftCols.find((x) => x.key === c.key);
                  return (
                    <button
                      key={c.key}
                      className={`comparator-column-checkbox ${selected ? 'selected' : ''}`}
                      onClick={() => toggleColumn(c)}
                    >
                      {c.label}
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Save step (after the flow is complete) */}
            {(() => {
              const missing: string[] = [];
              if (!draftName.trim()) missing.push(t('comparator.missingName'));
              if (draftRefs.length === 0) missing.push(t('comparator.missingFile'));
              if (draftCols.length === 0) missing.push(t('comparator.missingColumn'));
              const ready = missing.length === 0;
              return (
                <section className="comparator-editor-section comparator-save-section">
                  <h3 className="comparator-editor-section-title">
                    {t('comparator.saveAndCompute')}
                  </h3>
                  <p className="comparator-muted">
                    {ready
                      ? t('comparator.savePromptReadyMerged')
                      : t('comparator.savePromptMissing', { missing: missing.join(` ${t('comparator.and')} `) })}
                  </p>
                  <button
                    className="comparator-btn comparator-btn-primary comparator-btn-save"
                    onClick={saveAndCompute}
                    disabled={busy || !ready}
                  >
                    {t('comparator.saveAndCompute')}
                  </button>
                </section>
              );
            })()}

            {/* Spreadsheet */}
            {activeGrid?.id && draftRefs.length > 0 && draftCols.length > 0 && (
              <section className="comparator-editor-section">
                <div className="comparator-grid-head">
                  <h3 className="comparator-editor-section-title">{t('comparator.grid')}</h3>
                  {activeGrid?.id && (
                    <button
                      className="comparator-btn comparator-btn-sm"
                      onClick={saveAndCompute}
                      disabled={busy}
                    >
                      {t('comparator.saveAndCompute')}
                    </button>
                  )}
                </div>
                <p className="comparator-muted">{t('comparator.gridHelp')}</p>
                <div className="comparator-spreadsheet-wrap">
                  <table className="comparator-spreadsheet">
                    <thead>
                      <tr>
                        <th>{t('comparator.file')}</th>
                        {draftCols.map((c) => (
                          <th key={c.key}>{c.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {draftRefs.map((ref) => {
                        const md = refMetadata[ref];
                        return (
                        <tr key={ref}>
                          <td className="comparator-cell-row-header">
                            <div className="comparator-row-label">
                              {labelFor(ref)}
                              {md?.deep_dive_url && (
                                <a
                                  className="comparator-deepdive-pill"
                                  href={md.deep_dive_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title={`Brubru deep-dive: ${md.deep_dive_short_title ?? 'open'}`}
                                  style={{ marginLeft: 6 }}
                                >
                                  {t('comparator.deepDive')}
                                </a>
                              )}
                            </div>
                            {subtitleFor(ref) && (
                              <div className="comparator-row-sub">{subtitleFor(ref)}</div>
                            )}
                          </td>
                          {draftCols.map((col) => {
                            const cell = cellsByKey[`${ref}|${col.key}`];
                            if (!cell) {
                              return (
                                <td key={col.key} className="comparator-cell-empty">
                                  {t('comparator.notComputed')}
                                </td>
                              );
                            }
                            if (cell.computation_status === 'failed') {
                              return (
                                <td
                                  key={col.key}
                                  className="comparator-cell-failed"
                                  title={cell.computation_error ?? t('comparator.unknown')}
                                >
                                  {t('comparator.failed')}
                                </td>
                              );
                            }
                            if (cell.value_text === null) {
                              return (
                                <td
                                  key={col.key}
                                  className="comparator-cell-empty"
                                  title={cell.computation_error ?? t('comparator.unknown')}
                                >
                                  {cell.computation_error
                                    ? cell.computation_error
                                    : t('comparator.unknown')}
                                </td>
                              );
                            }
                            const cite = cell.citation;
                            return (
                              <td key={col.key}>
                                {cell.value_text}
                                {cite?.url && (
                                  <a
                                    className="comparator-cell-citation"
                                    href={cite.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title={cite.source ?? t('comparator.source')}
                                  >
                                    {t('comparator.source')}
                                  </a>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        </>
      )}

      {/* My Files modal — rendered via portal to document.body so framer-motion
          transform parents (AnimatedPage) don't clip the position:fixed overlay. */}
      {myFilesOpen && createPortal(
        <div
          className="comparator-modal-overlay"
          onClick={() => setMyFilesOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label={t('comparator.pickFromFiles')}
        >
          <div className="comparator-modal" onClick={(e) => e.stopPropagation()}>
            <div className="comparator-modal-header">
              <h3>{t('comparator.pickFromFiles')}</h3>
              <button
                className="comparator-tag-remove"
                onClick={() => setMyFilesOpen(false)}
                aria-label={t('comparator.close')}
              >
                ×
              </button>
            </div>
            {myFilesLoading && <p className="comparator-muted">{t('comparator.loadingDots')}</p>}
            {!myFilesLoading && myFilesHits && myFilesHits.length === 0 && (
              <p className="comparator-muted">{t('comparator.noTrackedFiles')}</p>
            )}
            {!myFilesLoading && myFilesHits && myFilesHits.length > 0 && (
              <>
                <p className="comparator-muted">
                  {t('comparator.trackedFilesCount', { count: myFilesHits.length })}
                </p>
                <div className="comparator-myfiles-list">
                  {myFilesHits.map((h) => {
                    const already = draftRefs.includes(h.file_ref);
                    return (
                      <button
                        key={h.file_ref}
                        className={`comparator-myfiles-item ${already ? 'already-added' : ''}`}
                        onClick={() => {
                          if (!already) addHit(h);
                        }}
                        disabled={already}
                      >
                        <div className="comparator-myfiles-item-label">
                          {h.label} {already && <span className="comparator-muted">· {t('comparator.alreadyInGrid')}</span>}
                        </div>
                        {h.subtitle && (
                          <div className="comparator-myfiles-item-sub">{h.subtitle}</div>
                        )}
                      </button>
                    );
                  })}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button
                    className="comparator-btn comparator-btn-primary"
                    onClick={addAllMyFiles}
                  >
                    {t('comparator.addAll')}
                  </button>
                  <button className="comparator-btn" onClick={() => setMyFilesOpen(false)}>
                    {t('comparator.close')}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
};

function extractErr(e: any): string {
  return e?.response?.data?.detail || e?.message || 'Unknown error';
}

export default ComparatorTab;
