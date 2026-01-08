// frontend/src/components/admin/shared/admin_stats_card.tsx
import './admin_stats_card.css';

interface AdminStatsCardProps {
  icon: string; // mdi icon class name (e.g., "account-group")
  title: string;
  value: string | number;
  subtitle?: string;
  variant?: 'default' | 'success' | 'warning' | 'error';
  onClick?: () => void;
}

export const AdminStatsCard = ({
  icon,
  title,
  value,
  subtitle,
  variant = 'default',
  onClick
}: AdminStatsCardProps) => {
  return (
    <div
      className={`admin-stats-card admin-stats-card--${variant} ${onClick ? 'admin-stats-card--clickable' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="admin-stats-card__icon">
        <span className={`mdi mdi-${icon}`}></span>
      </div>
      <div className="admin-stats-card__content">
        <h3 className="admin-stats-card__title">{title}</h3>
        <p className="admin-stats-card__value">{value}</p>
        {subtitle && (
          <span className="admin-stats-card__subtitle">{subtitle}</span>
        )}
      </div>
    </div>
  );
};
