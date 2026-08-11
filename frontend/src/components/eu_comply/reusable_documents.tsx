// frontend/src/components/eu_comply/reusable_documents.tsx
//
// "Use the documents from last time" -- the fix for the single worst friction
// point in the feature.
//
// Migration 209 began storing the extracted text of every uploaded document,
// and every run since has been recording which documents it was performed
// against. None of it was ever readable, so a user checking the same package a
// second time was shown an empty dropzone and had to go and find the same
// policy file again. Re-checking after remediation is the entire point of a
// durable workspace, and the product asked you to start from nothing each time.
//
// Selection is additive with the upload control: re-use last quarter's policy
// AND attach the new annex. The dropzone stays exactly where it was.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './reusable_documents.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ReusableDocument {
  id: string;
  title: string;
  filename: string | null;
  characters: number;
  last_used_at: string | null;
  used_in_runs: number;
  duplicate_copies: number;
}

interface ReusableDocumentsProps {
  clusterId: number;
  selected: string[];
  onChange: (ids: string[]) => void;
}

export const ReusableDocuments = ({ clusterId, selected, onChange }: ReusableDocumentsProps) => {
  const { t } = useTranslation();
  const [docs, setDocs] = useState<ReusableDocument[] | null>(null);

  useEffect(() => {
    const token = useAuth.getState().token;
    if (!token) { setDocs([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${API_BASE_URL}/api/eu-law-comply/clusters/${clusterId}/documents`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!r.ok) throw new Error(String(r.status));
        const d = await r.json();
        if (!cancelled) setDocs(d.documents || []);
      } catch {
        // Falling back to upload-only is a complete path, so a failure here is
        // silent rather than an error the user cannot act on.
        if (!cancelled) setDocs([]);
      }
    })();
    return () => { cancelled = true; };
  }, [clusterId]);

  // Nothing stored for this package yet: this is a first run, and the dropzone
  // below already says everything that needs saying.
  if (!docs || docs.length === 0) return null;

  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };

  return (
    <section className="reuse-docs">
      <div className="reuse-docs__head">
        <span className="mdi mdi-file-restore-outline"></span>
        <span className="reuse-docs__heading">
          {t('comply.reuse.heading', 'Re-use what you checked last time')}
        </span>
        <span className="reuse-docs__count">
          {selected.length > 0
            ? `${selected.length} ${t('comply.reuse.selected', 'selected')}`
            : `${docs.length} ${docs.length === 1
                ? t('comply.reuse.available', 'available')
                : t('comply.reuse.availablePlural', 'available')}`}
        </span>
      </div>

      <ul className="reuse-docs__list">
        {docs.map((d) => {
          const isOn = selected.includes(d.id);
          return (
            <li key={d.id}>
              <label className={`reuse-docs__item${isOn ? ' is-selected' : ''}`}>
                <input
                  type="checkbox"
                  className="reuse-docs__checkbox"
                  checked={isOn}
                  onChange={() => toggle(d.id)}
                />
                <span className="mdi mdi-file-document-outline reuse-docs__icon"></span>
                <span className="reuse-docs__meta">
                  <span className="reuse-docs__name">{d.filename || d.title}</span>
                  <span className="reuse-docs__detail">
                    {d.characters.toLocaleString()} {t('comply.reuse.characters', 'characters')}
                    {d.last_used_at && (
                      <>
                        {' '}&middot; {t('comply.reuse.lastUsed', 'last used')}{' '}
                        {new Date(d.last_used_at).toLocaleDateString()}
                      </>
                    )}
                    {d.used_in_runs > 1 && (
                      <>
                        {' '}&middot; {d.used_in_runs} {t('comply.reuse.runs', 'runs')}
                      </>
                    )}
                  </span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>

      <p className="reuse-docs__hint">
        {t(
          'comply.reuse.hint',
          'Selected documents are checked again as they are. You can also add new files below.',
        )}
      </p>
    </section>
  );
};

export default ReusableDocuments;
