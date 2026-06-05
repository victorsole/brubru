/**
 * API Keys Service
 *
 * Typed client for /api/me/api-keys (self-serve mint + list + revoke).
 *
 * Backend: backend/api/me_api_keys.py
 */

import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/me/api-keys`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ============================================================================
// Types — must match backend Pydantic schemas in me_api_keys.py
// ============================================================================

export interface ScopeOption {
  name: string;
  label: string;
  description: string;
  default_on_self_serve: boolean;
}

export interface ScopeCatalogue {
  scopes: ScopeOption[];
  defaults: string[];
  expiry_options_days: number[];
  max_active_keys: number;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
  is_expired: boolean;
}

export interface CreateKeyRequest {
  name: string;
  scopes: string[];
  expires_in_days: number;
}

export interface CreateKeyResponse {
  id: string;
  key: string; // plaintext — shown ONCE
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  warning: string;
}

export interface MintError {
  status: number;
  reason_code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ============================================================================
// Service
// ============================================================================

export const ApiKeysService = {
  /** Returns the scope catalogue used to populate the mint UI. Public — no auth. */
  async getScopeCatalogue(): Promise<ScopeCatalogue> {
    const res = await axios.get<ScopeCatalogue>(`${API_BASE}/scopes`);
    return res.data;
  },

  /** Mint a new key for the current user. Returns plaintext ONCE. */
  async createKey(payload: CreateKeyRequest): Promise<CreateKeyResponse> {
    try {
      const res = await axios.post<CreateKeyResponse>(API_BASE, payload, {
        headers: authHeaders(),
      });
      return res.data;
    } catch (err) {
      throw normaliseError(err);
    }
  },

  /** List the current user's keys. Plaintext never returned. */
  async listMyKeys(): Promise<ApiKeySummary[]> {
    const res = await axios.get<ApiKeySummary[]>(API_BASE, { headers: authHeaders() });
    return res.data;
  },

  /** Revoke a key. Idempotent — 204 even if already revoked. */
  async revokeKey(keyId: string): Promise<void> {
    await axios.delete(`${API_BASE}/${keyId}`, { headers: authHeaders() });
  },
};

// ============================================================================
// Error normalisation
// ============================================================================

function normaliseError(err: unknown): MintError {
  if (axios.isAxiosError(err) && err.response) {
    const status = err.response.status;
    const data = err.response.data;
    // FastAPI returns either {detail: {error, reason_code, ...}} or
    // {detail: [...]} for Pydantic validation errors.
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail;
      if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const d = detail as Record<string, unknown>;
        return {
          status,
          reason_code: String(d.reason_code ?? 'unknown'),
          message: String(d.error ?? 'Request failed'),
          details: d,
        };
      }
      if (Array.isArray(detail)) {
        // Pydantic validation — surface first error
        const first = detail[0] as { msg?: string; loc?: string[] } | undefined;
        return {
          status,
          reason_code: 'validation_error',
          message: first?.msg ?? 'Invalid input',
          details: { loc: first?.loc, errors: detail },
        };
      }
    }
    return { status, reason_code: 'unknown', message: 'Request failed' };
  }
  return { status: 0, reason_code: 'network_error', message: 'Network error' };
}
