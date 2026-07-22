// frontend/src/components/tour/tour_steps.ts
import type { Step } from 'react-joyride';
import type { TourKey } from '../../stores/tour_store.ts';

// Tour step definitions for each feature
// Steps should be concise (max 25 words) and target existing CSS classes
//
// i18n: each step carries titleKey/contentKey (i18next keys) alongside
// title/content, which hold the English fallback text. tour_tooltip.tsx
// translates at render time with t(titleKey, title) / t(contentKey, content).

export type TourStep = Step & {
  titleKey: string;
  contentKey: string;
};

export const tourSteps: Record<TourKey, TourStep[]> = {
  // Welcome tour - shown on first login to main page
  welcome: [
    {
      target: '.chat-interface__input-container',
      titleKey: 'tour.steps.welcome.askAnything.title',
      title: 'Ask Brubru Anything',
      contentKey: 'tour.steps.welcome.askAnything.content',
      content:
        'Type questions about EU legislation, MEPs, policy areas, or paste documents for analysis. Brubru is available in 6 languages.',
      placement: 'top',
      disableBeacon: true,
    },
    {
      target: '.header__nav',
      titleKey: 'tour.steps.welcome.exploreTools.title',
      title: 'Explore Brubru Tools',
      contentKey: 'tour.steps.welcome.exploreTools.content',
      content:
        'Access specialised tools: draft amendments, check compliance, track tenders, and monitor your EU bubble.',
      placement: 'bottom',
    },
    {
      target: '.header__language',
      titleKey: 'tour.steps.welcome.chooseLanguage.title',
      title: 'Choose Your Language',
      contentKey: 'tour.steps.welcome.chooseLanguage.content',
      content:
        'Brubru is available in English, French, Dutch, Spanish, Catalan, and Italian. Select your preferred language.',
      placement: 'bottom',
    },
  ],

  // Chat tour - deeper dive into chat features
  chat: [
    {
      target: '.chat-interface__input',
      titleKey: 'tour.steps.chat.yourQuestion.title',
      title: 'Your Question Here',
      contentKey: 'tour.steps.chat.yourQuestion.content',
      content:
        'Type questions about EU policy, legislation, or institutions. Press Enter to send or Shift+Enter for a new line.',
      placement: 'top',
      disableBeacon: true,
    },
    {
      target: '.main-page__documents',
      titleKey: 'tour.steps.chat.uploadDocuments.title',
      title: 'Upload Documents',
      contentKey: 'tour.steps.chat.uploadDocuments.content',
      content:
        'Upload PDFs for compliance checking, summarisation, or analysis. Brubru will reference them in responses.',
      placement: 'right',
    },
    {
      target: '.chat-interface__examples',
      titleKey: 'tour.steps.chat.exampleQuestions.title',
      title: 'Example Questions',
      contentKey: 'tour.steps.chat.exampleQuestions.content',
      content:
        'Not sure where to start? Click any example to try it. These are curated by EU policy experts.',
      placement: 'top',
    },
  ],

  // Amendator tour
  amendator: [
    {
      target: '.amendator__document-selector',
      titleKey: 'tour.steps.amendator.selectText.title',
      title: 'Select Legislative Text',
      contentKey: 'tour.steps.amendator.selectText.content',
      content:
        'Choose the EU legislative document you want to amend. Search by title, CELEX number, or procedure reference.',
      placement: 'bottom',
      disableBeacon: true,
    },
    {
      target: '.amendator__editor',
      titleKey: 'tour.steps.amendator.draftAmendment.title',
      title: 'Draft Your Amendment',
      contentKey: 'tour.steps.amendator.draftAmendment.content',
      content:
        'Write amendments using standard European Parliament formatting. Changes are tracked automatically.',
      placement: 'right',
    },
    {
      target: '.amendator__ai-panel',
      titleKey: 'tour.steps.amendator.aiAssistant.title',
      title: 'AI Drafting Assistant',
      contentKey: 'tour.steps.amendator.aiAssistant.content',
      content:
        'Get AI-powered suggestions for your amendments. Brubru helps ensure legal consistency and clarity.',
      placement: 'left',
    },
    {
      target: '.amendator__export',
      titleKey: 'tour.steps.amendator.export.title',
      title: 'Export Your Work',
      contentKey: 'tour.steps.amendator.export.content',
      content:
        'Export amendments in Akoma Ntoso XML (official EP format) or Word for sharing with colleagues.',
      placement: 'bottom',
    },
  ],

  // EU Bubble tour
  eu_bubble: [
    {
      target: '.bubble-dashboard__feed',
      titleKey: 'tour.steps.euBubble.personalisedFeed.title',
      title: 'Your Personalised Feed',
      contentKey: 'tour.steps.euBubble.personalisedFeed.content',
      content:
        'Real-time updates from 15+ EU institutional sources including Parliament, Commission, and Council.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.bubble-dashboard__filters',
      titleKey: 'tour.steps.euBubble.filterFeed.title',
      title: 'Filter Your Feed',
      contentKey: 'tour.steps.euBubble.filterFeed.content',
      content:
        'Filter by institution, policy area, document type, or date range to find exactly what matters to you.',
      placement: 'left',
    },
    {
      target: '.bubble-dashboard__analytics',
      titleKey: 'tour.steps.euBubble.trackTrends.title',
      title: 'Track Trends',
      contentKey: 'tour.steps.euBubble.trackTrends.content',
      content:
        'Monitor legislative activity patterns, voting trends, and policy developments over time.',
      placement: 'top',
    },
  ],

  // EU Comply tour
  eu_comply: [
    {
      target: '.eu-comply__law-browser',
      titleKey: 'tour.steps.euComply.lawDatabase.title',
      title: 'EU Law Database',
      contentKey: 'tour.steps.euComply.lawDatabase.content',
      content:
        'Search through EU regulations, directives, and decisions. Filter by policy area, date, or legal status.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.eu-comply__upload',
      titleKey: 'tour.steps.euComply.uploadDocument.title',
      title: 'Upload Your Document',
      contentKey: 'tour.steps.euComply.uploadDocument.content',
      content:
        'Upload your policy document, contract, or internal rules for automated compliance gap analysis.',
      placement: 'left',
    },
    {
      target: '.eu-comply__report',
      titleKey: 'tour.steps.euComply.complianceReport.title',
      title: 'Compliance Report',
      contentKey: 'tour.steps.euComply.complianceReport.content',
      content:
        'View detailed gap analysis with specific article references and actionable recommendations.',
      placement: 'top',
    },
  ],

  // Tenderator tour
  tenderator: [
    {
      target: '.tenderator__filters',
      titleKey: 'tour.steps.tenderator.findTenders.title',
      title: 'Find EU Tenders',
      contentKey: 'tour.steps.tenderator.findTenders.content',
      content:
        'Filter tenders from TED (Tenders Electronic Daily) by sector, contract value, deadline, and location.',
      placement: 'right',
      disableBeacon: true,
    },
    {
      target: '.tenderator__results',
      titleKey: 'tour.steps.tenderator.browseOpportunities.title',
      title: 'Browse Opportunities',
      contentKey: 'tour.steps.tenderator.browseOpportunities.content',
      content:
        'View matching tenders with key details: contracting authority, deadline, estimated value, and requirements.',
      placement: 'left',
    },
    {
      target: '.tenderator__match-score',
      titleKey: 'tour.steps.tenderator.matchScoring.title',
      title: 'AI Match Scoring',
      contentKey: 'tour.steps.tenderator.matchScoring.content',
      content:
        'Each tender shows an AI-calculated relevance score based on your profile and past interests.',
      placement: 'top',
    },
  ],
};
