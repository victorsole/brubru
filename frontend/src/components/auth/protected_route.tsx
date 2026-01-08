import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireTier?: 'white' | 'yellow' | 'blue';
}

export const ProtectedRoute = ({ children, requireTier }: ProtectedRouteProps) => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
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
