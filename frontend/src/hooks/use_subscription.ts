import { create } from 'zustand';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UsageStats {
  amendments_used: number;
  amendments_limit: number;
  saved_searches_used: number;
  saved_searches_limit: number;
  api_calls_used: number;
  api_calls_limit: number;
  current_tier: string;
  subscription_expires_at: string | null;
  can_upgrade: boolean;
}

interface SubscriptionTier {
  id: string;
  name: string;
  price_monthly: number;
  price_annual: number | null;
  description: string;
  features: string[];
  limits: any;
  custom_pricing?: boolean;
  minimum_users?: number;
}

interface SubscriptionState {
  usage: UsageStats | null;
  tiers: SubscriptionTier[] | null;
  fetchUsage: () => Promise<void>;
  fetchTiers: () => Promise<void>;
  upgrade: (tier: string, billingPeriod: 'monthly' | 'annual') => Promise<void>;
  checkFeatureAccess: (feature: string) => Promise<boolean>;
  createCheckoutSession: (tier: string, billingPeriod: 'monthly' | 'annual') => Promise<string>;
  createPortalSession: () => Promise<string>;
}

export const useSubscription = create<SubscriptionState>((set, get) => ({
  usage: null,
  tiers: null,

  fetchUsage: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/subscriptions/usage`);
      set({ usage: response.data });
    } catch (err) {
      console.error('Failed to fetch usage', err);
    }
  },

  fetchTiers: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/subscriptions/tiers`);
      set({ tiers: response.data });
    } catch (err) {
      console.error('Failed to fetch tiers', err);
    }
  },

  upgrade: async (tier: string, billingPeriod: 'monthly' | 'annual') => {
    try {
      await axios.post(`${API_URL}/api/subscriptions/upgrade`, {
        tier,
        billing_period: billingPeriod
      });
      // Refresh usage after upgrade
      await get().fetchUsage();
    } catch (err) {
      console.error('Failed to upgrade', err);
      throw err;
    }
  },

  checkFeatureAccess: async (feature: string): Promise<boolean> => {
    try {
      const response = await axios.get(`${API_URL}/api/subscriptions/features`, {
        params: { feature }
      });
      return response.data.has_access;
    } catch (err) {
      console.error('Failed to check feature access', err);
      return false;
    }
  },

  // Stripe Payment Methods
  createCheckoutSession: async (tier: string, billingPeriod: 'monthly' | 'annual'): Promise<string> => {
    try {
      const response = await axios.post(`${API_URL}/api/stripe/create-checkout-session`, {
        tier,
        billing_period: billingPeriod
      });

      // Redirect to Stripe Checkout
      window.location.href = response.data.checkout_url;
      return response.data.checkout_url;
    } catch (err: any) {
      console.error('Failed to create checkout session', err);
      throw err;
    }
  },

  createPortalSession: async (): Promise<string> => {
    try {
      const response = await axios.post(`${API_URL}/api/stripe/create-portal-session`);

      // Redirect to Stripe Customer Portal
      window.location.href = response.data.portal_url;
      return response.data.portal_url;
    } catch (err: any) {
      console.error('Failed to create portal session', err);
      throw err;
    }
  }
}));
