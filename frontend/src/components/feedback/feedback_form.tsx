// frontend/src/components/feedback/feedback_form.tsx
import { useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './feedback_form.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface FeedbackFormProps {
  onSuccess?: () => void;
}

export const FeedbackForm = ({ onSuccess }: FeedbackFormProps) => {
  const { token } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    feedback_type: 'general',
    title: '',
    description: '',
    category: '',
    affected_feature: '',
    screenshot_url: ''
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Collect browser and device info
      const browserInfo = {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        }
      };

      const deviceInfo = {
        screen: {
          width: window.screen.width,
          height: window.screen.height
        },
        colorDepth: window.screen.colorDepth
      };

      const payload = {
        ...formData,
        browser_info: browserInfo,
        device_info: deviceInfo,
        // Only include optional fields if they have values
        category: formData.category || undefined,
        affected_feature: formData.affected_feature || undefined,
        screenshot_url: formData.screenshot_url || undefined
      };

      await axios.post(`${API_BASE_URL}/api/feedback/submit`, payload, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      setSubmitted(true);

      // Reset form
      setFormData({
        feedback_type: 'general',
        title: '',
        description: '',
        category: '',
        affected_feature: '',
        screenshot_url: ''
      });

      // Call onSuccess callback if provided
      if (onSuccess) {
        onSuccess();
      }

      // Close form after 2 seconds
      setTimeout(() => {
        setIsOpen(false);
        setSubmitted(false);
      }, 2000);
    } catch (err: any) {
      console.error('Failed to submit feedback:', err);
      setError(err.response?.data?.detail || 'Failed to submit feedback. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        className="feedback-form__trigger btn btn--secondary"
        onClick={() => setIsOpen(true)}
      >
        Submit Feedback
      </button>
    );
  }

  return (
    <div className="feedback-form">
      <div className="feedback-form__header">
        <h3>Send Feedback</h3>
        <button
          className="feedback-form__close"
          onClick={() => setIsOpen(false)}
          aria-label="Close feedback form"
        >
          ×
        </button>
      </div>

      {submitted ? (
        <div className="feedback-form__success">
          <div className="feedback-form__success-icon">✓</div>
          <h4>Thank you for your feedback!</h4>
          <p>We appreciate you taking the time to help us improve Brubru.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="feedback-form__content">
          {/* Feedback Type */}
          <div className="feedback-form__field">
            <label htmlFor="feedback_type">
              Type <span className="feedback-form__required">*</span>
            </label>
            <select
              id="feedback_type"
              name="feedback_type"
              value={formData.feedback_type}
              onChange={handleChange}
              required
              disabled={loading}
            >
              <option value="general">General Feedback</option>
              <option value="bug">Bug Report</option>
              <option value="feature_request">Feature Request</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Title */}
          <div className="feedback-form__field">
            <label htmlFor="title">
              Title <span className="feedback-form__required">*</span>
            </label>
            <input
              id="title"
              name="title"
              type="text"
              value={formData.title}
              onChange={handleChange}
              placeholder="Brief summary of your feedback"
              minLength={5}
              maxLength={200}
              required
              disabled={loading}
            />
          </div>

          {/* Description */}
          <div className="feedback-form__field">
            <label htmlFor="description">
              Description <span className="feedback-form__required">*</span>
            </label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Please provide detailed information..."
              rows={6}
              minLength={10}
              required
              disabled={loading}
            />
          </div>

          {/* Category (Optional) */}
          <div className="feedback-form__field">
            <label htmlFor="category">Category (optional)</label>
            <input
              id="category"
              name="category"
              type="text"
              value={formData.category}
              onChange={handleChange}
              placeholder="e.g., UI/UX, Performance, Security"
              disabled={loading}
            />
          </div>

          {/* Affected Feature (for bugs) */}
          {formData.feedback_type === 'bug' && (
            <div className="feedback-form__field">
              <label htmlFor="affected_feature">Affected Feature</label>
              <input
                id="affected_feature"
                name="affected_feature"
                type="text"
                value={formData.affected_feature}
                onChange={handleChange}
                placeholder="Which feature is affected?"
                disabled={loading}
              />
            </div>
          )}

          {/* Screenshot URL (Optional) */}
          <div className="feedback-form__field">
            <label htmlFor="screenshot_url">Screenshot URL (optional)</label>
            <input
              id="screenshot_url"
              name="screenshot_url"
              type="url"
              value={formData.screenshot_url}
              onChange={handleChange}
              placeholder="https://..."
              disabled={loading}
            />
            <small>Upload your screenshot to a service like Imgur and paste the URL here</small>
          </div>

          {/* Error Message */}
          {error && (
            <div className="feedback-form__error">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="feedback-form__actions">
            <button
              type="button"
              className="btn btn--secondary btn--small"
              onClick={() => setIsOpen(false)}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn--primary btn--small"
              disabled={loading}
            >
              {loading ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
