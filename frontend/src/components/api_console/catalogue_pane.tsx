// frontend/src/components/api_console/catalogue_pane.tsx
// Every route the API serves, from the live spec. Typing here only filters the list in the browser: no call is made.
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ConsoleCatalogue, ConsoleOperation } from '../../services/api_console';
import { searchOperations } from '../../services/api_console';

const MAX_RESULTS = 100;

interface Props {
  catalogue: ConsoleCatalogue;
  selected: ConsoleOperation | null;
  onSelect: (op: ConsoleOperation) => void;
}

const Row = ({ op, active, onSelect }: { op: ConsoleOperation; active: boolean; onSelect: (op: ConsoleOperation) => void }) => {
  const { t } = useTranslation();
  return (
    <li>
      <button
        type="button"
        className={`api-console__route${active ? ' api-console__route--active' : ''}`}
        aria-current={active ? 'true' : undefined}
        onClick={() => onSelect(op)}
      >
        <code>{op.path.replace('/api/v2', '')}</code>
        {op.summary && <span className="api-console__route-summary">{op.summary}</span>}
        {op.deprecated && <span className="api-console__badge">{t('api.console.deprecated')}</span>}
      </button>
    </li>
  );
};

export const CataloguePane = ({ catalogue, selected, onSelect }: Props) => {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState<string | null>(selected?.folder ?? null);
  const results = useMemo(() => searchOperations(catalogue, query), [catalogue, query]);
  const searching = query.trim().length > 0;
  const count = catalogue.operations.length.toLocaleString(i18n.language);

  return (
    <div className="api-console__pane api-console__pane--catalogue">
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
                <Row key={op.path} op={op} active={selected?.path === op.path} onSelect={onSelect} />
              ))}
            </ul>
          </>
        ) : (
          catalogue.folders.map((folder) => {
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
                      <Row key={op.path} op={op} active={selected?.path === op.path} onSelect={onSelect} />
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
