import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';
import './auth_pages.css';

const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

export const SignupPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signup, loginWithGoogle, loginWithLinkedIn } = useAuth();

  const preselectedTier = searchParams.get('tier') || 'white';

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    organization: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (!/\d/.test(formData.password)) {
      setError('Password must contain at least one digit');
      return;
    }

    if (!/[A-Z]/.test(formData.password)) {
      setError('Password must contain at least one uppercase letter');
      return;
    }

    setLoading(true);

    try {
      await signup({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        organization: formData.organization
      });

      // Link pre-user chats to the new account
      const preUserId = localStorage.getItem('brubru_preuser_id');
      if (preUserId) {
        try {
          await axios.post(`${API_BASE_URL}/api/auth/link-preuser`, { pre_user_id: preUserId });
        } catch { /* non-critical */ }
        localStorage.removeItem('brubru_preuser_id');
        localStorage.removeItem('brubru_preuser_queries');
      }

      // Redirect based on tier
      if (preselectedTier === 'yellow') {
        navigate('/checkout?tier=yellow');
      } else {
        navigate('/main');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse: any) => {
    setLoading(true);
    setError('');
    try {
      await loginWithGoogle(credentialResponse);

      // Link pre-user chats to the new account
      const preUserId = localStorage.getItem('brubru_preuser_id');
      if (preUserId) {
        try {
          await axios.post(`${API_BASE_URL}/api/auth/link-preuser`, { pre_user_id: preUserId });
        } catch { /* non-critical */ }
        localStorage.removeItem('brubru_preuser_id');
        localStorage.removeItem('brubru_preuser_queries');
      }

      if (preselectedTier === 'yellow') {
        navigate('/checkout?tier=yellow');
      } else {
        navigate('/main');
      }
    } catch (err: any) {
      setError('Google signup failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google signup failed');
  };

  const handleLinkedInLogin = () => {
    loginWithLinkedIn();
  };

  return (
    <div className="auth-page">
      <video
        className="auth-page__video"
        autoPlay
        loop
        muted
        playsInline
      >
        <source src="/assets/eu_flag.mp4" type="video/mp4" />
      </video>
      <div className="auth-page__overlay"></div>
      <div className="auth-page__container">
        <div className="auth-page__header">
          <img src="/assets/brubru_mainlogo.png" alt="Brubru" className="auth-page__logo" />
          <h1>Create Your Account</h1>
          <p>
            {preselectedTier === 'yellow'
              ? 'Start your 14-day free trial'
              : 'Create your account to get started'}
          </p>
        </div>

        {error && (
          <div className="auth-page__error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-page__form">
          <div className="auth-page__field">
            <label htmlFor="email">Email *</label>
            <input
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              required
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div className="auth-page__field">
            <label htmlFor="full_name">Full Name</label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={formData.full_name}
              onChange={handleChange}
              autoComplete="name"
              disabled={loading}
            />
          </div>

          <div className="auth-page__field">
            <label htmlFor="organization">Organisation</label>
            <input
              id="organization"
              name="organization"
              type="text"
              value={formData.organization}
              onChange={handleChange}
              autoComplete="organization"
              disabled={loading}
            />
          </div>

          <div className="auth-page__field">
            <label htmlFor="password">Password *</label>
            <input
              id="password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              required
              autoComplete="new-password"
              disabled={loading}
            />
            <small>At least 8 characters, include uppercase and number</small>
          </div>

          <div className="auth-page__field">
            <label htmlFor="confirmPassword">Confirm Password *</label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary btn--full"
            disabled={loading}
          >
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-page__divider">
          <span>or sign up with</span>
        </div>

        <div className="auth-page__oauth">
          <div className="google-login-wrapper">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              size="large"
              text="signup_with"
            />
            <button className="btn--oauth-google-custom">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Sign up with Google
            </button>
          </div>
          <button
            onClick={handleLinkedInLogin}
            className="btn btn--oauth btn--oauth-linkedin"
            disabled={loading}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Sign up with LinkedIn
          </button>
        </div>

        <div className="auth-page__footer">
          <p>
            Already have an account? <Link to="/login">Log in</Link>
          </p>
          <p className="auth-page__terms">
            By signing up, you agree to our{' '}
            <a href="/terms" target="_blank">Terms of Service</a> and{' '}
            <a href="/privacy" target="_blank">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  );
};
