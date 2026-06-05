/**
 * Billing Service
 *
 * Typed client for /api/billing/* (balance, top-up via Stripe Checkout,
 * auto-top-up settings).
 *
 * Backend: backend/api/billing.py
 */

import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/billing`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ============================================================================
// Types — must mirror backend Pydantic schemas in api/billing.py
// ============================================================================

export interface UsageRow {
  id: number;
  endpoint: string;
  method: string;
  cost_eur: number;
  status_code: number | null;
  refunded: boolean;
  is_sandbox: boolean;
  created_at: string;
}

export interface TopupRow {
  id: string;
  amount_eur: number;
  status: 'pending' | 'succeeded' | 'failed' | 'refunded';
  created_at: string;
  succeeded_at: string | null;
}

export interface AutoTopupConfig {
  enabled: boolean;
  threshold_eur: number | null;
  amount_eur: number | null;
}

export interface BalanceResponse {
  balance_eur: number;
  balance_eur_micro: number;
  auto_topup: AutoTopupConfig;
  recent_usage: UsageRow[];
  recent_topups: TopupRow[];
}

export interface TopupResponse {
  session_id: string;
  checkout_url: string;
  amount_eur: number;
}

export interface BillingError {
  status: number;
  reason_code: string;
  message: string;
}

// ============================================================================
// Service
// ============================================================================

export const BillingService = {
  async getBalance(): Promise<BalanceResponse> {
    const res = await axios.get<BalanceResponse>(`${API_BASE}/balance`, {
      headers: authHeaders(),
    });
    return res.data;
  },

  async createTopup(amountEur: number): Promise<TopupResponse> {
    try {
      const res = await axios.post<TopupResponse>(
        `${API_BASE}/topup`,
        { amount_eur: amountEur },
        { headers: authHeaders() },
      );
      return res.data;
    } catch (err) {
      throw normaliseError(err);
    }
  },

  async setAutoTopup(config: AutoTopupConfig): Promise<AutoTopupConfig> {
    try {
      const res = await axios.post<AutoTopupConfig>(
        `${API_BASE}/auto-topup`,
        config,
        { headers: authHeaders() },
      );
      return res.data;
    } catch (err) {
      throw normaliseError(err);
    }
  },
};

function normaliseError(err: unknown): BillingError {
  if (axios.isAxiosError(err) && err.response) {
    const status = err.response.status;
    const data = err.response.data;
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail;
      if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const d = detail as Record<string, unknown>;
        return {
          status,
          reason_code: String(d.reason_code ?? 'unknown'),
          message: String(d.error ?? 'Request failed'),
        };
      }
    }
    return { status, reason_code: 'unknown', message: 'Request failed' };
  }
  return { status: 0, reason_code: 'network_error', message: 'Network error' };
}
