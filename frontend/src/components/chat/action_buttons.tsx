// frontend/src/components/chat/action_buttons.tsx
import type { ChatAction } from './chat_interface';
import './action_buttons.css';

interface ActionButtonsProps {
  actions: ChatAction[];
  onActionClick: (action: ChatAction) => void;
  isPreUser?: boolean;
}

export const ActionButtons = ({ actions, onActionClick, isPreUser }: ActionButtonsProps) => {
  if (!actions || actions.length === 0) return null;

  return (
    <div className="action-buttons">
      <span className="action-buttons__label">Quick actions:</span>
      <div className="action-buttons__row">
        {actions.map((action, idx) => (
          <button
            key={`${action.action_type}-${idx}`}
            type="button"
            className="action-buttons__btn"
            style={{
              '--action-colour': action.colour,
            } as React.CSSProperties}
            onClick={() => onActionClick(action)}
            title={isPreUser ? action.pre_user_label || action.label : action.label}
          >
            <span className={`mdi ${action.icon}`}></span>
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
};
