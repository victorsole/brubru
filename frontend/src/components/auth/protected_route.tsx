import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import { FeaturePreviewPage } from '../../pages/feature_preview_page';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireTier?: 'white' | 'yellow' | 'blue';
  showPreview?: boolean; // If true, show feature preview; if false, redirect to login
}

export const ProtectedRoute = ({ children, requireTier, showPreview = true }: ProtectedRouteProps) => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    // Show feature preview page for main features, redirect to login for account pages
    if (showPreview) {
      return <FeaturePreviewPage />;
    }
    return <Navigate to="/login" replace />;
  }

  // Check tier if required
  if (requireTier) {
    const tierOrder = ['white', 'yellow', 'blue'];
    const userTierIndex = tierOrder.indexOf(user?.subscription_tier || 'white');
    const requiredTierIndex = tierOrder.indexOf(requireTier);

    if (userTierIndex < requiredTierIndex) {
      return <Navigate to="/pricing" replace />;
    }
  }

  return <>{children}</>;
};
