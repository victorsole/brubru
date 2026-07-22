// frontend/src/components/tour/tour_tooltip.tsx
import { motion, useReducedMotion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import type { TooltipRenderProps } from 'react-joyride';
import Icon from '@mdi/react';
import { mdiClose, mdiArrowLeft, mdiArrowRight, mdiCheck } from '@mdi/js';
import './tour_tooltip.css';

export const TourTooltip = ({
  continuous,
  index,
  step,
  size,
  backProps,
  closeProps,
  primaryProps,
  skipProps,
  tooltipProps,
  isLastStep,
}: TooltipRenderProps) => {
  const { t } = useTranslation();
  const shouldReduceMotion = useReducedMotion();

  // tour_steps.ts stores i18n keys (titleKey/contentKey) alongside the
  // English fallback held in title/content.
  const stepWithKeys = step as typeof step & {
    titleKey?: string;
    contentKey?: string;
  };
  const stepTitle =
    stepWithKeys.titleKey && typeof step.title === 'string'
      ? t(stepWithKeys.titleKey, step.title)
      : step.title;
  const stepContent =
    stepWithKeys.contentKey && typeof step.content === 'string'
      ? t(stepWithKeys.contentKey, step.content)
      : step.content;

  const tooltipVariants = {
    initial: shouldReduceMotion
      ? { opacity: 0 }
      : { opacity: 0, scale: 0.95, y: 8 },
    animate: shouldReduceMotion
      ? { opacity: 1 }
      : {
          opacity: 1,
          scale: 1,
          y: 0,
          transition: { duration: 0.2, ease: [0.25, 0.1, 0.25, 1] },
        },
    exit: shouldReduceMotion
      ? { opacity: 0 }
      : { opacity: 0, scale: 0.95, transition: { duration: 0.15 } },
  };

  return (
    <motion.div
      className="tour-tooltip"
      {...tooltipProps}
      variants={tooltipVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-step-title"
      aria-describedby="tour-step-content"
    >
      {/* Close button */}
      <button
        className="tour-tooltip__close"
        {...closeProps}
        aria-label={t('tour.closeAria', 'Close tour')}
      >
        <Icon path={mdiClose} size={0.8} />
      </button>

      {/* Content */}
      <div className="tour-tooltip__content">
        {stepTitle && (
          <h3 id="tour-step-title" className="tour-tooltip__title">
            {stepTitle}
          </h3>
        )}
        <div id="tour-step-content" className="tour-tooltip__body">
          {stepContent}
        </div>
      </div>

      {/* Footer with progress and buttons */}
      <div className="tour-tooltip__footer">
        {/* Progress indicator */}
        <div className="tour-tooltip__progress">
          <span className="tour-tooltip__progress-text">
            {t('tour.progressOf', {
              defaultValue: '{{current}} of {{total}}',
              current: index + 1,
              total: size,
            })}
          </span>
          <div className="tour-tooltip__progress-dots">
            {Array.from({ length: size }, (_, i) => (
              <span
                key={i}
                className={`tour-tooltip__dot ${
                  i === index ? 'tour-tooltip__dot--active' : ''
                } ${i < index ? 'tour-tooltip__dot--completed' : ''}`}
              />
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="tour-tooltip__actions">
          {/* Skip button - only show if not last step */}
          {!isLastStep && (
            <button
              className="tour-tooltip__button tour-tooltip__button--skip"
              {...skipProps}
            >
              {t('tour.skip', 'Skip tour')}
            </button>
          )}

          {/* Back button - only show if not first step */}
          {index > 0 && (
            <button
              className="tour-tooltip__button tour-tooltip__button--back"
              {...backProps}
            >
              <Icon path={mdiArrowLeft} size={0.7} />
              <span>{t('tour.back', 'Back')}</span>
            </button>
          )}

          {/* Next/Finish button */}
          {continuous && (
            <button
              className="tour-tooltip__button tour-tooltip__button--primary"
              {...primaryProps}
            >
              {isLastStep ? (
                <>
                  <Icon path={mdiCheck} size={0.7} />
                  <span>{t('tour.finish', 'Finish')}</span>
                </>
              ) : (
                <>
                  <span>{t('common.next', 'Next')}</span>
                  <Icon path={mdiArrowRight} size={0.7} />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
};
