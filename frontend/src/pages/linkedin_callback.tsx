import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const LinkedInCallback = () => {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState('');

  useEffect(() => {
    const handleLinkedInCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const storedState = sessionStorage.getItem('linkedin_oauth_state');

      // Verify state to prevent CSRF
      if (!state || state !== storedState) {
        setError('Invalid state parameter');
        setTimeout(() => window.close(), 3000);
        return;
      }

      if (!code) {
        setError('No authorization code received');
        setTimeout(() => window.close(), 3000);
        return;
      }

      try {
        // Forward the claim token if this OAuth was started from /claim/:token
        const claimToken = sessionStorage.getItem('brubru_claim_token');
        const payload: Record<string, string> = {
          code,
          redirect_uri: `${window.location.origin}/auth/linkedin/callback`,
        };
        if (claimToken) {
          payload.claim_token = claimToken;
          sessionStorage.removeItem('brubru_claim_token');
        }

        // Send code to backend for token exchange
        const response = await axios.post(`${API_URL}/api/auth/linkedin/callback`, payload);

        const { access_token, user, previous_last_login } = response.data;

        // Store auth in parent window
        if (window.opener) {
          window.opener.postMessage({
            type: 'LINKEDIN_AUTH_SUCCESS',
            token: access_token,
            user,
            previous_last_login
          }, window.location.origin);
        }

        // Close popup
        window.close();
      } catch (err: any) {
        setError(err.response?.data?.detail || 'LinkedIn authentication failed');
        setTimeout(() => window.close(), 3000);
      }
    };

    handleLinkedInCallback();
  }, [searchParams]);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      flexDirection: 'column',
      fontFamily: 'sans-serif'
    }}>
      {error ? (
        <>
          <h2>❌ Authentication Failed</h2>
          <p>{error}</p>
          <p>This window will close automatically...</p>
        </>
      ) : (
        <>
          <h2>🔐 Authenticating with LinkedIn...</h2>
          <p>Please wait...</p>
        </>
      )}
    </div>
  );
};
