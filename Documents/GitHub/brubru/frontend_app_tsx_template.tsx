// frontend/src/app.tsx
// Main application component with React Router

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/shared/header';
import Footer from './components/shared/footer';
import ChatPage from './pages/chat_page';
import AmendatorPage from './pages/amendator_page';
import './styles/globals.css'; // Import global styles

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        {/* Header shows on all pages with navigation */}
        <Header />

        {/* Main content area - routes switch here */}
        <main className="main-content">
          <Routes>
            {/* Chat Interface - default home page */}
            <Route path="/" element={<ChatPage />} />

            {/* Amendator - accessible from header */}
            <Route path="/amendator" element={<AmendatorPage />} />

            {/* 404 Not Found - optional */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>

        {/* Footer shows on all pages */}
        <Footer />
      </div>
    </BrowserRouter>
  );
}

// Simple 404 page component
function NotFoundPage() {
  return (
    <div className="not-found">
      <h1>404 - Page Not Found</h1>
      <p>The page you're looking for doesn't exist.</p>
      <a href="/">Go back to Chat</a>
    </div>
  );
}

export default App;
