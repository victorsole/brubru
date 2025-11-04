// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Header } from './components/shared/header';
import { Footer } from './components/shared/footer';
import { MainPage } from './pages/main_page';
import { AmendatorPage } from './pages/amendator_page';
import './styles/globals.css';

export const App = () => {
  return (
    <BrowserRouter>
      <div className="app">
        <Header />
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route path="/amendator" element={<AmendatorPage />} />
        </Routes>
        <Footer />
      </div>
    </BrowserRouter>
  );
};
