/**
 * Archive service — shared client for the My EU Bubble archive feature.
 *
 * Lets users archive ("Dismiss") items that have run their course and restore
 * them later. Backed by /api/archive/* (see backend/api/archive.py).
 *
 * Track-based entities (carriage, consultation, committee_work, commission_doc,
 * text_adopted, vote) archive by the UserXTrack id. Calendar events are shared
 * rows, so they archive per-user by event_id via the join-table endpoints.
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/archive`;

export type ArchiveEntityType =
  | 'carriage'
  | 'consultation'
  | 'committee_work'
  | 'commission_doc'
  | 'text_adopted'
  | 'vote';

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const archiveService = {
  /** Archive a tracked item (Dismiss). reason defaults to 'user'. */
  archive: async (entityType: ArchiveEntityType, trackId: string, reason = 'user') => {
    const r = await axios.post(
      `${API_BASE}/${entityType}/${trackId}?reason=${encodeURIComponent(reason)}`,
      {},
      { headers: authHeaders() },
    );
    return r.data;
  },

  /** Restore (un-archive) a tracked item. */
  restore: async (entityType: ArchiveEntityType, trackId: string) => {
    const r = await axios.post(
      `${API_BASE}/${entityType}/${trackId}/restore`,
      {},
      { headers: authHeaders() },
    );
    return r.data;
  },

  /** Archive a shared calendar event for the current user only. */
  archiveCalendar: async (eventId: string, reason = 'user') => {
    const r = await axios.post(
      `${API_BASE}/calendar/${eventId}?reason=${encodeURIComponent(reason)}`,
      {},
      { headers: authHeaders() },
    );
    return r.data;
  },

  /** Restore a calendar event for the current user. */
  restoreCalendar: async (eventId: string) => {
    const r = await axios.post(
      `${API_BASE}/calendar/${eventId}/restore`,
      {},
      { headers: authHeaders() },
    );
    return r.data;
  },
};
