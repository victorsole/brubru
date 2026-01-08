// frontend/src/components/tour/tour_tooltip.tsx
import { motion, useReducedMotion } from 'framer-motion';
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
  const shouldReduceMotion = useReducedMotion();

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
        aria-label="Close tour"
      >
        <Icon path={mdiClose} size={0.8} />
      </button>

      {/* Content */}
      <div className="tour-tooltip__content">
        {step.title && (
          <h3 id="tour-step-title" className="tour-tooltip__title">
            {step.title}
          </h3>
        )}
        <div id="tour-step-content" className="tour-tooltip__body">
          {step.content}
        </div>
      </div>

      {/* Footer with progress and buttons */}
      <div className="tour-tooltip__footer">
        {/* Progress indicator */}
        <div className="tour-tooltip__progress">
          <span className="tour-tooltip__progress-text">
            {index + 1} of {size}
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
              Skip tour
            </button>
          )}

          {/* Back button - only show if not first step */}
          {index > 0 && (
            <button
              className="tour-tooltip__button tour-tooltip__button--back"
              {...backProps}
            >
              <Icon path={mdiArrowLeft} size={0.7} />
              <span>Back</span>
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
                  <span>Finish</span>
                </>
              ) : (
                <>
                  <span>Next</span>
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
