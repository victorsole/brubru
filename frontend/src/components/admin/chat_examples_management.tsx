import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ChatExample {
  id: string;
  text: string;
  locale?: string | null;
  scope: string;
  subscription_tiers?: string[] | null;
  is_active: boolean;
  sort_order: number;
  usage_count: number;
}

export const ChatExamplesManagement = () => {
  const { token } = useAuth();
  const [items, setItems] = useState<ChatExample[]>([]);
  const [loading, setLoading] = useState(true);
  const [localeFilter, setLocaleFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');

  // Form state for create/edit
  const [editing, setEditing] = useState<ChatExample | null>(null);
  const [form, setForm] = useState<{ text: string; locale?: string; scope: string; tiers: string; is_active: boolean }>(
    { text: '', locale: '', scope: 'main_chat', tiers: '', is_active: true }
  );

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const load = async () => {
    try {
      setLoading(true);
      const resp = await axios.get(`${API_BASE_URL}/api/admin/chat-examples`, {
        headers,
        params: {
          locale: localeFilter || undefined,
          scope: scopeFilter || undefined,
        },
      });
      setItems(resp.data);
    } catch (e: any) {
      console.error(e.response?.data?.detail || 'Failed to load examples');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setEditing(null);
    setForm({ text: '', locale: '', scope: 'main_chat', tiers: '', is_active: true });
  };

  const onSubmit = async () => {
    try {
      const payload = {
        text: form.text,
        locale: form.locale || null,
        scope: form.scope || 'main_chat',
        subscription_tiers: form.tiers ? form.tiers.split(',').map(s => s.trim()).filter(Boolean) : null,
        is_active: form.is_active,
      };
      if (editing) {
        const resp = await axios.patch(`${API_BASE_URL}/api/admin/chat-examples/${editing.id}`, payload, { headers });
        const updated = resp.data as ChatExample;
        setItems(prev => prev.map(i => i.id === updated.id ? updated : i));
      } else {
        const resp = await axios.post(`${API_BASE_URL}/api/admin/chat-examples`, payload, { headers });
        setItems(prev => [...prev, resp.data]);
      }
      resetForm();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to save');
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm('Delete this example?')) return;
    try {
      await axios.delete(`${API_BASE_URL}/api/admin/chat-examples/${id}`, { headers });
      setItems(prev => prev.filter(i => i.id !== id));
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to delete');
    }
  };

  const onToggleActive = async (item: ChatExample) => {
    try {
      const resp = await axios.patch(`${API_BASE_URL}/api/admin/chat-examples/${item.id}`, { is_active: !item.is_active }, { headers });
      const updated = resp.data as ChatExample;
      setItems(prev => prev.map(i => i.id === updated.id ? updated : i));
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to update');
    }
  };

  const move = async (id: string, direction: 'up' | 'down') => {
    const ix = items.findIndex(i => i.id === id);
    const newIdx = direction === 'up' ? ix - 1 : ix + 1;
    if (ix < 0 || newIdx < 0 || newIdx >= items.length) return;
    const reordered = [...items];
    const [moved] = reordered.splice(ix, 1);
    reordered.splice(newIdx, 0, moved);
    setItems(reordered);
    try {
      await axios.patch(`${API_BASE_URL}/api/admin/chat-examples/reorder`, {
        ordered_ids: reordered.map(i => i.id)
      }, { headers });
    } catch {
      // revert on failure
      setItems(items);
      alert('Failed to reorder');
    }
  };

  if (loading && items.length === 0) {
    return <div className="admin-section__loading">Loading chat examples...</div>;
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Chat Examples</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Locale (e.g., en, en-GB)"
            value={localeFilter}
            onChange={(e) => setLocaleFilter(e.target.value)}
            className="admin-section__search"
          />
          <input
            type="text"
            placeholder="Scope (default: main_chat)"
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className="admin-section__search"
          />
          <button className="btn btn--primary btn--small" onClick={load}>Filter</button>
          <button className="btn btn--success btn--small" onClick={load}>Refresh</button>
        </div>
      </div>

      {/* Create/Edit form */}
      <div className="admin-section__card" style={{ marginBottom: 16 }}>
        <div className="admin-section__card-header">
          <strong>{editing ? 'Edit Example' : 'Create Example'}</strong>
        </div>
        <div className="admin-section__card-body" style={{ display: 'grid', gap: 8 }}>
          <input
            type="text"
            placeholder="Prompt text"
            value={form.text}
            onChange={(e) => setForm({ ...form, text: e.target.value })}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              placeholder="Locale (optional)"
              value={form.locale}
              onChange={(e) => setForm({ ...form, locale: e.target.value })}
            />
            <input
              type="text"
              placeholder="Scope"
              value={form.scope}
              onChange={(e) => setForm({ ...form, scope: e.target.value })}
            />
          </div>
          <input
            type="text"
            placeholder="Subscription tiers (comma-separated, optional)"
            value={form.tiers}
            onChange={(e) => setForm({ ...form, tiers: e.target.value })}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn--primary btn--small" onClick={onSubmit}>{editing ? 'Update' : 'Create'}</button>
            {editing && (
              <button className="btn btn--secondary btn--small" onClick={resetForm}>Cancel</button>
            )}
          </div>
        </div>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Text</th>
              <th>Locale</th>
              <th>Scope</th>
              <th>Tiers</th>
              <th>Active</th>
              <th>Usage</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it, idx) => (
              <tr key={it.id}>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn--small" onClick={() => move(it.id, 'up')} disabled={idx === 0}>↑</button>
                    <button className="btn btn--small" onClick={() => move(it.id, 'down')} disabled={idx === items.length - 1}>↓</button>
                  </div>
                </td>
                <td style={{ maxWidth: 420 }}>
                  <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.text}</div>
                </td>
                <td>{it.locale || '-'}</td>
                <td>{it.scope}</td>
                <td>{it.subscription_tiers?.join(', ') || 'All'}</td>
                <td>
                  <span className={`admin-section__status ${it.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                    {it.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{it.usage_count}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn--small" onClick={() => { setEditing(it); setForm({ text: it.text, locale: it.locale || '', scope: it.scope, tiers: it.subscription_tiers?.join(', ') || '', is_active: it.is_active }); }}>Edit</button>
                    <button className="btn btn--small" onClick={() => onToggleActive(it)}>{it.is_active ? 'Deactivate' : 'Activate'}</button>
                    <button className="btn btn--danger btn--small" onClick={() => onDelete(it.id)}>Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
