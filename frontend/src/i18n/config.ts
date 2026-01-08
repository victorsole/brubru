// frontend/src/i18n/config.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Supported languages (matching header selector)
export const SUPPORTED_LANGUAGES = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  it: 'Italiano',
  pt: 'Português',
  nl: 'Nederlands',
  pl: 'Polski',
  cs: 'Čeština',
  sk: 'Slovenčina',
  sl: 'Slovenščina',
  hr: 'Hrvatski',
  ro: 'Română',
  bg: 'Български',
  el: 'Ελληνικά',
  hu: 'Magyar',
  da: 'Dansk',
  sv: 'Svenska',
  fi: 'Suomi',
  et: 'Eesti',
  lv: 'Latviešu',
  lt: 'Lietuvių',
  mt: 'Malti',
  ga: 'Gaeilge',
  ca: 'Català',
} as const;

export type SupportedLanguage = keyof typeof SUPPORTED_LANGUAGES;

// English translations (source language - will be translated to others dynamically)
const enTranslations = {
  // Header
  'header.main': 'Main',
  'header.amendator': 'Amendator',
  'header.myEuBubble': 'My EU Bubble',
  'header.euLawComply': 'EU Law Comply',
  'header.tenderator': 'Tenderator',
  'header.profile': 'Profile',
  'header.adminPanel': 'Admin Panel',
  'header.viewProfile': 'View Profile',
  'header.subscription': 'Subscription',
  'header.logOut': 'Log Out',

  // Main Page
  'main.chatHistory': 'Chat History',
  'main.previousConversations': 'Previous conversations will appear here',

  // Chat Interface
  'chat.welcome': 'Welcome to Brubru',
  'chat.tagline': 'Your AI multiagent companion for navigating the EU bubble in Brussels',
  'chat.startConversation': 'Start a conversation to analyse EU legislation, strategise advocacy campaigns, or get guidance on European Parliament procedures.',
  'chat.tryAsking': 'Try asking:',
  'chat.example1': 'What\'s the status of the AI Act?',
  'chat.example2': 'Show me recent amendments on GDPR',
  'chat.example3': 'Who are the MEPs on the ENVI committee?',
  'chat.example4': 'Find legislation about carbon border adjustment',
  'chat.placeholder': 'Ask about EU legislation, procedures, or policy analysis...',
  'chat.send': 'Send',
  'chat.stream': 'Stream',
  'chat.cancel': 'Cancel',
  'chat.errorMessage': 'Sorry, I encountered an error processing your request. Please try again.',
  'chat.failedResponse': 'Failed to get response. Please try again.',

  // Document Upload
  'docs.title': 'Documents',
  'docs.noDocuments': 'No documents uploaded',
  'docs.documentsUploaded': 'Documents uploaded',
  'docs.dragDrop': 'Drag & drop files here or click to browse',
  'docs.supported': 'Supported: PDF, Word, Text, Markdown, PowerPoint, Excel, PNG, JPEG',
  'docs.maxSize': 'Max 10MB per file',
  'docs.tooLarge': 'is too large. Maximum size is 10MB.',

  // My EU Bubble
  'bubble.title': 'My EU Bubble',
  'bubble.subtitle': 'Your personalised EU policy intelligence dashboard',
  'bubble.dashboard': 'Dashboard',
  'bubble.documents': 'Documents',
  'bubble.amendments': 'Amendments',
  'bubble.analytics': 'Analytics',

  // Amendment Sidebar
  'amendments.title': 'Amendments',
  'amendments.noAmendments': 'No amendments yet',
  'amendments.createFirst': 'Create your first amendment using the editor on the right',
  'amendments.tabled': 'Tabled',
  'amendments.candidate': 'Candidate',
  'amendments.withdrawn': 'Withdrawn',
  'amendments.exporting': 'Exporting...',
  'amendments.exported': 'Exported!',
  'amendments.exportAll': 'Export All',

  // AI Assistant
  'ai.openAssistant': 'Open AI Assistant',
  'ai.assistant': 'AI',
  'ai.analyzing': 'Analyzing...',
  'ai.foundAmendment': 'I found an amendment for you!',
  'ai.selectRow': 'Select a row and I\'ll suggest an amendment',
  'ai.policyPosition': 'Your Policy Position:',
  'ai.policyPlaceholder': 'Paste your policy position or key goals here...\n\nExample: \'We want to strengthen data protection for children, ensure parental consent for under-16s, and increase transparency requirements for data processors.\'',
  'ai.uploadDocs': 'Upload Policy Documents:',
  'ai.uploadButton': 'Upload Documents',
  'ai.currentlySelected': 'Currently Selected:',
  'ai.clickRow': 'Click a row in the amendment table to select it',
  'ai.thinking': 'Thinking...',
  'ai.suggest': 'AI Suggest Amendment',
  'ai.suggestion': 'AI Suggestion:',
  'ai.type': 'Type:',
  'ai.proposedText': 'Proposed Text:',
  'ai.justification': 'Justification:',
  'ai.accept': 'Accept',
  'ai.modify': 'Modify',
  'ai.reject': 'Reject',

  // Profile Page
  'profile.title': 'Profile Settings',
  'profile.subscription': 'Subscription',
  'profile.upgrade': 'Upgrade',
  'profile.amendmentsMonth': 'Amendments this month',
  'profile.unlimited': 'unlimited',
  'profile.apiCalls': 'API calls this month',
  'profile.renewsOn': 'Subscription renews',
  'profile.personalInfo': 'Personal Information',
  'profile.email': 'Email',
  'profile.emailNote': 'Email cannot be changed',
  'profile.fullName': 'Full Name',
  'profile.organisation': 'Organisation',
  'profile.country': 'Country',
  'profile.selectCountry': 'Select country',
  'profile.saving': 'Saving...',
  'profile.saveChanges': 'Save Changes',
  'profile.saved': 'Saved',
  'profile.policyInterests': 'Policy Interests',
  'profile.policyDescription': 'Select your areas of interest. Brubru will use these preferences to personalise your experience and prioritise relevant content.',
  'profile.feedback': 'Feedback & Support',
  'profile.feedbackDescription': 'Help us improve Brubru by sharing your feedback, reporting bugs, or requesting new features. Your input is invaluable in making our platform better.',
  'profile.accountSettings': 'Account Settings',
  'profile.accountCreated': 'Account created',
  'profile.lastLogin': 'Last login',
  'profile.deleteWarning': 'Delete your account and all associated data. This action cannot be undone.',
  'profile.deleteAccount': 'Delete Account',

  // Subscription Page
  'subscription.hero.title': 'Choose Your Brubru Plan',
  'subscription.hero.subtitle': 'Powerful EU policy intelligence for every professional',
  'subscription.hero.description': 'Whether you\'re an advocacy professional, MEP assistant, or policy expert, we have a plan that fits your needs.',

  // Tier names and pricing
  'subscription.white.name': 'Basic',
  'subscription.white.price': '€0',
  'subscription.white.period': '/month',
  'subscription.white.description': 'Essential tools to get started with EU policy monitoring',
  'subscription.white.button': 'Get Started',

  'subscription.yellow.name': 'Professional',
  'subscription.yellow.price': '€79',
  'subscription.yellow.period': '/month',
  'subscription.yellow.annualPrice': 'or €790/year',
  'subscription.yellow.annualSavings': '(save €158)',
  'subscription.yellow.description': 'Advanced AI and unlimited amendments for professional advocates',
  'subscription.yellow.button': 'Upgrade to Professional',
  'subscription.yellow.popular': 'Most Popular',

  'subscription.blue.name': 'Enterprise',
  'subscription.blue.price': 'Custom pricing',
  'subscription.blue.period': '',
  'subscription.blue.description': 'Tailored solutions for teams and organisations with custom requirements',
  'subscription.blue.button': 'Contact Us',
  'subscription.blue.contactEmail': 'helloberesol@gmail.com',
  'subscription.blue.minUsers': '5+ users',

  // Features
  'subscription.features.title': 'Feature Comparison',
  'subscription.features.subtitle': 'See what\'s included in each plan',

  // White tier features
  'subscription.features.white.chat': 'Basic AI chat',
  'subscription.features.white.amendments': '5 amendments per month',
  'subscription.features.white.searches': '5 saved searches',
  'subscription.features.white.support': 'Community support',
  'subscription.features.white.exports': 'Basic exports (XML, HTML)',
  'subscription.features.white.watermark': 'Brubru watermark on exports',

  // Yellow tier features
  'subscription.features.yellow.chat': 'Advanced AI chat',
  'subscription.features.yellow.amendments': 'Unlimited amendments',
  'subscription.features.yellow.searches': 'Unlimited saved searches',
  'subscription.features.yellow.support': 'Email support (48h response)',
  'subscription.features.yellow.exports': 'All export formats (PDF, Word, XML, HTML)',
  'subscription.features.yellow.watermark': 'No watermark',
  'subscription.features.yellow.priority': 'Priority response times',
  'subscription.features.yellow.rss': 'RSS feed alerts',
  'subscription.features.yellow.personalization': 'Personalised greeting',

  // Blue tier features
  'subscription.features.blue.everything': 'Everything in Professional, plus:',
  'subscription.features.blue.multiUser': 'Multi-user team accounts',
  'subscription.features.blue.support': 'Dedicated support (24h response)',
  'subscription.features.blue.customDomain': 'Custom domain specialisation',
  'subscription.features.blue.whiteLabel': 'White-label options',
  'subscription.features.blue.sla': 'Service Level Agreement (SLA)',
  'subscription.features.blue.training': 'Onboarding & training',
  'subscription.features.blue.api': 'API access',
  'subscription.features.blue.preferences': 'Advanced user preferences',

  // FAQ Section
  'subscription.faq.title': 'Frequently Asked Questions',
  'subscription.faq.q1': 'What payment methods do you accept?',
  'subscription.faq.a1': 'We accept all major credit cards, debit cards, and bank transfers through Stripe. Enterprise clients can arrange invoicing.',
  'subscription.faq.q2': 'Can I change my plan later?',
  'subscription.faq.a2': 'Yes, you can upgrade your plan at any time. Downgrades take effect at the end of your current billing cycle.',
  'subscription.faq.q3': 'What is your refund policy?',
  'subscription.faq.a3': 'We offer a 14-day money-back guarantee for annual plans. Monthly plans can be cancelled at any time.',
  'subscription.faq.q4': 'Do you offer a free trial?',
  'subscription.faq.a4': 'Our Basic tier is free forever with 5 amendments per month. You can try Professional features with a 14-day trial.',
  'subscription.faq.q5': 'How does Enterprise pricing work?',
  'subscription.faq.a5': 'Enterprise pricing is customised based on team size, feature requirements, and usage volume. Contact us for a tailored quote.',
  'subscription.faq.q6': 'What happens if I exceed my amendment limit?',
  'subscription.faq.a6': 'Basic tier users are limited to 5 amendments per month. To create more, upgrade to Professional for unlimited amendments.',

  // Social Proof
  'subscription.trust.title': 'Trusted by policy professionals across Europe',
  'subscription.trust.subtitle': 'Join organisations already using Brubru',

  // CTA Section
  'subscription.cta.title': 'Ready to get started?',
  'subscription.cta.subtitle': 'Join policy professionals using Brubru to navigate the EU landscape',
  'subscription.cta.button': 'Start Free',
  'subscription.cta.contact': 'Or contact us for Enterprise',

  // EU Law Comply
  'euLawComply.history': 'Analysis History',
  'euLawComply.completed': 'Completed',
  'euLawComply.processing': 'Processing',
  'euLawComply.failed': 'Failed',
  'euLawComply.loadingHistory': 'Loading history...',
  'euLawComply.retry': 'Retry',
  'euLawComply.noAnalyses': 'No compliance analyses yet',
  'euLawComply.runFirstAnalysis': 'Run your first compliance analysis to get started',
  'euLawComply.refresh': 'Refresh',
  'euLawComply.refreshing': 'Refreshing...',

  // Common
  'common.loading': 'Loading...',
  'common.error': 'Error',
  'common.success': 'Success',
  'common.save': 'Save',
  'common.cancel': 'Cancel',
  'common.delete': 'Delete',
  'common.edit': 'Edit',
  'common.search': 'Search',
  'common.filter': 'Filter',
  'common.close': 'Close',
  'common.open': 'Open',
};

// Initialize i18next
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: enTranslations,
      },
    },
    fallbackLng: 'en',
    supportedLngs: Object.keys(SUPPORTED_LANGUAGES),

    // Language detection - only from localStorage, not from browser
    detection: {
      order: ['localStorage'], // Removed 'navigator' to prevent browser language auto-detection
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },

    interpolation: {
      escapeValue: false, // React already escapes
    },

    // Load translations on demand
    load: 'languageOnly', // 'en' instead of 'en-US'

    react: {
      useSuspense: false,
      bindI18n: 'languageChanged loaded',
      bindI18nStore: 'added removed',
      transEmptyNodeValue: '',
      transSupportBasicHtmlNodes: true,
      transKeepBasicHtmlNodesFor: ['br', 'strong', 'i', 'p'],
    },
  });

export default i18n;
