// frontend/src/components/api_console/catalogue_pane.tsx
// Every route the API serves, from the live spec: for people who want more than the starting points. Typing here only
// filters the list in the browser: no call is made.
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ConsoleCatalogue, ConsoleOperation, RouteWordsMap } from '../../services/api_console';
import { BUNDLE_ORDER, bundleCount, searchOperations, summaryIn } from '../../services/api_console';

const MAX_RESULTS = 100;

interface Props {
  catalogue: ConsoleCatalogue;
  selected: ConsoleOperation | null;
  onSelect: (op: ConsoleOperation) => void;
  bundle: string;
  onBundle: (bundle: string) => void;
  routeWords: RouteWordsMap;
}

const Row = ({ op, active, onSelect, routeWords }: { op: ConsoleOperation; active: boolean; onSelect: (op: ConsoleOperation) => void; routeWords: RouteWordsMap }) => {
  const { t } = useTranslation();
  return (
    <li>
      <button
        type="button"
        className={`api-console__route${active ? ' api-console__route--active' : ''}`}
        aria-current={active ? 'true' : undefined}
        data-route={op.path}
        onClick={() => onSelect(op)}
      >
        {op.summary && <span className="api-console__route-summary">{summaryIn(op, routeWords)}</span>}
        <code>{op.path.replace('/api/v2', '')}</code>
        {op.deprecated && <span className="api-console__badge">{t('api.console.deprecated')}</span>}
      </button>
    </li>
  );
};

export const CataloguePane = ({ catalogue, selected, onSelect, bundle, onBundle, routeWords }: Props) => {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState<string | null>(selected?.folder ?? null);
  const results = useMemo(
    () => searchOperations(catalogue, query, routeWords).filter((op) => !bundle || op.bundles.includes(bundle)),
    [catalogue, query, bundle, routeWords],
  );
  const folders = useMemo(() => (
    bundle
      ? catalogue.folders
        .map((f) => ({ ...f, operations: f.operations.filter((op) => op.bundles.includes(bundle)) }))
        .filter((f) => f.operations.length > 0)
      : catalogue.folders
  ), [catalogue, bundle]);
  const searching = query.trim().length > 0;
  const shown = bundle ? bundleCount(catalogue, bundle) : catalogue.operations.length;
  const count = shown.toLocaleString(i18n.language);
  const bundles = BUNDLE_ORDER.filter((id) => bundleCount(catalogue, id) > 0);

  // The folder of the chosen route is the open one, including when a bundle chooses the route.
  useEffect(() => {
    if (selected) setOpen(selected.folder);
  }, [selected]);

  return (
    <div className="api-console__pane api-console__pane--catalogue">
      {bundles.length > 0 && (
        <div className="api-console__bundle-picker">
          <label htmlFor="api-console-bundle">{t('api.console.bundleLabel')}</label>
          <select id="api-console-bundle" value={bundle} onChange={(e) => onBundle(e.target.value)}>
            <option value="">{t('api.console.allRoutes')} ({catalogue.operations.length.toLocaleString(i18n.language)})</option>
            {bundles.map((id) => (
              <option key={id} value={id}>
                {t(`api.bundles.${id}.name`, { defaultValue: id })} ({bundleCount(catalogue, id).toLocaleString(i18n.language)})
              </option>
            ))}
          </select>
        </div>
      )}
      <label className="api-console__sr-only" htmlFor="api-console-search">{t('api.console.search', { count })}</label>
      <input
        id="api-console-search"
        className="api-console__search"
        type="search"
        placeholder={t('api.console.search', { count })}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoComplete="off"
      />
      <div className="api-console__list">
        {searching ? (
          <>
            <p className="api-console__note" role="status">
              {results.length === 0
                ? t('api.console.noMatch')
                : results.length > MAX_RESULTS
                  ? t('api.console.firstResults', { shown: MAX_RESULTS, count: results.length.toLocaleString(i18n.language) })
                  : t('api.console.resultCount', { count: results.length })}
            </p>
            <ul className="api-console__routes">
              {results.slice(0, MAX_RESULTS).map((op) => (
                <Row key={op.path} op={op} active={selected?.path === op.path} onSelect={onSelect} routeWords={routeWords} />
              ))}
            </ul>
          </>
        ) : (
          folders.map((folder) => {
            const isOpen = open === folder.id;
            return (
              <div className="api-console__folder" key={folder.id}>
                <button
                  type="button"
                  className="api-console__folder-head"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : folder.id)}
                >
                  <span className={`mdi ${isOpen ? 'mdi-chevron-down' : 'mdi-chevron-right'}`} aria-hidden="true" />
                  <span className="api-console__folder-name">{folder.id}</span>
                  <span className="api-console__folder-count">{folder.operations.length}</span>
                </button>
                {isOpen && (
                  <ul className="api-console__routes">
                    {folder.operations.map((op) => (
                      <Row key={op.path} op={op} active={selected?.path === op.path} onSelect={onSelect} routeWords={routeWords} />
                    ))}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
