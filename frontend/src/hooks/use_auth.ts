import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface User {
  id: string;
  email: string;
  full_name: string | null;
  organization: string | null;
  role: string;
  avatar_url: string | null;
  country: string | null;
  policy_interests: string | null;
  background_preference: string | null;
  subscription_tier: string;
  subscription_expires_at: string | null;
  created_at: string;
  last_login: string | null;
  is_active: boolean;
  is_verified: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: any) => Promise<void>;
  logout: () => void;
  loginWithGoogle: (credentialResponse: any) => Promise<void>;
  loginWithLinkedIn: () => void;
  updateProfile: (data: any) => Promise<void>;
  refreshToken: () => Promise<void>;
}

// Listen for LinkedIn OAuth callback
if (typeof window !== 'undefined') {
  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin) return;

    if (event.data.type === 'LINKEDIN_AUTH_SUCCESS') {
      const { token, user } = event.data;
      useAuth.getState().token = token;
      useAuth.getState().user = user;
      useAuth.getState().isAuthenticated = true;
      useAuth.setState({ token, user, isAuthenticated: true });
    }
  });
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (email: string, password: string) => {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const response = await axios.post(`${API_URL}/api/auth/login`, formData);
        const { access_token, user } = response.data;

        set({ token: access_token, user, isAuthenticated: true });
      },

      signup: async (data: any) => {
        await axios.post(`${API_URL}/api/auth/signup`, data);

        // Auto-login after signup
        await get().login(data.email, data.password);
      },

      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
      },

      loginWithGoogle: async (credentialResponse: any) => {
        try {
          const response = await axios.post(`${API_URL}/api/auth/google`, {
            access_token: credentialResponse.credential
          });
          const { access_token, user } = response.data;
          set({ token: access_token, user, isAuthenticated: true });
        } catch (error) {
          console.error('Google login failed:', error);
          throw error;
        }
      },

      loginWithLinkedIn: async () => {
        const clientId = import.meta.env.VITE_LINKEDIN_CLIENT_ID;
        const redirectUri = `${window.location.origin}/auth/linkedin/callback`;
        const state = Math.random().toString(36).substring(7);

        // Store state for verification
        sessionStorage.setItem('linkedin_oauth_state', state);

        // Build authorization URL
        const authUrl = `https://www.linkedin.com/oauth/v2/authorization?` +
          `response_type=code&` +
          `client_id=${clientId}&` +
          `redirect_uri=${encodeURIComponent(redirectUri)}&` +
          `state=${state}&` +
          `scope=openid%20profile%20email`;

        // Open OAuth popup
        const width = 600;
        const height = 700;
        const left = window.screen.width / 2 - width / 2;
        const top = window.screen.height / 2 - height / 2;

        window.open(
          authUrl,
          'LinkedIn Login',
          `width=${width},height=${height},left=${left},top=${top}`
        );
      },

      updateProfile: async (data: any) => {
        const token = get().token;
        const response = await axios.patch(
          `${API_URL}/api/auth/me`,
          data,
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );
        set({ user: response.data });
      },

      refreshToken: async () => {
        const token = get().token;
        if (!token) return;

        try {
          const response = await axios.post(
            `${API_URL}/api/auth/refresh`,
            {},
            {
              headers: { Authorization: `Bearer ${token}` }
            }
          );
          const { access_token, user } = response.data;
          set({ token: access_token, user });
        } catch (err) {
          // Token expired, logout
          set({ user: null, token: null, isAuthenticated: false });
        }
      }
    }),
    {
      name: 'brubru-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated
      })
    }
  )
);

// Axios interceptor to add auth token
axios.interceptors.request.use((config) => {
  const token = useAuth.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Axios interceptor to handle 401 errors
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = error.config?.url || '';

    // Don't retry auth endpoints - they handle their own errors
    const isAuthEndpoint = requestUrl.includes('/api/auth/');

    // Don't retry if we've already retried this request
    const hasRetried = error.config?._hasRetried;

    if (error.response?.status === 401 && !isAuthEndpoint && !hasRetried) {
      // Try to refresh token
      try {
        await useAuth.getState().refreshToken();
        // Mark as retried to prevent infinite loop
        error.config._hasRetried = true;
        // Retry original request
        return axios(error.config);
      } catch (refreshError) {
        // Refresh failed, logout
        useAuth.getState().logout();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
