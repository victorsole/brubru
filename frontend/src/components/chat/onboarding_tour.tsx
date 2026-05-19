// frontend/src/components/chat/onboarding_tour.tsx
//
// Pre-user intro overlay. Three turns of conversation instead of three
// static slides. Brubru asks instead of lectures. Skip is always free.
//
// Q1: which policy area matters most right now? (chip choice)
// Q2: anything specific you watch? (free-text alias, OEIL or CELEX)
// Q3: want me to keep an eye on it? (sign up CTA)
//
// Each answered turn fires a pre-user event so the empty state and future
// hooks can lean on what we just learned.

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { trackPreUserEvent } from '../../services/preuser_tracker';
import './onboarding_tour.css';

const TOUR_STORAGE_KEY = 'brubru_tour_completed';
const PRE_USER_ID_KEY = 'brubru_preuser_id';

interface OnboardingTourProps {
  /** Only show for pre-users (not authenticated) */
  isAuthenticated: boolean;
}

const POLICY_CHIPS: Array<{ slug: string; label: string }> = [
  { slug: 'ai_digital', label: 'AI and Digital' },
  { slug: 'climate_energy', label: 'Climate and Energy' },
  { slug: 'finance', label: 'Finance' },
  { slug: 'health', label: 'Health' },
  { slug: 'trade', label: 'Trade' },
  { slug: 'agri_fisheries', label: 'Agriculture and Fisheries' },
];

const getPreUserId = (): string => {
  let id = localStorage.getItem(PRE_USER_ID_KEY);
  if (!id) {
    id = (window.crypto?.randomUUID?.() as string) || `${Date.now()}-${Math.random()}`;
    localStorage.setItem(PRE_USER_ID_KEY, id);
  }
  return id;
};

export const OnboardingTour = ({ isAuthenticated }: OnboardingTourProps) => {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const [watchedItem, setWatchedItem] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) return;
    const completed = localStorage.getItem(TOUR_STORAGE_KEY);
    if (completed) return;
    const timer = setTimeout(() => setVisible(true), 800);
    return () => clearTimeout(timer);
  }, [isAuthenticated]);

  const close = () => {
    setVisible(false);
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');
  };

  const goSignup = () => {
    close();
    navigate('/signup');
  };

  const pickPolicyArea = (slug: string, label: string) => {
    trackPreUserEvent(getPreUserId(), 'onboarding_interest_chosen', {
      slug,
      label,
    });
    setStep(1);
  };

  const submitWatchedItem = () => {
    const trimmed = watchedItem.trim();
    if (trimmed) {
      trackPreUserEvent(getPreUserId(), 'onboarding_watched_item', {
        text: trimmed,
      });
    }
    setStep(2);
  };

  const skipWatchedItem = () => {
    trackPreUserEvent(getPreUserId(), 'onboarding_watched_skipped');
    setStep(2);
  };

  if (!visible) return null;

  return createPortal(
    <div className="onboarding-tour__overlay" onClick={close}>
      <div className="onboarding-tour__card" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="onboarding-tour__close"
          onClick={close}
          aria-label="Close"
        >
          <span className="mdi mdi-close" />
        </button>

        <div className="onboarding-tour__steps">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`onboarding-tour__dot ${i === step ? 'onboarding-tour__dot--active' : ''} ${i < step ? 'onboarding-tour__dot--done' : ''}`}
            />
          ))}
        </div>

        <div className="onboarding-tour__content">
          {step === 0 && (
            <>
              <span className="mdi mdi-hand-wave-outline onboarding-tour__icon" />
              <h3>What is on your mind right now?</h3>
              <p>Pick the policy area you care about today. I will tailor what I show you next.</p>
              <div className="onboarding-tour__chips">
                {POLICY_CHIPS.map((chip) => (
                  <button
                    key={chip.slug}
                    type="button"
                    className="onboarding-tour__chip"
                    onClick={() => pickPolicyArea(chip.slug, chip.label)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <span className="mdi mdi-eye-outline onboarding-tour__icon" />
              <h3>Anything specific you watch?</h3>
              <p>Type a name (AI Act, CSRD, GDPR), an OEIL reference, or a CELEX. I will keep an eye on it.</p>
              <input
                type="text"
                className="onboarding-tour__input"
                placeholder="e.g. AI Act, 2024/0079(COD), 32024R1689"
                value={watchedItem}
                onChange={(e) => setWatchedItem(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitWatchedItem();
                }}
                autoFocus
              />
            </>
          )}

          {step === 2 && (
            <>
              <span className="mdi mdi-rocket-launch-outline onboarding-tour__icon" />
              <h3>Want me to keep an eye on it?</h3>
              <p>Sign up free and I will track legislation for you, flag changes, and draft amendments and position papers when you need them. No credit card.</p>
            </>
          )}
        </div>

        <div className="onboarding-tour__actions">
          {step === 0 && (
            <button
              type="button"
              className="onboarding-tour__btn onboarding-tour__btn--skip"
              onClick={close}
            >
              Skip for now
            </button>
          )}

          {step === 1 && (
            <>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--skip"
                onClick={skipWatchedItem}
              >
                Skip
              </button>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--primary"
                onClick={submitWatchedItem}
              >
                {watchedItem.trim() ? 'Continue' : 'No specific file yet'}
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--secondary"
                onClick={close}
              >
                Maybe later
              </button>
              <button
                type="button"
                className="onboarding-tour__btn onboarding-tour__btn--primary"
                onClick={goSignup}
              >
                Sign up free
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
};
