// frontend/src/components/chat/onboarding_tour.tsx
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import './onboarding_tour.css';

const TOUR_STORAGE_KEY = 'brubru_tour_completed';

interface OnboardingTourProps {
  /** Only show for pre-users (not authenticated) */
  isAuthenticated: boolean;
}

const STEPS = [
  {
    title: 'Your AI partner for EU affairs',
    description: 'Ask me anything about EU policy, legislation, committees, or institutional processes. I am trained daily on EU institutional data and improve with every query.',
    icon: 'mdi-chat-processing-outline',
  },
  {
    title: 'Help me improve',
    description: 'After each answer, use the feedback buttons to tell me if my response was helpful. Your feedback directly shapes what I learn next -- every click makes Brubru smarter.',
    icon: 'mdi-star-shooting-outline',
  },
  {
    title: 'There is more to discover',
    description: 'Sign up for free to unlock legislative tracking, amendment drafting, document generation, compliance checks, and more. No credit card required.',
    icon: 'mdi-rocket-launch-outline',
    cta: { label: 'Sign up free', route: '/signup' },
  },
];

export const OnboardingTour = ({ isAuthenticated }: OnboardingTourProps) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Only show for pre-users who haven't completed the tour
    if (isAuthenticated) return;
    const completed = localStorage.getItem(TOUR_STORAGE_KEY);
    if (completed) return;

    // Small delay so the page renders first
    const timer = setTimeout(() => setVisible(true), 800);
    return () => clearTimeout(timer);
  }, [isAuthenticated]);

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleClose();
    }
  };

  const handleClose = () => {
    setVisible(false);
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');
  };

  const handleCTA = (route: string) => {
    handleClose();
    navigate(route);
  };

  if (!visible) return null;

  const step = STEPS[currentStep];
  const isLast = currentStep === STEPS.length - 1;

  return createPortal(
    <div className="onboarding-tour__overlay" onClick={handleClose}>
      <div className="onboarding-tour__card" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button
          type="button"
          className="onboarding-tour__close"
          onClick={handleClose}
          aria-label="Close tour"
        >
          <span className="mdi mdi-close" />
        </button>

        {/* Step indicator */}
        <div className="onboarding-tour__steps">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`onboarding-tour__dot ${i === currentStep ? 'onboarding-tour__dot--active' : ''} ${i < currentStep ? 'onboarding-tour__dot--done' : ''}`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="onboarding-tour__content">
          <span className={`mdi ${step.icon} onboarding-tour__icon`} />
          <h3>{step.title}</h3>
          <p>{step.description}</p>
        </div>

        {/* Actions */}
        <div className="onboarding-tour__actions">
          {step.cta ? (
            <>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--secondary"
                onClick={handleClose}
              >
                Maybe later
              </button>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--primary"
                onClick={() => handleCTA(step.cta!.route)}
              >
                {step.cta.label}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--skip"
                onClick={handleClose}
              >
                Skip
              </button>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--primary"
                onClick={handleNext}
              >
                {isLast ? 'Get started' : 'Next'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};
