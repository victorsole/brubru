// frontend/src/components/tour/tour_steps.ts
import type { Step } from 'react-joyride';
import type { TourKey } from '../../stores/tour_store.ts';

// Tour step definitions for each feature
// Steps should be concise (max 25 words) and target existing CSS classes

export const tourSteps: Record<TourKey, Step[]> = {
  // Welcome tour - shown on first login to main page
  welcome: [
    {
      target: '.chat-interface__input-container',
      title: 'Ask Brubru Anything',
      content:
        'Type questions about EU legislation, MEPs, policy areas, or paste documents for analysis. Brubru is available in 6 languages.',
      placement: 'top',
      disableBeacon: true,
    },
    {
      target: '.header__nav',
      title: 'Explore Brubru Tools',
      content:
        'Access specialised tools: draft amendments, check compliance, track tenders, and monitor your EU bubble.',
      placement: 'bottom',
    },
    {
      target: '.header__language',
      title: 'Choose Your Language',
      content:
        'Brubru is available in English, French, Dutch, Spanish, Catalan, and Italian. Select your preferred language.',
      placement: 'bottom',
    },
  ],

  // Chat tour - deeper dive into chat features
  chat: [
    {
      target: '.chat-interface__input',
      title: 'Your Question Here',
      content:
        'Type questions about EU policy, legislation, or institutions. Press Enter to send or Shift+Enter for a new line.',
      placement: 'top',
      disableBeacon: true,
    },
    {
      target: '.main-page__documents',
      title: 'Upload Documents',
      content:
        'Upload PDFs for compliance checking, summarisation, or analysis. Brubru will reference them in responses.',
      placement: 'right',
    },
    {
      target: '.chat-interface__examples',
      title: 'Example Questions',
      content:
        'Not sure where to start? Click any example to try it. These are curated by EU policy experts.',
      placement: 'top',
    },
  ],

  // Amendator tour
  amendator: [
    {
      target: '.amendator__document-selector',
      title: 'Select Legislative Text',
      content:
        'Choose the EU legislative document you want to amend. Search by title, CELEX number, or procedure reference.',
      placement: 'bottom',
      disableBeacon: true,
    },
    {
      target: '.amendator__editor',
      title: 'Draft Your Amendment',
      content:
        'Write amendments using standard European Parliament formatting. Changes are tracked automatically.',
      placement: 'right',
    },
    {
      target: '.amendator__ai-panel',
      title: 'AI Drafting Assistant',
      content:
        'Get AI-powered suggestions for your amendments. Brubru helps ensure legal consistency and clarity.',
      placement: 'left',
    },
    {
      target: '.amendator__export',
      title: 'Export Your Work',
      content:
        'Export amendments in Akoma Ntoso XML (official EP format) or Word for sharing with colleagues.',
      placement: 'bottom',
    },
  ],

  // EU Bubble tour
  eu_bubble: [
    {
      target: '.bubble-dashboard__feed',
      title: 'Your Personalised Feed',
      content:
        'Real-time updates from 15+ EU institutional sources including Parliament, Commission, and Council.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.bubble-dashboard__filters',
      title: 'Filter Your Feed',
      content:
        'Filter by institution, policy area, document type, or date range to find exactly what matters to you.',
      placement: 'left',
    },
    {
      target: '.bubble-dashboard__analytics',
      title: 'Track Trends',
      content:
        'Monitor legislative activity patterns, voting trends, and policy developments over time.',
      placement: 'top',
    },
  ],

  // EU Comply tour
  eu_comply: [
    {
      target: '.eu-comply__law-browser',
      title: 'EU Law Database',
      content:
        'Search through EU regulations, directives, and decisions. Filter by policy area, date, or legal status.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.eu-comply__upload',
      title: 'Upload Your Document',
      content:
        'Upload your policy document, contract, or internal rules for automated compliance gap analysis.',
      placement: 'left',
    },
    {
      target: '.eu-comply__report',
      title: 'Compliance Report',
      content:
        'View detailed gap analysis with specific article references and actionable recommendations.',
      placement: 'top',
    },
  ],

  // Tenderator tour
  tenderator: [
    {
      target: '.tenderator__filters',
      title: 'Find EU Tenders',
      content:
        'Filter tenders from TED (Tenders Electronic Daily) by sector, contract value, deadline, and location.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.tenderator__results',
      title: 'Browse Opportunities',
      content:
        'View matching tenders with key details: contracting authority, deadline, estimated value, and requirements.',
      placement: 'left',
    },
    {
      target: '.tenderator__match-score',
      title: 'AI Match Scoring',
      content:
        'Each tender shows an AI-calculated relevance score based on your profile and past interests.',
      placement: 'top',
    },
  ],
};
