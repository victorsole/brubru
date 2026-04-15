// frontend/src/App.tsx
import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { RoutePresence, AnimatedPage } from './components/animations/page_transition';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { useAuth } from './hooks/use_auth';
import { Header } from './components/shared/header';
import { Footer } from './components/shared/footer';
import { CookieConsent } from './components/shared/cookie_consent';
import { TourProvider } from './components/tour';
import { ProtectedRoute } from './components/auth/protected_route';
import './i18n/config'; // Initialize i18n

// Pages
import { LandingPage } from './pages/landing_page';
import { LoginPage } from './pages/login_page';
import { SignupPage } from './pages/signup_page';
import { LinkedInCallback } from './pages/linkedin_callback';
import { MainPage } from './pages/main_page';
import { AmendatorPage } from './pages/amendator_page';
import { ProfilePage } from './pages/profile_page';
import { SubscriptionPage } from './pages/subscription_page';
import { MyEUBubblePage } from './pages/my_eu_bubble_page';
import { AdminPanelPage } from './pages/admin_panel_page';
import { EUComplyPage } from './pages/eu_comply_page';
import { TenderatorPage } from './pages/tenderator_page';
import { AboutPage } from './pages/about_page';
import { ApiPage } from './pages/api_page';
import { ContactPage } from './pages/contact_page';
import { PrivacyPage } from './pages/privacy_page';
import { TermsPage } from './pages/terms_page';
import { CookiesPage } from './pages/cookies_page';
import { SubprocessorsPage } from './pages/subprocessors_page';
import './styles/globals.css';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

// Only log environment variables in development mode
if (import.meta.env.DEV) {
  console.log('Environment variables loaded:');
  console.log('VITE_GOOGLE_CLIENT_ID:', import.meta.env.VITE_GOOGLE_CLIENT_ID);
  console.log('VITE_API_URL:', import.meta.env.VITE_API_URL);
  console.log('VITE_LINKEDIN_CLIENT_ID:', import.meta.env.VITE_LINKEDIN_CLIENT_ID);
}

export const App = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const { isAuthenticated } = useAuth();

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BrowserRouter>
      <TourProvider>
      <div className="app">
        <RoutePresence>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={isAuthenticated ? <Navigate to="/main" /> : (
            <AnimatedPage>
              <LandingPage />
            </AnimatedPage>
          )} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/main" /> : (
            <AnimatedPage>
              <LoginPage />
            </AnimatedPage>
          )} />
          <Route path="/signup" element={isAuthenticated ? <Navigate to="/main" /> : (
            <AnimatedPage>
              <SignupPage />
            </AnimatedPage>
          )} />
          <Route path="/auth/linkedin/callback" element={(
            <AnimatedPage>
              <LinkedInCallback />
            </AnimatedPage>
          )} />

          {/* Policy pages (public) */}
          <Route path="/about" element={(
            <>
              <Header />
              <AnimatedPage>
                <AboutPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/contact" element={(
            <>
              <Header />
              <AnimatedPage>
                <ContactPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/privacy" element={(
            <>
              <Header />
              <AnimatedPage>
                <PrivacyPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/terms" element={(
            <>
              <Header />
              <AnimatedPage>
                <TermsPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/cookies" element={(
            <>
              <Header />
              <AnimatedPage>
                <CookiesPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/api" element={(
            <>
              <Header />
              <AnimatedPage>
                <ApiPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />
          <Route path="/subprocessors" element={(
            <>
              <Header />
              <AnimatedPage>
                <SubprocessorsPage />
              </AnimatedPage>
              <Footer isSidebarOpen={isSidebarOpen} />
            </>
          )} />

          {/* Protected routes */}
          <Route
            path="/main"
            element={
              <>
                <Header />
                <AnimatedPage>
                  <MainPage isSidebarOpen={isSidebarOpen} setIsSidebarOpen={setIsSidebarOpen} />
                </AnimatedPage>
                <Footer isSidebarOpen={isSidebarOpen} />
              </>
            }
          />
          <Route
            path="/amendator"
            element={
              <ProtectedRoute>
                <>
                  <Header />
                  <AnimatedPage>
                    <AmendatorPage isSidebarOpen={isSidebarOpen} setIsSidebarOpen={setIsSidebarOpen} />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute showPreview={false}>
                <>
                  <Header />
                  <AnimatedPage>
                    <ProfilePage />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subscription"
            element={
              <ProtectedRoute showPreview={false}>
                <>
                  <Header />
                  <AnimatedPage>
                    <SubscriptionPage />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-eu-bubble"
            element={
              <ProtectedRoute>
                <>
                  <Header />
                  <AnimatedPage>
                    <MyEUBubblePage />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute showPreview={false}>
                <>
                  <Header />
                  <AnimatedPage>
                    <AdminPanelPage />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/eulawcomply"
            element={
              <ProtectedRoute>
                <>
                  <Header />
                  <AnimatedPage>
                    <EUComplyPage isSidebarOpen={isSidebarOpen} setIsSidebarOpen={setIsSidebarOpen} />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tenderator"
            element={
              <ProtectedRoute>
                <>
                  <Header />
                  <AnimatedPage>
                    <TenderatorPage isSidebarOpen={isSidebarOpen} setIsSidebarOpen={setIsSidebarOpen} />
                  </AnimatedPage>
                  <Footer isSidebarOpen={isSidebarOpen} />
                </>
              </ProtectedRoute>
            }
          />

          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        </RoutePresence>
        <CookieConsent />
      </div>
      </TourProvider>
      </BrowserRouter>
    </GoogleOAuthProvider>
  );
};
