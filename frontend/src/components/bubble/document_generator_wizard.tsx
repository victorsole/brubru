/**
 * Document Generator Wizard Component
 *
 * AI-powered document generation wizard for:
 * - Position Papers
 * - MEP Briefing Notes
 * - Talking Points
 *
 * Priority #3: Position Paper Generator
 */

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiFileDocumentOutline,
  mdiAccountTie,
  mdiMessageText,
  mdiScriptTextOutline,
  mdiCommentQuestionOutline,
  mdiEmailOutline,
  mdiImagePlusOutline,
  mdiCloseCircleOutline,
  mdiArrowLeft,
  mdiArrowRight,
  mdiCheck,
  mdiLoading,
  mdiContentCopy,
  mdiDownload,
  mdiFileDocumentEditOutline,
  mdiBullhornOutline,
  mdiAccountGroupOutline,
  mdiClipboardListOutline,
  mdiPresentation,
  mdiBullseyeArrow,
} from '@mdi/js';
import { marked } from 'marked';
import { useAuth } from '../../hooks/use_auth';
import './document_generator_wizard.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
type DocumentType =
  | 'position_paper'
  | 'mep_briefing'
  | 'talking_points'
  | 'resolution'
  | 'ep_question'
  | 'petition'
  | 'eu_email'
  | 'one_pager'
  | 'press_release'
  | 'stakeholder_map'
  | 'impact_assessment'
  | 'presentation'
  | 'event_poster';
type PositionStance = 'support' | 'support_with_amendments' | 'oppose' | 'neutral';
type DocumentTone = 'constructive' | 'critical' | 'technical' | 'diplomatic';
type OrganisationType = 'company' | 'industry_association' | 'ngo' | 'think_tank' | 'law_firm' | 'consultancy';

interface KeyAsk {
  summary: string;
  detail?: string;
  article_reference?: string;
}

interface GeneratedDocument {
  document_type: string;
  title: string;
  content: string;
  sections: Record<string, string>;
  word_count: number;
  document_id?: string;
}

interface DocumentGeneratorWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onDocumentGenerated: () => void;
  /** Preselect a document type when launched (e.g. from chat handoff). */
  presetDocType?: string;
  /** Prefill the topic / legislation title when launched from chat. */
  presetTopic?: string;
}

// Document type cards for selection. Title/description live in i18n; resolved at render.
const DOCUMENT_TYPES = [
  {
    id: 'position_paper' as DocumentType,
    titleKey: 'docGen.typePositionPaperTitle',
    descriptionKey: 'docGen.typePositionPaperDesc',
    icon: mdiFileDocumentOutline,
    color: '#2e7d32',
  },
  {
    id: 'mep_briefing' as DocumentType,
    titleKey: 'docGen.typeMepBriefingTitle',
    descriptionKey: 'docGen.typeMepBriefingDesc',
    icon: mdiAccountTie,
    color: '#1565c0',
  },
  {
    id: 'talking_points' as DocumentType,
    titleKey: 'docGen.typeTalkingPointsTitle',
    descriptionKey: 'docGen.typeTalkingPointsDesc',
    icon: mdiMessageText,
    color: '#7b1fa2',
  },
  {
    id: 'resolution' as DocumentType,
    titleKey: 'docGen.typeResolutionTitle',
    descriptionKey: 'docGen.typeResolutionDesc',
    icon: mdiScriptTextOutline,
    color: '#b91c1c',
  },
  {
    id: 'ep_question' as DocumentType,
    titleKey: 'docGen.typeEpQuestionTitle',
    descriptionKey: 'docGen.typeEpQuestionDesc',
    icon: mdiCommentQuestionOutline,
    color: '#0693e3',
  },
  {
    id: 'petition' as DocumentType,
    titleKey: 'docGen.typePetitionTitle',
    descriptionKey: 'docGen.typePetitionDesc',
    icon: mdiScriptTextOutline,
    color: '#d97706',
  },
  {
    id: 'eu_email' as DocumentType,
    titleKey: 'docGen.typeEuEmailTitle',
    descriptionKey: 'docGen.typeEuEmailDesc',
    icon: mdiEmailOutline,
    color: '#0d9488',
  },
  {
    id: 'one_pager' as DocumentType,
    titleKey: 'docGen.typeOnePagerTitle',
    descriptionKey: 'docGen.typeOnePagerDesc',
    icon: mdiFileDocumentEditOutline,
    color: '#16a34a',
  },
  {
    id: 'press_release' as DocumentType,
    titleKey: 'docGen.typePressReleaseTitle',
    descriptionKey: 'docGen.typePressReleaseDesc',
    icon: mdiBullhornOutline,
    color: '#ea580c',
  },
  {
    id: 'stakeholder_map' as DocumentType,
    titleKey: 'docGen.typeStakeholderMapTitle',
    descriptionKey: 'docGen.typeStakeholderMapDesc',
    icon: mdiAccountGroupOutline,
    color: '#4f46e5',
  },
  {
    id: 'impact_assessment' as DocumentType,
    titleKey: 'docGen.typeImpactAssessmentTitle',
    descriptionKey: 'docGen.typeImpactAssessmentDesc',
    icon: mdiClipboardListOutline,
    color: '#0891b2',
  },
  {
    id: 'presentation' as DocumentType,
    titleKey: 'docGen.typePresentationTitle',
    descriptionKey: 'docGen.typePresentationDesc',
    icon: mdiPresentation,
    color: '#a21caf',
  },
  {
    id: 'event_poster' as DocumentType,
    titleKey: 'docGen.typeEventPosterTitle',
    descriptionKey: 'docGen.typeEventPosterDesc',
    icon: mdiBullseyeArrow,
    color: '#db2777',
  },
];

const KIND_KEY: Record<DocumentType, string> = {
  position_paper: 'docGen.kindPositionPaper',
  mep_briefing: 'docGen.kindMepBriefing',
  talking_points: 'docGen.kindTalkingPoints',
  resolution: 'docGen.kindResolution',
  eu_email: 'docGen.kindEuEmail',
  ep_question: 'docGen.kindEpQuestion',
  petition: 'docGen.kindEpPetition',
  one_pager: 'docGen.kindOnePager',
  press_release: 'docGen.kindPressRelease',
  stakeholder_map: 'docGen.kindStakeholderMap',
  impact_assessment: 'docGen.kindImpactAssessment',
  presentation: 'docGen.kindPresentation',
  event_poster: 'docGen.kindEventPoster',
};

// ---------------------------------------------------------------------------
// Branding + style-reference sub-panels shared by the new document types
// ---------------------------------------------------------------------------

interface BrandingPanelProps {
  org: string; setOrg: (v: string) => void;
  url: string; setUrl: (v: string) => void;
  email: string; setEmail: (v: string) => void;
  phone: string; setPhone: (v: string) => void;
  transparencyId: string; setTransparencyId: (v: string) => void;
  logoStorageId: string | null; setLogoStorageId: (v: string | null) => void;
  logoFilename: string | null; setLogoFilename: (v: string | null) => void;
  logoUploading: boolean;
  logoError: string | null;
  onLogoUpload: (file: File) => void;
}

const BrandingPanel = ({
  org, setOrg, url, setUrl, email, setEmail, phone, setPhone,
  transparencyId, setTransparencyId,
  logoStorageId, setLogoStorageId, logoFilename, setLogoFilename,
  logoUploading, logoError, onLogoUpload,
}: BrandingPanelProps) => {
  const { t } = useTranslation();
  return (
  <>
    <div className="doc-generator__form-section-divider">Branding</div>
    <div className="doc-generator__form-row">
      <div className="doc-generator__form-group">
        <label>{t('docGen.wizard.organisation')}</label>
        <input type="text" value={org} onChange={(e) => setOrg(e.target.value)} />
      </div>
      <div className="doc-generator__form-group">
        <label>{t('docGen.wizard.organisationUrl')}</label>
        <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} />
      </div>
    </div>
    <div className="doc-generator__form-row">
      <div className="doc-generator__form-group">
        <label>{t('docGen.wizard.contactEmail')}</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="doc-generator__form-group">
        <label>{t('docGen.wizard.contactPhone')}</label>
        <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </div>
      <div className="doc-generator__form-group">
        <label>{t('docGen.wizard.euTransparencyId')}</label>
        <input type="text" value={transparencyId} onChange={(e) => setTransparencyId(e.target.value)} />
      </div>
    </div>
    <div className="doc-generator__form-group">
      <label>{t('docGen.wizard.organisationLogo')}</label>
      <p className="doc-generator__form-hint">{t('docGen.wizard.logoHint')}</p>
      {logoStorageId ? (
        <div className="doc-generator__logo-chip">
          <Icon path={mdiImagePlusOutline} size={0.7} />
          <span>{logoFilename || 'Logo attached'}</span>
          <button type="button" className="doc-generator__logo-remove"
            onClick={() => { setLogoStorageId(null); setLogoFilename(null); }}
            title="Remove logo">
            <Icon path={mdiCloseCircleOutline} size={0.8} />
          </button>
        </div>
      ) : (
        <label className="doc-generator__logo-upload">
          <input type="file" accept="image/png,image/jpeg,image/svg+xml"
            style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onLogoUpload(f); }} />
          <Icon path={mdiImagePlusOutline} size={0.9} />
          {logoUploading ? 'Uploading…' : 'Upload logo'}
        </label>
      )}
      {logoError && <div className="doc-generator__form-error">{logoError}</div>}
    </div>
  </>
  );
};

interface StyleRefPanelProps {
  storageId: string | null; setStorageId: (v: string | null) => void;
  filename: string | null; setFilename: (v: string | null) => void;
  uploading: boolean;
  error: string | null;
  onUpload: (file: File) => void;
  hint: string;
}

const StyleRefPanel = ({
  storageId, setStorageId, filename, setFilename,
  uploading, error, onUpload, hint,
}: StyleRefPanelProps) => {
  const { t } = useTranslation();
  return (
  <>
    <div className="doc-generator__form-section-divider">{t('docGen.wizard.styleRefSection')}</div>
    <div className="doc-generator__form-group">
      <p className="doc-generator__form-hint">{hint}</p>
      {storageId ? (
        <div className="doc-generator__logo-chip">
          <Icon path={mdiImagePlusOutline} size={0.7} />
          <span>{filename || 'Reference attached'}</span>
          <button type="button" className="doc-generator__logo-remove"
            onClick={() => { setStorageId(null); setFilename(null); }}
            title="Remove style reference">
            <Icon path={mdiCloseCircleOutline} size={0.8} />
          </button>
        </div>
      ) : (
        <label className="doc-generator__logo-upload">
          <input type="file" accept=".pdf,.docx,.pptx,.doc,application/pdf"
            style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }} />
          <Icon path={mdiImagePlusOutline} size={0.9} />
          {uploading ? 'Uploading…' : 'Upload reference'}
        </label>
      )}
      {error && <div className="doc-generator__form-error">{error}</div>}
    </div>
  </>
  );
};

export const DocumentGeneratorWizard = ({
  isOpen,
  onClose,
  onDocumentGenerated,
  presetDocType,
  presetTopic,
}: DocumentGeneratorWizardProps) => {
  const { t } = useTranslation();
  const { token, user } = useAuth();
  const userTier = user?.subscription_tier || 'white';
  const canUseResolution = userTier === 'yellow' || userTier === 'blue';

  // Wizard state
  const [step, setStep] = useState(1);
  const [selectedType, setSelectedType] = useState<DocumentType | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDocument, setGeneratedDocument] = useState<GeneratedDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Form state - Position Paper
  const [legislationTitle, setLegislationTitle] = useState('');
  const [procedureReference, setProcedureReference] = useState('');
  const [position, setPosition] = useState<PositionStance>('support_with_amendments');
  const [keyAsks, setKeyAsks] = useState<KeyAsk[]>([{ summary: '' }]);
  const [organisationName, setOrganisationName] = useState(user?.organization || '');
  const [organisationType, setOrganisationType] = useState<OrganisationType>('industry_association');
  const [tone, setTone] = useState<DocumentTone>('constructive');
  const [organisationDescription, setOrganisationDescription] = useState('');
  const [sectorImpact, setSectorImpact] = useState('');

  // Form state - MEP Briefing
  const [mepName, setMepName] = useState('');
  const [politicalGroup, setPoliticalGroup] = useState('');
  const [nationality, setNationality] = useState('');
  const [committee, setCommittee] = useState('');
  const [theAsk, setTheAsk] = useState('');
  const [keyPoints, setKeyPoints] = useState<string[]>(['']);
  const [votingRecommendation, setVotingRecommendation] = useState('');
  const [nationalAngle, setNationalAngle] = useState('');

  // Form state - Talking Points
  const [meetingWith, setMeetingWith] = useState('');
  const [meetingInstitution, setMeetingInstitution] = useState('');
  const [meetingPurpose, setMeetingPurpose] = useState('');
  const [topic, setTopic] = useState('');
  const [keyMessages, setKeyMessages] = useState<string[]>(['']);
  const [meetingKeyAsks, setMeetingKeyAsks] = useState<string[]>(['']);

  // Form state - Resolution
  const [resolutionTopic, setResolutionTopic] = useState('');
  const [contextDescription, setContextDescription] = useState('');
  const [keyDemands, setKeyDemands] = useState<string[]>(['']);
  const [additionalReferences, setAdditionalReferences] = useState<string[]>([]);

  // Form state - EP Question
  const [epqTopic, setEpqTopic] = useState('');
  const [epqAddressee, setEpqAddressee] = useState<'commission' | 'council' | 'vp_hr'>('commission');
  const [epqQuestionType, setEpqQuestionType] = useState<'standard' | 'priority'>('standard');
  const [epqContext, setEpqContext] = useState('');
  const [epqLegislationRefs, setEpqLegislationRefs] = useState<string[]>([]);
  const [epqSources, setEpqSources] = useState<string[]>([]);
  const [epqNumSubQuestions, setEpqNumSubQuestions] = useState(3);
  const [epqTone, setEpqTone] = useState<'assertive' | 'diplomatic' | 'technical'>('assertive');
  const [epqPolicyArea, setEpqPolicyArea] = useState('');

  // Form state -- EU Email / Letter
  const [emRecipientName, setEmRecipientName] = useState('');
  const [emRecipientTitle, setEmRecipientTitle] = useState('');
  const [emRecipientRole, setEmRecipientRole] = useState<
    | 'commissioner'
    | 'cabinet_member'
    | 'director_general'
    | 'director'
    | 'head_of_unit'
    | 'policy_officer'
    | 'mep'
    | 'apa'
    | 'ep_group_advisor'
    | 'ep_committee_staff'
    | 'council_attache'
    | 'permrep_counsellor'
    | 'ambassador'
    | 'other'
  >('policy_officer');
  const [emRecipientInstitution, setEmRecipientInstitution] = useState<
    | 'european_commission'
    | 'european_parliament'
    | 'council_eu'
    | 'permanent_representation'
    | 'eeas'
    | 'agency'
    | 'other'
  >('european_commission');
  const [emRecipientUnit, setEmRecipientUnit] = useState('');
  const [emPurpose, setEmPurpose] = useState<
    | 'meeting_request'
    | 'follow_up'
    | 'position_input'
    | 'invitation'
    | 'thanks'
    | 'information_request'
    | 'amendment_input'
    | 'other'
  >('meeting_request');
  const [emSubjectHint, setEmSubjectHint] = useState('');
  const [emPolicyFileRef, setEmPolicyFileRef] = useState('');
  const [emTheAsk, setEmTheAsk] = useState('');
  const [emContextNotes, setEmContextNotes] = useState('');
  const [emDeadlineOrDate, setEmDeadlineOrDate] = useState('');
  const [emTone, setEmTone] = useState<'standard' | 'warm' | 'urgent' | 'formal'>('standard');
  const [emRelationship, setEmRelationship] = useState<'cold' | 'warm' | 'established'>('cold');
  const [emLanguage, setEmLanguage] = useState<'en' | 'fr'>('en');
  const [emSenderName, setEmSenderName] = useState(user?.full_name || '');
  const [emSenderTitle, setEmSenderTitle] = useState('');
  const [emSenderOrg, setEmSenderOrg] = useState(user?.organization || '');
  const [emSenderEmail, setEmSenderEmail] = useState(user?.email || '');
  const [emSenderPhone, setEmSenderPhone] = useState('');
  const [emTransparencyRegisterId, setEmTransparencyRegisterId] = useState('');
  // Logo upload (re-uses /api/documents/upload)
  const [emLogoStorageId, setEmLogoStorageId] = useState<string | null>(null);
  const [emLogoFilename, setEmLogoFilename] = useState<string | null>(null);
  const [emLogoUploading, setEmLogoUploading] = useState(false);
  const [emLogoError, setEmLogoError] = useState<string | null>(null);

  // ====================================================================
  // Shared state for the 6 new types (one-pager, press release,
  // stakeholder map, impact assessment, presentation, event poster).
  // ====================================================================

  // Shared branding block
  const [brOrgName, setBrOrgName] = useState(user?.organization || '');
  const [brOrgUrl, setBrOrgUrl] = useState('');
  const [brContactEmail, setBrContactEmail] = useState(user?.email || '');
  const [brContactPhone, setBrContactPhone] = useState('');
  const [brTransparencyId, setBrTransparencyId] = useState('');
  const [brLogoStorageId, setBrLogoStorageId] = useState<string | null>(null);
  const [brLogoFilename, setBrLogoFilename] = useState<string | null>(null);
  const [brLogoUploading, setBrLogoUploading] = useState(false);
  const [brLogoError, setBrLogoError] = useState<string | null>(null);

  // Optional "style reference" upload (one-pager, IA, presentation, poster)
  const [styleRefStorageId, setStyleRefStorageId] = useState<string | null>(null);
  const [styleRefFilename, setStyleRefFilename] = useState<string | null>(null);
  const [styleRefUploading, setStyleRefUploading] = useState(false);
  const [styleRefError, setStyleRefError] = useState<string | null>(null);

  // One-pager
  const [opTopic, setOpTopic] = useState('');
  const [opHeadlineAsk, setOpHeadlineAsk] = useState('');
  const [opPosition, setOpPosition] = useState<PositionStance>('support_with_amendments');
  const [opKeyAsks, setOpKeyAsks] = useState<string[]>(['', '']);
  const [opSupportingEvidence, setOpSupportingEvidence] = useState('');
  const [opOrgPitch, setOpOrgPitch] = useState('');
  const [opProcedureRef, setOpProcedureRef] = useState('');
  const [opTone, setOpTone] = useState<DocumentTone>('constructive');
  const [opLanguage, setOpLanguage] = useState<'en' | 'fr'>('en');

  // Press release
  const [prInstitutionStyle, setPrInstitutionStyle] = useState<
    'commission' | 'parliament' | 'council' | 'agency'
  >('commission');
  const [prHeadline, setPrHeadline] = useState('');
  const [prSubHeadline, setPrSubHeadline] = useState('');
  const [prDatelineCity, setPrDatelineCity] = useState('Brussels');
  const [prDatelineDate, setPrDatelineDate] = useState('');
  const [prLeadParagraph, setPrLeadParagraph] = useState('');
  const [prKeyPoints, setPrKeyPoints] = useState<string[]>(['', '', '']);
  const [prQuoteText, setPrQuoteText] = useState('');
  const [prQuoteAttribution, setPrQuoteAttribution] = useState('');
  const [prBackground, setPrBackground] = useState('');
  const [prNextSteps, setPrNextSteps] = useState('');
  const [prContacts, setPrContacts] = useState('');
  const [prLanguage, setPrLanguage] = useState<'en' | 'fr'>('en');

  // Stakeholder map
  const [smPolicyTopic, setSmPolicyTopic] = useState('');
  const [smProcedureRef, setSmProcedureRef] = useState('');
  const [smScope, setSmScope] = useState<'eu' | 'national' | 'both'>('eu');
  const [smSector, setSmSector] = useState('');
  const [smObjectives, setSmObjectives] = useState('');
  const [smKnown, setSmKnown] = useState<string[]>(['']);
  const [smTargetCount, setSmTargetCount] = useState(12);
  const [smLanguage, setSmLanguage] = useState<'en' | 'fr'>('en');

  // Impact assessment
  const [iaTitle, setIaTitle] = useState('');
  const [iaPolicyArea, setIaPolicyArea] = useState('');
  const [iaProblem, setIaProblem] = useState('');
  const [iaDrivers, setIaDrivers] = useState<string[]>(['']);
  const [iaObjectivesGeneral, setIaObjectivesGeneral] = useState('');
  const [iaObjectivesSpecific, setIaObjectivesSpecific] = useState<string[]>(['']);
  const [iaBaseline, setIaBaseline] = useState('');
  const [iaOptions, setIaOptions] = useState<string[]>([
    'Option 0: Baseline (no EU action)',
    'Option 1: Soft-law guidance',
    'Option 2: Binding EU framework',
  ]);
  const [iaPreferredHint, setIaPreferredHint] = useState('');
  const [iaLanguage, setIaLanguage] = useState<'en' | 'fr'>('en');

  // Presentation
  const [presTitle, setPresTitle] = useState('');
  const [presSubtitle, setPresSubtitle] = useState('');
  const [presAudience, setPresAudience] = useState<
    | 'commission_official'
    | 'commission_cabinet'
    | 'mep_office'
    | 'ep_committee_staff'
    | 'council_attache'
    | 'permrep'
    | 'academic'
    | 'industry'
    | 'press'
    | 'general'
  >('commission_official');
  const [presAudienceLabel, setPresAudienceLabel] = useState('');
  const [presPurpose, setPresPurpose] = useState('');
  const [presKeyMessages, setPresKeyMessages] = useState<string[]>(['', '', '']);
  const [presSections, setPresSections] = useState<string[]>([
    'Context',
    'Analysis',
    'Recommendation',
    'Next steps',
  ]);
  const [presNumSlides, setPresNumSlides] = useState(10);
  const [presLanguage, setPresLanguage] = useState<'en' | 'fr'>('en');

  // Event poster
  const [evpTitle, setEvpTitle] = useState('');
  const [evpTagline, setEvpTagline] = useState('');
  const [evpDate, setEvpDate] = useState('');
  const [evpLocation, setEvpLocation] = useState('');
  const [evpEventType, setEvpEventType] = useState<
    'conference' | 'panel' | 'webinar' | 'roundtable' | 'workshop' | 'launch' | 'other'
  >('panel');
  const [evpHosts, setEvpHosts] = useState<string[]>(['']);
  const [evpSpeakers, setEvpSpeakers] = useState<string[]>(['']);
  const [evpAgenda, setEvpAgenda] = useState<string[]>(['']);
  const [evpRegistrationUrl, setEvpRegistrationUrl] = useState('');
  const [evpContactInfo, setEvpContactInfo] = useState('');
  const [evpFormat, setEvpFormat] = useState<
    'a4_portrait' | 'a4_landscape' | 'a3_portrait' | 'instagram_square' | 'linkedin_landscape'
  >('a4_portrait');
  const [evpAccentColor, setEvpAccentColor] = useState('#0066cc');
  const [evpLanguage, setEvpLanguage] = useState<'en' | 'fr'>('en');

  // Shared logo / style-reference upload helpers
  const uploadFileTo = async (
    file: File,
    onOk: (id: string, filename: string) => void,
    setUploading: (b: boolean) => void,
    setError: (e: string | null) => void,
  ) => {
    if (!token) return;
    setError(null);
    if (file.size > 10 * 1024 * 1024) {
      setError('File must be under 10 MB.');
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      onOk(data.document_id, data.filename || file.name);
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleBrLogoUpload = (file: File) =>
    uploadFileTo(
      file,
      (id, name) => {
        setBrLogoStorageId(id);
        setBrLogoFilename(name);
      },
      setBrLogoUploading,
      setBrLogoError,
    );
  const handleStyleRefUpload = (file: File) =>
    uploadFileTo(
      file,
      (id, name) => {
        setStyleRefStorageId(id);
        setStyleRefFilename(name);
      },
      setStyleRefUploading,
      setStyleRefError,
    );

  const handleLogoUpload = async (file: File) => {
    if (!token) return;
    setEmLogoError(null);
    if (file.size > 5 * 1024 * 1024) {
      setEmLogoError('Logo must be under 5 MB.');
      return;
    }
    if (!file.type.startsWith('image/')) {
      setEmLogoError('Logo must be an image (PNG, JPG, SVG).');
      return;
    }
    setEmLogoUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setEmLogoStorageId(data.document_id);
      setEmLogoFilename(data.filename || file.name);
    } catch (err) {
      console.error('Logo upload failed:', err);
      setEmLogoError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setEmLogoUploading(false);
    }
  };

  // Apply chat handoff preset (docType + topic) once when the modal opens.
  useEffect(() => {
    if (!isOpen) return;
    const valid: DocumentType[] = [
      'position_paper',
      'mep_briefing',
      'talking_points',
      'resolution',
      'ep_question',
      'eu_email',
      'one_pager',
      'press_release',
      'stakeholder_map',
      'impact_assessment',
      'presentation',
      'event_poster',
    ];
    if (presetDocType && valid.includes(presetDocType as DocumentType)) {
      const typed = presetDocType as DocumentType;
      setSelectedType(typed);
      setStep(2);
      if (presetTopic) {
        if (typed === 'position_paper' || typed === 'mep_briefing') {
          setLegislationTitle(presetTopic);
        } else if (typed === 'talking_points') {
          setTopic(presetTopic);
        } else if (typed === 'resolution') {
          setResolutionTopic(presetTopic);
        } else if (typed === 'ep_question') {
          setEpqTopic(presetTopic);
        } else if (typed === 'eu_email') {
          setEmTheAsk(presetTopic);
        } else if (typed === 'one_pager') {
          setOpTopic(presetTopic);
        } else if (typed === 'press_release') {
          setPrHeadline(presetTopic);
        } else if (typed === 'stakeholder_map') {
          setSmPolicyTopic(presetTopic);
        } else if (typed === 'impact_assessment') {
          setIaTitle(presetTopic);
        } else if (typed === 'presentation') {
          setPresTitle(presetTopic);
        } else if (typed === 'event_poster') {
          setEvpTitle(presetTopic);
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, presetDocType, presetTopic]);

  // Reset wizard
  const resetWizard = () => {
    setStep(1);
    setSelectedType(null);
    setGeneratedDocument(null);
    setError(null);
    setLegislationTitle('');
    setProcedureReference('');
    setPosition('support_with_amendments');
    setKeyAsks([{ summary: '' }]);
    setOrganisationName(user?.organization || '');
    setOrganisationType('industry_association');
    setTone('constructive');
    setOrganisationDescription('');
    setSectorImpact('');
    setMepName('');
    setPoliticalGroup('');
    setNationality('');
    setCommittee('');
    setTheAsk('');
    setKeyPoints(['']);
    setVotingRecommendation('');
    setNationalAngle('');
    setMeetingWith('');
    setMeetingInstitution('');
    setMeetingPurpose('');
    setTopic('');
    setKeyMessages(['']);
    setMeetingKeyAsks(['']);
    setResolutionTopic('');
    setContextDescription('');
    setKeyDemands(['']);
    setAdditionalReferences([]);
    setEpqTopic('');
    setEpqAddressee('commission');
    setEpqQuestionType('standard');
    setEpqContext('');
    setEpqLegislationRefs([]);
    setEpqSources([]);
    setEpqNumSubQuestions(3);
    setEpqTone('assertive');
    setEpqPolicyArea('');
    // EU Email
    setEmRecipientName('');
    setEmRecipientTitle('');
    setEmRecipientRole('policy_officer');
    setEmRecipientInstitution('european_commission');
    setEmRecipientUnit('');
    setEmPurpose('meeting_request');
    setEmSubjectHint('');
    setEmPolicyFileRef('');
    setEmTheAsk('');
    setEmContextNotes('');
    setEmDeadlineOrDate('');
    setEmTone('standard');
    setEmRelationship('cold');
    setEmLanguage('en');
    setEmSenderName(user?.full_name || '');
    setEmSenderTitle('');
    setEmSenderOrg(user?.organization || '');
    setEmSenderEmail(user?.email || '');
    setEmSenderPhone('');
    setEmTransparencyRegisterId('');
    setEmLogoStorageId(null);
    setEmLogoFilename(null);
    setEmLogoUploading(false);
    setEmLogoError(null);
    // Branding + style reference
    setBrOrgName(user?.organization || '');
    setBrOrgUrl('');
    setBrContactEmail(user?.email || '');
    setBrContactPhone('');
    setBrTransparencyId('');
    setBrLogoStorageId(null);
    setBrLogoFilename(null);
    setBrLogoUploading(false);
    setBrLogoError(null);
    setStyleRefStorageId(null);
    setStyleRefFilename(null);
    setStyleRefUploading(false);
    setStyleRefError(null);
    // One-pager
    setOpTopic(''); setOpHeadlineAsk(''); setOpPosition('support_with_amendments');
    setOpKeyAsks(['', '']); setOpSupportingEvidence(''); setOpOrgPitch('');
    setOpProcedureRef(''); setOpTone('constructive'); setOpLanguage('en');
    // Press release
    setPrInstitutionStyle('commission'); setPrHeadline(''); setPrSubHeadline('');
    setPrDatelineCity('Brussels'); setPrDatelineDate('');
    setPrLeadParagraph(''); setPrKeyPoints(['', '', '']);
    setPrQuoteText(''); setPrQuoteAttribution('');
    setPrBackground(''); setPrNextSteps(''); setPrContacts(''); setPrLanguage('en');
    // Stakeholder map
    setSmPolicyTopic(''); setSmProcedureRef(''); setSmScope('eu'); setSmSector('');
    setSmObjectives(''); setSmKnown(['']); setSmTargetCount(12); setSmLanguage('en');
    // Impact assessment
    setIaTitle(''); setIaPolicyArea(''); setIaProblem(''); setIaDrivers(['']);
    setIaObjectivesGeneral(''); setIaObjectivesSpecific(['']); setIaBaseline('');
    setIaOptions([
      'Option 0: Baseline (no EU action)',
      'Option 1: Soft-law guidance',
      'Option 2: Binding EU framework',
    ]);
    setIaPreferredHint(''); setIaLanguage('en');
    // Presentation
    setPresTitle(''); setPresSubtitle(''); setPresAudience('commission_official');
    setPresAudienceLabel(''); setPresPurpose('');
    setPresKeyMessages(['', '', '']);
    setPresSections(['Context', 'Analysis', 'Recommendation', 'Next steps']);
    setPresNumSlides(10); setPresLanguage('en');
    // Event poster
    setEvpTitle(''); setEvpTagline(''); setEvpDate(''); setEvpLocation('');
    setEvpEventType('panel'); setEvpHosts(['']); setEvpSpeakers(['']); setEvpAgenda(['']);
    setEvpRegistrationUrl(''); setEvpContactInfo('');
    setEvpFormat('a4_portrait'); setEvpAccentColor('#0066cc'); setEvpLanguage('en');
  };

  const handleClose = () => {
    resetWizard();
    onClose();
  };

  // Add/remove key asks
  const addKeyAsk = () => {
    if (keyAsks.length < 5) {
      setKeyAsks([...keyAsks, { summary: '' }]);
    }
  };

  const removeKeyAsk = (index: number) => {
    if (keyAsks.length > 1) {
      setKeyAsks(keyAsks.filter((_, i) => i !== index));
    }
  };

  const updateKeyAsk = (index: number, field: keyof KeyAsk, value: string) => {
    const updated = [...keyAsks];
    updated[index] = { ...updated[index], [field]: value };
    setKeyAsks(updated);
  };

  // Add/remove list items
  const addListItem = (list: string[], setList: (l: string[]) => void, max: number) => {
    if (list.length < max) {
      setList([...list, '']);
    }
  };

  const removeListItem = (list: string[], setList: (l: string[]) => void, index: number) => {
    if (list.length > 1) {
      setList(list.filter((_, i) => i !== index));
    }
  };

  const updateListItem = (list: string[], setList: (l: string[]) => void, index: number, value: string) => {
    const updated = [...list];
    updated[index] = value;
    setList(updated);
  };

  // Generate document
  // Pack the shared branding block for the new doc types.
  const brandingPayload = () => ({
    organisation_name: brOrgName.trim() || undefined,
    organisation_url: brOrgUrl.trim() || undefined,
    contact_email: brContactEmail.trim() || undefined,
    contact_phone: brContactPhone.trim() || undefined,
    transparency_register_id: brTransparencyId.trim() || undefined,
    logo_storage_id: brLogoStorageId || undefined,
  });

  const handleGenerate = async () => {
    if (!token || !selectedType) return;

    setIsGenerating(true);
    setError(null);

    try {
      let endpoint = '';
      let payload: Record<string, unknown> = {};

      if (selectedType === 'position_paper') {
        endpoint = '/generate/position-paper';
        payload = {
          legislation_title: legislationTitle,
          procedure_reference: procedureReference || undefined,
          position,
          key_asks: keyAsks.filter(ask => ask.summary.trim()),
          organisation_name: organisationName,
          organisation_type: organisationType,
          tone,
          organisation_description: organisationDescription || undefined,
          sector_impact: sectorImpact || undefined,
        };
      } else if (selectedType === 'mep_briefing') {
        endpoint = '/generate/mep-briefing';
        payload = {
          mep_name: mepName,
          political_group: politicalGroup || undefined,
          nationality: nationality || undefined,
          committee: committee || undefined,
          legislation_title: legislationTitle,
          procedure_reference: procedureReference || undefined,
          position,
          the_ask: theAsk,
          key_points: keyPoints.filter(p => p.trim()),
          voting_recommendation: votingRecommendation || undefined,
          organisation_name: organisationName,
          national_angle: nationalAngle || undefined,
        };
      } else if (selectedType === 'talking_points') {
        endpoint = '/generate/talking-points';
        payload = {
          meeting_with: meetingWith,
          meeting_institution: meetingInstitution || undefined,
          meeting_purpose: meetingPurpose,
          topic,
          procedure_reference: procedureReference || undefined,
          key_messages: keyMessages.filter(m => m.trim()),
          key_asks: meetingKeyAsks.filter(a => a.trim()),
          organisation_name: organisationName,
        };
      } else if (selectedType === 'resolution') {
        endpoint = '/generate/resolution';
        const filteredRefs = additionalReferences.filter(r => r.trim());
        payload = {
          topic: resolutionTopic,
          context_description: contextDescription,
          key_demands: keyDemands.filter(d => d.trim()).length > 0 ? keyDemands.filter(d => d.trim()) : undefined,
          procedure_reference: procedureReference || undefined,
          additional_references: filteredRefs.length > 0 ? filteredRefs : undefined,
        };
      } else if (selectedType === 'petition') {
        endpoint = '/generate/petition';
        payload = {
          topic: resolutionTopic,
          context_description: contextDescription || undefined,
          petitioner_name: organisationName || undefined,
        };
      } else if (selectedType === 'ep_question') {
        endpoint = '/generate/ep-question';
        const filteredLegRefs = epqLegislationRefs.filter((r: string) => r.trim());
        const filteredSources = epqSources.filter((s: string) => s.trim());
        payload = {
          topic: epqTopic,
          addressee: epqAddressee,
          question_type: epqQuestionType,
          context_description: epqContext,
          legislation_references: filteredLegRefs.length > 0 ? filteredLegRefs : undefined,
          sources: filteredSources.length > 0 ? filteredSources : undefined,
          num_sub_questions: epqNumSubQuestions,
          policy_area: epqPolicyArea || undefined,
          tone: epqTone,
          procedure_reference: procedureReference || undefined,
          celex_number: undefined,
        };
      } else if (selectedType === 'eu_email') {
        endpoint = '/generate/eu-email';
        payload = {
          recipient_name: emRecipientName.trim(),
          recipient_title: emRecipientTitle.trim() || undefined,
          recipient_role: emRecipientRole,
          recipient_institution: emRecipientInstitution,
          recipient_unit: emRecipientUnit.trim() || undefined,
          purpose: emPurpose,
          subject_hint: emSubjectHint.trim() || undefined,
          policy_file_reference: emPolicyFileRef.trim() || undefined,
          the_ask: emTheAsk.trim(),
          context_notes: emContextNotes.trim() || undefined,
          deadline_or_date: emDeadlineOrDate.trim() || undefined,
          tone: emTone,
          relationship: emRelationship,
          language: emLanguage,
          sender_name: emSenderName.trim(),
          sender_title: emSenderTitle.trim() || undefined,
          sender_org: emSenderOrg.trim(),
          sender_email: emSenderEmail.trim() || undefined,
          sender_phone: emSenderPhone.trim() || undefined,
          sender_transparency_register_id: emTransparencyRegisterId.trim() || undefined,
          logo_storage_id: emLogoStorageId || undefined,
        };
      } else if (selectedType === 'one_pager') {
        endpoint = '/generate/one-pager';
        payload = {
          topic: opTopic.trim(),
          procedure_reference: opProcedureRef.trim() || undefined,
          organisation_name: brOrgName.trim(),
          organisation_pitch: opOrgPitch.trim() || undefined,
          position: opPosition,
          headline_ask: opHeadlineAsk.trim(),
          key_asks: opKeyAsks.map((a) => a.trim()).filter(Boolean),
          supporting_evidence: opSupportingEvidence.trim() || undefined,
          tone: opTone,
          language: opLanguage,
          style_reference_storage_id: styleRefStorageId || undefined,
          branding: brandingPayload(),
        };
      } else if (selectedType === 'press_release') {
        endpoint = '/generate/eu-press-release';
        payload = {
          institution_style: prInstitutionStyle,
          headline: prHeadline.trim(),
          sub_headline: prSubHeadline.trim() || undefined,
          dateline_city: prDatelineCity.trim() || 'Brussels',
          dateline_date: prDatelineDate.trim() || undefined,
          lead_paragraph: prLeadParagraph.trim(),
          key_points: prKeyPoints.map((p) => p.trim()).filter(Boolean),
          quote_text: prQuoteText.trim() || undefined,
          quote_attribution: prQuoteAttribution.trim() || undefined,
          background: prBackground.trim() || undefined,
          next_steps: prNextSteps.trim() || undefined,
          contacts: prContacts.trim() || undefined,
          language: prLanguage,
          branding: brandingPayload(),
        };
      } else if (selectedType === 'stakeholder_map') {
        endpoint = '/generate/stakeholder-map';
        payload = {
          policy_topic: smPolicyTopic.trim(),
          procedure_reference: smProcedureRef.trim() || undefined,
          scope: smScope,
          sector: smSector.trim() || undefined,
          objectives: smObjectives.trim(),
          known_stakeholders: smKnown.map((s) => s.trim()).filter(Boolean),
          target_count: smTargetCount,
          language: smLanguage,
          branding: brandingPayload(),
        };
      } else if (selectedType === 'impact_assessment') {
        endpoint = '/generate/impact-assessment';
        payload = {
          initiative_title: iaTitle.trim(),
          policy_area: iaPolicyArea.trim() || undefined,
          problem_definition: iaProblem.trim(),
          drivers: iaDrivers.map((d) => d.trim()).filter(Boolean),
          objectives_general: iaObjectivesGeneral.trim() || undefined,
          objectives_specific: iaObjectivesSpecific.map((o) => o.trim()).filter(Boolean),
          baseline_scenario: iaBaseline.trim() || undefined,
          policy_options: iaOptions.map((o) => o.trim()).filter(Boolean),
          preferred_option_hint: iaPreferredHint.trim() || undefined,
          language: iaLanguage,
          style_reference_storage_id: styleRefStorageId || undefined,
          branding: brandingPayload(),
        };
      } else if (selectedType === 'presentation') {
        endpoint = '/generate/eu-presentation';
        payload = {
          title: presTitle.trim(),
          subtitle: presSubtitle.trim() || undefined,
          audience: presAudience,
          audience_label: presAudienceLabel.trim() || undefined,
          purpose: presPurpose.trim(),
          key_messages: presKeyMessages.map((m) => m.trim()).filter(Boolean),
          sections: presSections.map((s) => s.trim()).filter(Boolean),
          num_slides: presNumSlides,
          language: presLanguage,
          style_reference_storage_id: styleRefStorageId || undefined,
          branding: brandingPayload(),
        };
      } else if (selectedType === 'event_poster') {
        endpoint = '/generate/event-poster';
        payload = {
          event_title: evpTitle.trim(),
          event_tagline: evpTagline.trim() || undefined,
          event_date: evpDate.trim(),
          event_location: evpLocation.trim(),
          event_type: evpEventType,
          hosts: evpHosts.map((h) => h.trim()).filter(Boolean),
          speakers: evpSpeakers.map((s) => s.trim()).filter(Boolean),
          agenda_points: evpAgenda.map((a) => a.trim()).filter(Boolean),
          registration_url: evpRegistrationUrl.trim() || undefined,
          contact_info: evpContactInfo.trim() || undefined,
          format: evpFormat,
          accent_color: evpAccentColor,
          language: evpLanguage,
          style_reference_storage_id: styleRefStorageId || undefined,
          branding: brandingPayload(),
        };
      }

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate document');
      }

      const data = await response.json();
      setGeneratedDocument(data);
      setStep(4); // Move to preview step
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsGenerating(false);
    }
  };

  // Copy to clipboard
  const handleCopy = async () => {
    if (generatedDocument) {
      await navigator.clipboard.writeText(generatedDocument.content);
    }
  };

  // Check if current step is valid
  const isStepValid = () => {
    if (step === 1) return selectedType !== null;
    if (step === 2) {
      if (selectedType === 'position_paper') {
        return legislationTitle.trim() && organisationName.trim() && keyAsks.some(ask => ask.summary.trim());
      }
      if (selectedType === 'mep_briefing') {
        return mepName.trim() && legislationTitle.trim() && theAsk.trim() && organisationName.trim();
      }
      if (selectedType === 'talking_points') {
        return meetingWith.trim() && meetingPurpose.trim() && topic.trim() && organisationName.trim();
      }
      if (selectedType === 'petition') {
        return resolutionTopic.trim().length > 0;
      }
      if (selectedType === 'resolution') {
        return resolutionTopic.trim() && contextDescription.trim();
      }
      if (selectedType === 'ep_question') {
        return epqTopic.trim() && epqContext.trim();
      }
      if (selectedType === 'eu_email') {
        return (
          emRecipientName.trim().length > 0 &&
          emTheAsk.trim().length > 0 &&
          emSenderName.trim().length > 0 &&
          emSenderOrg.trim().length > 0
        );
      }
      if (selectedType === 'one_pager') {
        return (
          opTopic.trim().length > 0 &&
          opHeadlineAsk.trim().length > 0 &&
          brOrgName.trim().length > 0
        );
      }
      if (selectedType === 'press_release') {
        return prHeadline.trim().length > 0 && prLeadParagraph.trim().length > 0;
      }
      if (selectedType === 'stakeholder_map') {
        return smPolicyTopic.trim().length > 0 && smObjectives.trim().length > 0;
      }
      if (selectedType === 'impact_assessment') {
        return iaTitle.trim().length > 0 && iaProblem.trim().length > 0 && iaOptions.filter((o) => o.trim()).length >= 2;
      }
      if (selectedType === 'presentation') {
        return presTitle.trim().length > 0 && presPurpose.trim().length > 0;
      }
      if (selectedType === 'event_poster') {
        return evpTitle.trim().length > 0 && evpDate.trim().length > 0 && evpLocation.trim().length > 0;
      }
    }
    return true;
  };

  if (!isOpen) return null;

  const wizardContent = (
    <div className="doc-generator-overlay" onClick={handleClose}>
      <div className="doc-generator" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="doc-generator__header">
          <h2>{t('docGen.modalTitle')}</h2>
          <button className="doc-generator__close" onClick={handleClose}>×</button>
        </div>

        {/* Progress */}
        <div className="doc-generator__progress">
          <div className={`doc-generator__progress-step ${step >= 1 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">1</span>
            <span className="doc-generator__progress-label">{t('docGen.stepType')}</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 2 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">2</span>
            <span className="doc-generator__progress-label">{t('docGen.stepDetails')}</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 3 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">3</span>
            <span className="doc-generator__progress-label">{t('docGen.stepGenerate')}</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 4 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">4</span>
            <span className="doc-generator__progress-label">{t('docGen.stepPreview')}</span>
          </div>
        </div>

        {/* Content */}
        <div className="doc-generator__content">
          {/* Step 1: Select Document Type */}
          {step === 1 && (
            <div className="doc-generator__step">
              <h3>{t('docGen.whatToGenerate')}</h3>
              <div className="doc-generator__type-grid">
                {DOCUMENT_TYPES.map((type) => {
                  const isLocked = (type.id === 'resolution' || type.id === 'ep_question') && !canUseResolution;
                  // Build a soft (10%-ish opacity) version of the accent for the icon background.
                  const cardStyle = {
                    ['--card-accent' as string]: type.color,
                    ['--card-accent-soft' as string]: type.color + '1a',
                  } as React.CSSProperties;
                  return (
                    <div
                      key={type.id}
                      className={`doc-generator__type-card ${selectedType === type.id ? 'selected' : ''} ${isLocked ? 'doc-generator__type-card--locked' : ''}`}
                      onClick={() => !isLocked && setSelectedType(type.id)}
                      style={cardStyle}
                    >
                      <span className="doc-generator__type-icon-wrap">
                        <Icon path={type.icon} size={1.1} color={isLocked ? '#9ca3af' : type.color} />
                      </span>
                      <h4>{t(type.titleKey)}</h4>
                      <p>{isLocked ? t('docGen.subscriptionRequired') : t(type.descriptionKey)}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 2: Form based on document type */}
          {step === 2 && selectedType === 'position_paper' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.positionPaperDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>{t('docGen.legislationTitle')}</label>
                  <input
                    type="text"
                    value={legislationTitle}
                    onChange={(e) => setLegislationTitle(e.target.value)}
                    placeholder={t('docGen.egAiAct')}
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.procedureRef')}</label>
                    <input
                      type="text"
                      value={procedureReference}
                      onChange={(e) => setProcedureReference(e.target.value)}
                      placeholder={t('docGen.egProcedure')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.yourPosition')}</label>
                    <select value={position} onChange={(e) => setPosition(e.target.value as PositionStance)}>
                      <option value="support">{t('docGen.stanceSupport')}</option>
                      <option value="support_with_amendments">{t('docGen.stanceSupportWithAmendments')}</option>
                      <option value="oppose">{t('docGen.stanceOppose')}</option>
                      <option value="neutral">{t('docGen.stanceNeutral')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.keyAsks')}</label>
                  {keyAsks.map((ask, index) => (
                    <div key={index} className="doc-generator__key-ask">
                      <input
                        type="text"
                        value={ask.summary}
                        onChange={(e) => updateKeyAsk(index, 'summary', e.target.value)}
                        placeholder={t('docGen.askPlaceholder', { n: index + 1 })}
                      />
                      <input
                        type="text"
                        value={ask.article_reference || ''}
                        onChange={(e) => updateKeyAsk(index, 'article_reference', e.target.value)}
                        placeholder={t('docGen.articleRefPlaceholder')}
                        className="doc-generator__key-ask-ref"
                      />
                      {keyAsks.length > 1 && (
                        <button type="button" onClick={() => removeKeyAsk(index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyAsks.length < 5 && (
                    <button type="button" onClick={addKeyAsk} className="doc-generator__add-btn">{t('docGen.addAnotherAsk')}</button>
                  )}
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.organisationName')}</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder={t('docGen.organisationPlaceholder')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.organisationType')}</label>
                    <select value={organisationType} onChange={(e) => setOrganisationType(e.target.value as OrganisationType)}>
                      <option value="company">{t('docGen.orgCompany')}</option>
                      <option value="industry_association">{t('docGen.orgIndustryAssoc')}</option>
                      <option value="ngo">{t('docGen.orgNgo')}</option>
                      <option value="think_tank">{t('docGen.orgThinkTank')}</option>
                      <option value="law_firm">{t('docGen.orgLawFirm')}</option>
                      <option value="consultancy">{t('docGen.orgConsultancy')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.documentTone')}</label>
                  <select value={tone} onChange={(e) => setTone(e.target.value as DocumentTone)}>
                    <option value="constructive">{t('docGen.toneConstructive')}</option>
                    <option value="critical">{t('docGen.toneCritical')}</option>
                    <option value="technical">{t('docGen.toneTechnical')}</option>
                    <option value="diplomatic">{t('docGen.toneDiplomatic')}</option>
                  </select>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.sectorImpact')}</label>
                  <textarea
                    value={sectorImpact}
                    onChange={(e) => setSectorImpact(e.target.value)}
                    placeholder={t('docGen.sectorImpactPlaceholder')}
                    rows={3}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'mep_briefing' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.mepBriefingDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.mepName')}</label>
                    <input
                      type="text"
                      value={mepName}
                      onChange={(e) => setMepName(e.target.value)}
                      placeholder={t('docGen.egBenifei')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.politicalGroup')}</label>
                    <select value={politicalGroup} onChange={(e) => setPoliticalGroup(e.target.value)}>
                      <option value="">{t('docGen.selectEllipsis')}</option>
                      <option value="EPP">{t('docGen.groupEpp')}</option>
                      <option value="S&D">{t('docGen.groupSd')}</option>
                      <option value="Renew">{t('docGen.groupRenew')}</option>
                      <option value="Greens/EFA">{t('docGen.groupGreens')}</option>
                      <option value="ECR">{t('docGen.groupEcr')}</option>
                      <option value="ID">{t('docGen.groupId')}</option>
                      <option value="The Left">{t('docGen.groupTheLeft')}</option>
                      <option value="NI">{t('docGen.groupNi')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.nationality')}</label>
                    <input
                      type="text"
                      value={nationality}
                      onChange={(e) => setNationality(e.target.value)}
                      placeholder={t('docGen.egItalian')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.committee')}</label>
                    <input
                      type="text"
                      value={committee}
                      onChange={(e) => setCommittee(e.target.value)}
                      placeholder={t('docGen.egCommittees')}
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.legislationTitle')}</label>
                  <input
                    type="text"
                    value={legislationTitle}
                    onChange={(e) => setLegislationTitle(e.target.value)}
                    placeholder={t('docGen.egAiAct')}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.theAsk')}</label>
                  <input
                    type="text"
                    value={theAsk}
                    onChange={(e) => setTheAsk(e.target.value)}
                    placeholder={t('docGen.egSupportAmendment')}
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.yourPosition')}</label>
                    <select value={position} onChange={(e) => setPosition(e.target.value as PositionStance)}>
                      <option value="support">{t('docGen.stanceSupport')}</option>
                      <option value="support_with_amendments">{t('docGen.stanceSupportWithAmendments')}</option>
                      <option value="oppose">{t('docGen.stanceOppose')}</option>
                      <option value="neutral">{t('docGen.stanceNeutral')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.organisationName')}</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder={t('docGen.organisationPlaceholder')}
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.keyPoints')}</label>
                  {keyPoints.map((point, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={point}
                        onChange={(e) => updateListItem(keyPoints, setKeyPoints, index, e.target.value)}
                        placeholder={t('docGen.keyPointPlaceholder', { n: index + 1 })}
                      />
                      {keyPoints.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyPoints, setKeyPoints, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyPoints.length < 5 && (
                    <button type="button" onClick={() => addListItem(keyPoints, setKeyPoints, 5)} className="doc-generator__add-btn">{t('docGen.addPoint')}</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.nationalAngle')}</label>
                  <textarea
                    value={nationalAngle}
                    onChange={(e) => setNationalAngle(e.target.value)}
                    placeholder={t('docGen.nationalAnglePlaceholder')}
                    rows={2}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'talking_points' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.talkingPointsDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.meetingWith')}</label>
                    <input
                      type="text"
                      value={meetingWith}
                      onChange={(e) => setMeetingWith(e.target.value)}
                      placeholder={t('docGen.egVestager')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.institution')}</label>
                    <select value={meetingInstitution} onChange={(e) => setMeetingInstitution(e.target.value)}>
                      <option value="">{t('docGen.selectEllipsis')}</option>
                      <option value="European Commission">{t('docGen.instCommission')}</option>
                      <option value="European Parliament">{t('docGen.instParliament')}</option>
                      <option value="Council of the EU">{t('docGen.instCouncil')}</option>
                      <option value="Permanent Representation">{t('docGen.instPermRep')}</option>
                      <option value="Other">{t('docGen.instOther')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.meetingPurpose')}</label>
                  <input
                    type="text"
                    value={meetingPurpose}
                    onChange={(e) => setMeetingPurpose(e.target.value)}
                    placeholder={t('docGen.egMeetingPurpose')}
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.topic')}</label>
                    <input
                      type="text"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder={t('docGen.egAiAct')}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.organisationName')}</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder={t('docGen.organisationPlaceholder')}
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.keyMessages')}</label>
                  {keyMessages.map((msg, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={msg}
                        onChange={(e) => updateListItem(keyMessages, setKeyMessages, index, e.target.value)}
                        placeholder={t('docGen.messagePlaceholder', { n: index + 1 })}
                      />
                      {keyMessages.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyMessages, setKeyMessages, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyMessages.length < 5 && (
                    <button type="button" onClick={() => addListItem(keyMessages, setKeyMessages, 5)} className="doc-generator__add-btn">{t('docGen.addMessage')}</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.meetingKeyAsks')}</label>
                  {meetingKeyAsks.map((ask, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={ask}
                        onChange={(e) => updateListItem(meetingKeyAsks, setMeetingKeyAsks, index, e.target.value)}
                        placeholder={t('docGen.askShortPlaceholder', { n: index + 1 })}
                      />
                      {meetingKeyAsks.length > 1 && (
                        <button type="button" onClick={() => removeListItem(meetingKeyAsks, setMeetingKeyAsks, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {meetingKeyAsks.length < 3 && (
                    <button type="button" onClick={() => addListItem(meetingKeyAsks, setMeetingKeyAsks, 3)} className="doc-generator__add-btn">{t('docGen.addAsk')}</button>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'petition' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.petitionDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>{t('docGen.petitionSubject')}</label>
                  <input
                    type="text"
                    value={resolutionTopic}
                    onChange={(e) => setResolutionTopic(e.target.value)}
                    placeholder={t('docGen.egPetitionSubject')}
                  />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.contextDescription')}</label>
                  <textarea
                    value={contextDescription}
                    onChange={(e) => setContextDescription(e.target.value)}
                    placeholder={t('docGen.contextPlaceholder')}
                    rows={4}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'resolution' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.resolutionDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>{t('docGen.resolutionTopic')}</label>
                  <input
                    type="text"
                    value={resolutionTopic}
                    onChange={(e) => setResolutionTopic(e.target.value)}
                    placeholder={t('docGen.egResolutionTopic')}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.procedureRef')}</label>
                  <input
                    type="text"
                    value={procedureReference}
                    onChange={(e) => setProcedureReference(e.target.value)}
                    placeholder={t('docGen.egRspProc')}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.contextDescription')}</label>
                  <textarea
                    value={contextDescription}
                    onChange={(e) => setContextDescription(e.target.value)}
                    placeholder={t('docGen.contextPlaceholder')}
                    rows={4}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.keyDemands')}</label>
                  <p className="doc-generator__form-hint">
                    {t('docGen.keyDemandsHint')}
                  </p>
                  {keyDemands.map((demand, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={demand}
                        onChange={(e) => updateListItem(keyDemands, setKeyDemands, index, e.target.value)}
                        placeholder={t('docGen.demandPlaceholder', { n: index + 1 })}
                      />
                      {keyDemands.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyDemands, setKeyDemands, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyDemands.length < 10 && (
                    <button type="button" onClick={() => addListItem(keyDemands, setKeyDemands, 10)} className="doc-generator__add-btn">{t('docGen.addDemand')}</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.additionalReferences')}</label>
                  <p className="doc-generator__form-hint">
                    {t('docGen.additionalReferencesHint')}
                  </p>
                  {additionalReferences.length === 0 ? (
                    <button type="button" onClick={() => setAdditionalReferences([''])} className="doc-generator__add-btn">{t('docGen.addReference')}</button>
                  ) : (
                    <>
                      {additionalReferences.map((ref, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={ref}
                            onChange={(e) => updateListItem(additionalReferences, setAdditionalReferences, index, e.target.value)}
                            placeholder={t('docGen.egRefRegulation')}
                          />
                          <button type="button" onClick={() => {
                            const updated = additionalReferences.filter((_, i) => i !== index);
                            setAdditionalReferences(updated);
                          }} className="doc-generator__remove-btn">×</button>
                        </div>
                      ))}
                      {additionalReferences.length < 5 && (
                        <button type="button" onClick={() => addListItem(additionalReferences, setAdditionalReferences, 5)} className="doc-generator__add-btn">{t('docGen.addReference')}</button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'ep_question' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.epQuestionDetails')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>{t('docGen.topicTitle')}</label>
                  <input
                    type="text"
                    value={epqTopic}
                    onChange={(e) => setEpqTopic(e.target.value)}
                    placeholder={t('docGen.egEpqTopic')}
                    maxLength={200}
                  />
                  <span className="doc-generator__char-count">{epqTopic.length}/200</span>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.addressee')}</label>
                    <select value={epqAddressee} onChange={(e) => setEpqAddressee(e.target.value as 'commission' | 'council' | 'vp_hr')}>
                      <option value="commission">{t('docGen.instCommission')}</option>
                      <option value="council">{t('docGen.addresseeCouncil')}</option>
                      <option value="vp_hr">{t('docGen.addresseeVpHr')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.questionType')}</label>
                    <select value={epqQuestionType} onChange={(e) => setEpqQuestionType(e.target.value as 'standard' | 'priority')}>
                      <option value="standard">{t('docGen.qStandard')}</option>
                      <option value="priority">{t('docGen.qPriority')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.contextEvidence')}</label>
                  <p className="doc-generator__form-hint">
                    {t('docGen.contextEvidenceHint')}
                  </p>
                  <textarea
                    value={epqContext}
                    onChange={(e) => setEpqContext(e.target.value)}
                    placeholder={t('docGen.egEpqContext')}
                    rows={5}
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.numSubQuestions')}</label>
                    <select value={epqNumSubQuestions} onChange={(e) => setEpqNumSubQuestions(Number(e.target.value))}>
                      <option value={1}>{t('docGen.subQ1')}</option>
                      <option value={2}>{t('docGen.subQ2')}</option>
                      <option value={3}>{t('docGen.subQ3')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.tone')}</label>
                    <select value={epqTone} onChange={(e) => setEpqTone(e.target.value as 'assertive' | 'diplomatic' | 'technical')}>
                      <option value="assertive">{t('docGen.epqToneAssertive')}</option>
                      <option value="diplomatic">{t('docGen.epqToneDiplomatic')}</option>
                      <option value="technical">{t('docGen.epqToneTechnical')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.procedureRef')}</label>
                  <input
                    type="text"
                    value={procedureReference}
                    onChange={(e) => setProcedureReference(e.target.value)}
                    placeholder={t('docGen.egProcedure')}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.legislationReferences')}</label>
                  <p className="doc-generator__form-hint">
                    {t('docGen.legislationReferencesHint')}
                  </p>
                  {epqLegislationRefs.length === 0 ? (
                    <button type="button" onClick={() => setEpqLegislationRefs([''])} className="doc-generator__add-btn">{t('docGen.addLegRef')}</button>
                  ) : (
                    <>
                      {epqLegislationRefs.map((ref, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={ref}
                            onChange={(e) => updateListItem(epqLegislationRefs, setEpqLegislationRefs, index, e.target.value)}
                            placeholder={t('docGen.egRegEu2021')}
                          />
                          <button type="button" onClick={() => {
                            const updated = epqLegislationRefs.filter((_, i) => i !== index);
                            setEpqLegislationRefs(updated);
                          }} className="doc-generator__remove-btn">×</button>
                        </div>
                      ))}
                      {epqLegislationRefs.length < 5 && (
                        <button type="button" onClick={() => addListItem(epqLegislationRefs, setEpqLegislationRefs, 5)} className="doc-generator__add-btn">{t('docGen.addReference')}</button>
                      )}
                    </>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.evidenceSources')}</label>
                  <p className="doc-generator__form-hint">
                    {t('docGen.evidenceSourcesHint')}
                  </p>
                  {epqSources.length === 0 ? (
                    <button type="button" onClick={() => setEpqSources([''])} className="doc-generator__add-btn">{t('docGen.addSource')}</button>
                  ) : (
                    <>
                      {epqSources.map((src, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={src}
                            onChange={(e) => updateListItem(epqSources, setEpqSources, index, e.target.value)}
                            placeholder={t('docGen.egEcaReport')}
                          />
                          <button type="button" onClick={() => {
                            const updated = epqSources.filter((_, i) => i !== index);
                            setEpqSources(updated);
                          }} className="doc-generator__remove-btn">×</button>
                        </div>
                      ))}
                      {epqSources.length < 5 && (
                        <button type="button" onClick={() => addListItem(epqSources, setEpqSources, 5)} className="doc-generator__add-btn">{t('docGen.addSource')}</button>
                      )}
                    </>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.policyArea')}</label>
                  <select value={epqPolicyArea} onChange={(e) => setEpqPolicyArea(e.target.value)}>
                    <option value="">{t('docGen.selectOptionalEllipsis')}</option>
                    <option value="Digital">{t('docGen.paDigital')}</option>
                    <option value="Trade">{t('docGen.paTrade')}</option>
                    <option value="Industry">{t('docGen.paIndustry')}</option>
                    <option value="Environment">{t('docGen.paEnvironment')}</option>
                    <option value="Agriculture">{t('docGen.paAgriculture')}</option>
                    <option value="Transport">{t('docGen.paTransport')}</option>
                    <option value="Justice">{t('docGen.paJustice')}</option>
                    <option value="Health">{t('docGen.paHealth')}</option>
                    <option value="Foreign Affairs">{t('docGen.paForeignAffairs')}</option>
                    <option value="Energy">{t('docGen.paEnergy')}</option>
                    <option value="Employment">{t('docGen.paEmployment')}</option>
                    <option value="Internal Market">{t('docGen.paInternalMarket')}</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'eu_email' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.emailLetterTitle')}</h3>
              <p className="doc-generator__form-hint">
                Brussels-style email in 6 blocks: subject, greeting, hook, core message,
                sign-off, signature with GDPR + Transparency Register footer. No em-dashes.
              </p>
              <div className="doc-generator__form">

                {/* Recipient */}
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.recipientName')}</label>
                    <input
                      type="text"
                      value={emRecipientName}
                      onChange={(e) => setEmRecipientName(e.target.value)}
                      placeholder="e.g. Margrethe Vestager"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.theirTitle')}</label>
                    <input
                      type="text"
                      value={emRecipientTitle}
                      onChange={(e) => setEmRecipientTitle(e.target.value)}
                      placeholder="e.g. Executive Vice-President"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.roleCategory')}</label>
                    <select
                      value={emRecipientRole}
                      onChange={(e) => setEmRecipientRole(e.target.value as typeof emRecipientRole)}
                    >
                      <option value="commissioner">{t('docGen.wizard.roleCommissioner')}</option>
                      <option value="cabinet_member">{t('docGen.wizard.roleCabinetMember')}</option>
                      <option value="director_general">{t('docGen.wizard.roleDirectorGeneral')}</option>
                      <option value="director">{t('docGen.wizard.roleDirector')}</option>
                      <option value="head_of_unit">{t('docGen.wizard.roleHeadOfUnit')}</option>
                      <option value="policy_officer">{t('docGen.wizard.rolePolicyOfficer')}</option>
                      <option value="mep">{t('docGen.wizard.roleMep')}</option>
                      <option value="apa">{t('docGen.wizard.roleApa')}</option>
                      <option value="ep_group_advisor">{t('docGen.wizard.roleEpGroupAdvisor')}</option>
                      <option value="ep_committee_staff">{t('docGen.wizard.audienceEpStaff')}</option>
                      <option value="council_attache">{t('docGen.wizard.audienceCouncilAttache')}</option>
                      <option value="permrep_counsellor">{t('docGen.wizard.rolePermrepCounsellor')}</option>
                      <option value="ambassador">{t('docGen.wizard.roleAmbassador')}</option>
                      <option value="other">{t('docGen.wizard.typeOther')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.institution')}</label>
                    <select
                      value={emRecipientInstitution}
                      onChange={(e) => setEmRecipientInstitution(e.target.value as typeof emRecipientInstitution)}
                    >
                      <option value="european_commission">{t('docGen.wizard.instEuropeanCommission')}</option>
                      <option value="european_parliament">{t('docGen.wizard.instEuropeanParliament')}</option>
                      <option value="council_eu">{t('docGen.wizard.instCouncilOfEu')}</option>
                      <option value="permanent_representation">{t('docGen.wizard.instPermrep')}</option>
                      <option value="eeas">{t('docGen.wizard.instEeas')}</option>
                      <option value="agency">{t('docGen.wizard.agencyStyle')}</option>
                      <option value="other">{t('docGen.wizard.typeOther')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.recipientUnit')}</label>
                  <input
                    type="text"
                    value={emRecipientUnit}
                    onChange={(e) => setEmRecipientUnit(e.target.value)}
                    placeholder="e.g. DG ENVI, IMCO, COREPER II"
                  />
                </div>

                {/* Intent */}
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.purpose')}</label>
                    <select
                      value={emPurpose}
                      onChange={(e) => setEmPurpose(e.target.value as typeof emPurpose)}
                    >
                      <option value="meeting_request">{t('docGen.wizard.purposeMeetingRequest')}</option>
                      <option value="follow_up">{t('docGen.wizard.purposeFollowUp')}</option>
                      <option value="position_input">{t('docGen.wizard.purposePositionInput')}</option>
                      <option value="amendment_input">{t('docGen.wizard.purposeAmendmentInput')}</option>
                      <option value="information_request">{t('docGen.wizard.purposeInfoRequest')}</option>
                      <option value="invitation">{t('docGen.wizard.purposeInvitation')}</option>
                      <option value="thanks">{t('docGen.wizard.purposeThanks')}</option>
                      <option value="other">{t('docGen.wizard.typeOther')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.relationship')}</label>
                    <select
                      value={emRelationship}
                      onChange={(e) => setEmRelationship(e.target.value as typeof emRelationship)}
                    >
                      <option value="cold">{t('docGen.wizard.relCold')}</option>
                      <option value="warm">{t('docGen.wizard.relWarm')}</option>
                      <option value="established">{t('docGen.wizard.relEstablished')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.tone')}</label>
                    <select value={emTone} onChange={(e) => setEmTone(e.target.value as typeof emTone)}>
                      <option value="standard">{t('docGen.wizard.toneStandard')}</option>
                      <option value="warm">{t('docGen.wizard.toneWarm')}</option>
                      <option value="urgent">{t('docGen.wizard.toneUrgent')}</option>
                      <option value="formal">{t('docGen.wizard.toneFormal')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={emLanguage} onChange={(e) => setEmLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.policyFileRef')}</label>
                  <input
                    type="text"
                    value={emPolicyFileRef}
                    onChange={(e) => setEmPolicyFileRef(e.target.value)}
                    placeholder="e.g. AI Act trilogue, 2021/0106(COD), DG ENVI Ecodesign implementation"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.subjectHint')}</label>
                  <input
                    type="text"
                    value={emSubjectHint}
                    onChange={(e) => setEmSubjectHint(e.target.value)}
                    placeholder="Leave blank for the AI to invent a Brussels-style subject"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.theAsk')}</label>
                  <textarea
                    rows={3}
                    value={emTheAsk}
                    onChange={(e) => setEmTheAsk(e.target.value)}
                    placeholder="In one or two plain-language sentences, the concrete thing you want from the recipient (a meeting, an amendment, a clarification, a position)."
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.contextNotes')}</label>
                  <textarea
                    rows={4}
                    value={emContextNotes}
                    onChange={(e) => setEmContextNotes(e.target.value)}
                    placeholder="Prior exchanges, what was said in a recent meeting, evidence to reference, why this matters now."
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.timeAnchor')}</label>
                  <input
                    type="text"
                    value={emDeadlineOrDate}
                    onChange={(e) => setEmDeadlineOrDate(e.target.value)}
                    placeholder="e.g. before the IMCO vote on 12 June, next Tuesday afternoon"
                  />
                </div>

                <div className="doc-generator__form-section-divider">Sender</div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.yourName')}</label>
                    <input
                      type="text"
                      value={emSenderName}
                      onChange={(e) => setEmSenderName(e.target.value)}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.yourTitle')}</label>
                    <input
                      type="text"
                      value={emSenderTitle}
                      onChange={(e) => setEmSenderTitle(e.target.value)}
                      placeholder="e.g. Policy Director"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.yourOrganisation')}</label>
                    <input
                      type="text"
                      value={emSenderOrg}
                      onChange={(e) => setEmSenderOrg(e.target.value)}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.euTransparencyId')}</label>
                    <input
                      type="text"
                      value={emTransparencyRegisterId}
                      onChange={(e) => setEmTransparencyRegisterId(e.target.value)}
                      placeholder="e.g. 123456789012-34"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.yourEmail')}</label>
                    <input
                      type="email"
                      value={emSenderEmail}
                      onChange={(e) => setEmSenderEmail(e.target.value)}
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.yourPhone')}</label>
                    <input
                      type="text"
                      value={emSenderPhone}
                      onChange={(e) => setEmSenderPhone(e.target.value)}
                      placeholder="+32 2 ..."
                    />
                  </div>
                </div>

                {/* Logo upload */}
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.organisationLogoOptional')}</label>
                  <p className="doc-generator__form-hint">{t('docGen.wizard.logoEmailHint')}</p>
                  {emLogoStorageId ? (
                    <div className="doc-generator__logo-chip">
                      <Icon path={mdiImagePlusOutline} size={0.7} />
                      <span>{emLogoFilename || 'Logo attached'}</span>
                      <button
                        type="button"
                        className="doc-generator__logo-remove"
                        onClick={() => {
                          setEmLogoStorageId(null);
                          setEmLogoFilename(null);
                        }}
                        title="Remove logo"
                      >
                        <Icon path={mdiCloseCircleOutline} size={0.8} />
                      </button>
                    </div>
                  ) : (
                    <label className="doc-generator__logo-upload">
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/svg+xml"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) handleLogoUpload(f);
                        }}
                      />
                      <Icon path={mdiImagePlusOutline} size={0.9} />
                      {emLogoUploading ? 'Uploading…' : 'Upload logo'}
                    </label>
                  )}
                  {emLogoError && (
                    <div className="doc-generator__form-error">{emLogoError}</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ==============================================================
              Step 2 forms for the 6 new document types
              ============================================================== */}

          {step === 2 && selectedType === 'one_pager' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.onePagerSectionTitle')}</h3>
              <p className="doc-generator__form-hint">
                Strict single-page summary with a headline ask, 2 to 5 short bullets,
                and supporting evidence. Renders to DOCX and PDF.
              </p>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.topicLabel')}</label>
                    <input type="text" value={opTopic} onChange={(e) => setOpTopic(e.target.value)}
                      placeholder="e.g. AI Act -- general-purpose AI rules" />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.procedureRef')}</label>
                    <input type="text" value={opProcedureRef} onChange={(e) => setOpProcedureRef(e.target.value)}
                      placeholder="e.g. 2021/0106(COD)" />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.headlineAskAddCounter')}</label>
                  <input type="text" value={opHeadlineAsk} onChange={(e) => setOpHeadlineAsk(e.target.value)}
                    placeholder="The single most important request, rendered as the H1" />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.position')}</label>
                    <select value={opPosition} onChange={(e) => setOpPosition(e.target.value as PositionStance)}>
                      <option value="support">{t('docGen.wizard.positionSupport')}</option>
                      <option value="support_with_amendments">{t('docGen.wizard.positionSupportWithAmendments')}</option>
                      <option value="oppose">{t('docGen.wizard.positionOppose')}</option>
                      <option value="neutral">{t('docGen.wizard.positionNeutral')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.tone')}</label>
                    <select value={opTone} onChange={(e) => setOpTone(e.target.value as DocumentTone)}>
                      <option value="constructive">{t('docGen.wizard.posToneConstructive')}</option>
                      <option value="critical">{t('docGen.wizard.posToneCritical')}</option>
                      <option value="technical">{t('docGen.wizard.posToneTechnical')}</option>
                      <option value="diplomatic">{t('docGen.wizard.posToneDiplomatic')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={opLanguage} onChange={(e) => setOpLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.keyAsksMinimal')}</label>
                  {opKeyAsks.map((a, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={a}
                        onChange={(e) => updateListItem(opKeyAsks, setOpKeyAsks, i, e.target.value)}
                        placeholder={`Key ask ${i + 1}`} />
                      {opKeyAsks.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(opKeyAsks, setOpKeyAsks, i)}>×</button>
                      )}
                    </div>
                  ))}
                  {opKeyAsks.length < 5 && (
                    <button type="button" className="doc-generator__add-btn"
                      onClick={() => addListItem(opKeyAsks, setOpKeyAsks, 5)}>Add ask</button>
                  )}
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.supportingEvidence')}</label>
                  <textarea rows={3} value={opSupportingEvidence}
                    onChange={(e) => setOpSupportingEvidence(e.target.value)}
                    placeholder="Numbers, citations, sector impact data." />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.organisationPitch')}</label>
                  <input type="text" value={opOrgPitch} onChange={(e) => setOpOrgPitch(e.target.value)}
                    placeholder="One- or two-sentence elevator pitch" />
                </div>
                <BrandingPanel
                  org={brOrgName} setOrg={setBrOrgName}
                  url={brOrgUrl} setUrl={setBrOrgUrl}
                  email={brContactEmail} setEmail={setBrContactEmail}
                  phone={brContactPhone} setPhone={setBrContactPhone}
                  transparencyId={brTransparencyId} setTransparencyId={setBrTransparencyId}
                  logoStorageId={brLogoStorageId} setLogoStorageId={setBrLogoStorageId}
                  logoFilename={brLogoFilename} setLogoFilename={setBrLogoFilename}
                  logoUploading={brLogoUploading} logoError={brLogoError}
                  onLogoUpload={handleBrLogoUpload}
                />
                <StyleRefPanel
                  storageId={styleRefStorageId} setStorageId={setStyleRefStorageId}
                  filename={styleRefFilename} setFilename={setStyleRefFilename}
                  uploading={styleRefUploading} error={styleRefError}
                  onUpload={handleStyleRefUpload}
                  hint="Upload an example one-pager (PDF/DOCX) for Brubru to learn your tone and layout."
                />
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'press_release' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.pressReleaseSectionTitle')}</h3>
              <p className="doc-generator__form-hint">{t('docGen.wizard.pressReleaseHint')}</p>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.houseStyle')}</label>
                    <select value={prInstitutionStyle}
                      onChange={(e) => setPrInstitutionStyle(e.target.value as typeof prInstitutionStyle)}>
                      <option value="commission">{t('docGen.wizard.commissionStyle')}</option>
                      <option value="parliament">{t('docGen.wizard.instEuropeanParliament')}</option>
                      <option value="council">{t('docGen.wizard.instCouncilOfEu')}</option>
                      <option value="agency">{t('docGen.wizard.agencyStyle')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={prLanguage} onChange={(e) => setPrLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.headline')}</label>
                  <input type="text" value={prHeadline} onChange={(e) => setPrHeadline(e.target.value)}
                    placeholder="e.g. Commission strengthens enforcement of the Digital Services Act" />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.subheadline')}</label>
                  <input type="text" value={prSubHeadline} onChange={(e) => setPrSubHeadline(e.target.value)}
                    placeholder="One-line strap" />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.datelineCity')}</label>
                    <input type="text" value={prDatelineCity} onChange={(e) => setPrDatelineCity(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.datelineDate')}</label>
                    <input type="text" value={prDatelineDate} onChange={(e) => setPrDatelineDate(e.target.value)}
                      placeholder="e.g. 20 May 2026" />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.leadParagraph')}</label>
                  <textarea rows={3} value={prLeadParagraph} onChange={(e) => setPrLeadParagraph(e.target.value)}
                    placeholder="The opening paragraph (who/what/where/when/why)." />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.keyPointsPr')}</label>
                  {prKeyPoints.map((p, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={p}
                        onChange={(e) => updateListItem(prKeyPoints, setPrKeyPoints, i, e.target.value)}
                        placeholder={`Key point ${i + 1}`} />
                      {prKeyPoints.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(prKeyPoints, setPrKeyPoints, i)}>×</button>
                      )}
                    </div>
                  ))}
                  {prKeyPoints.length < 8 && (
                    <button type="button" className="doc-generator__add-btn"
                      onClick={() => addListItem(prKeyPoints, setPrKeyPoints, 8)}>Add point</button>
                  )}
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.quote')}</label>
                    <textarea rows={2} value={prQuoteText} onChange={(e) => setPrQuoteText(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.attributedTo')}</label>
                    <input type="text" value={prQuoteAttribution}
                      onChange={(e) => setPrQuoteAttribution(e.target.value)}
                      placeholder="e.g. Margrethe Vestager, EVP" />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.background')}</label>
                  <textarea rows={3} value={prBackground} onChange={(e) => setPrBackground(e.target.value)} />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.nextSteps')}</label>
                    <textarea rows={2} value={prNextSteps} onChange={(e) => setPrNextSteps(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.pressContacts')}</label>
                    <textarea rows={2} value={prContacts} onChange={(e) => setPrContacts(e.target.value)}
                      placeholder="One contact per line" />
                  </div>
                </div>
                <BrandingPanel
                  org={brOrgName} setOrg={setBrOrgName}
                  url={brOrgUrl} setUrl={setBrOrgUrl}
                  email={brContactEmail} setEmail={setBrContactEmail}
                  phone={brContactPhone} setPhone={setBrContactPhone}
                  transparencyId={brTransparencyId} setTransparencyId={setBrTransparencyId}
                  logoStorageId={brLogoStorageId} setLogoStorageId={setBrLogoStorageId}
                  logoFilename={brLogoFilename} setLogoFilename={setBrLogoFilename}
                  logoUploading={brLogoUploading} logoError={brLogoError}
                  onLogoUpload={handleBrLogoUpload}
                />
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'stakeholder_map' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.stakeholderTitle')}</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.policyTopic')}</label>
                  <input type="text" value={smPolicyTopic} onChange={(e) => setSmPolicyTopic(e.target.value)}
                    placeholder="e.g. AI Act enforcement, EU Inc., Net Zero Industry Act" />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.policyFileRef')}</label>
                    <input type="text" value={smProcedureRef} onChange={(e) => setSmProcedureRef(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.scope')}</label>
                    <select value={smScope} onChange={(e) => setSmScope(e.target.value as typeof smScope)}>
                      <option value="eu">{t('docGen.wizard.scopeEu')}</option>
                      <option value="national">{t('docGen.wizard.scopeNational')}</option>
                      <option value="both">{t('docGen.wizard.scopeBoth')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.sector')}</label>
                    <input type="text" value={smSector} onChange={(e) => setSmSector(e.target.value)} />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.yourObjectives')}</label>
                  <textarea rows={3} value={smObjectives} onChange={(e) => setSmObjectives(e.target.value)}
                    placeholder="What you want to achieve on this file." />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.targetStakeholderCount')}</label>
                    <input type="number" min={4} max={40} value={smTargetCount}
                      onChange={(e) => setSmTargetCount(Number(e.target.value) || 12)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={smLanguage} onChange={(e) => setSmLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.knownStakeholders')}</label>
                  {smKnown.map((s, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={s}
                        onChange={(e) => updateListItem(smKnown, setSmKnown, i, e.target.value)}
                        placeholder="e.g. Brando Benifei (S&D, IMCO, AI Act rapporteur)" />
                      {smKnown.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(smKnown, setSmKnown, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(smKnown, setSmKnown, 30)}>{t('docGen.wizard.addStakeholder')}</button>
                </div>
                <BrandingPanel
                  org={brOrgName} setOrg={setBrOrgName}
                  url={brOrgUrl} setUrl={setBrOrgUrl}
                  email={brContactEmail} setEmail={setBrContactEmail}
                  phone={brContactPhone} setPhone={setBrContactPhone}
                  transparencyId={brTransparencyId} setTransparencyId={setBrTransparencyId}
                  logoStorageId={brLogoStorageId} setLogoStorageId={setBrLogoStorageId}
                  logoFilename={brLogoFilename} setLogoFilename={setBrLogoFilename}
                  logoUploading={brLogoUploading} logoError={brLogoError}
                  onLogoUpload={handleBrLogoUpload}
                />
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'impact_assessment' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.impactAssessmentTitle')}</h3>
              <p className="doc-generator__form-hint">
                Commission Better Regulation IA template (8 sections: problem, EU action,
                objectives, options, impacts, comparison, preferred option, monitoring).
              </p>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.initiativeTitle')}</label>
                    <input type="text" value={iaTitle} onChange={(e) => setIaTitle(e.target.value)}
                      placeholder="e.g. Revision of the Combined Transport Directive" />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.policyArea')}</label>
                    <input type="text" value={iaPolicyArea} onChange={(e) => setIaPolicyArea(e.target.value)}
                      placeholder="e.g. DG MOVE -- intermodal transport" />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.problemDefinition')}</label>
                  <textarea rows={4} value={iaProblem} onChange={(e) => setIaProblem(e.target.value)}
                    placeholder="What is the problem, who is affected, and how does it persist under the baseline." />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.drivers')}</label>
                  {iaDrivers.map((d, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={d}
                        onChange={(e) => updateListItem(iaDrivers, setIaDrivers, i, e.target.value)}
                        placeholder={`Driver ${i + 1}`} />
                      {iaDrivers.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(iaDrivers, setIaDrivers, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(iaDrivers, setIaDrivers, 10)}>{t('docGen.wizard.addDriver')}</button>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.generalObjective')}</label>
                  <textarea rows={2} value={iaObjectivesGeneral}
                    onChange={(e) => setIaObjectivesGeneral(e.target.value)} />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.specificObjectives')}</label>
                  {iaObjectivesSpecific.map((o, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={o}
                        onChange={(e) => updateListItem(iaObjectivesSpecific, setIaObjectivesSpecific, i, e.target.value)}
                        placeholder={`Objective ${i + 1}`} />
                      {iaObjectivesSpecific.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(iaObjectivesSpecific, setIaObjectivesSpecific, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(iaObjectivesSpecific, setIaObjectivesSpecific, 10)}>{t('docGen.wizard.addObjective')}</button>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.baselineScenario')}</label>
                  <textarea rows={2} value={iaBaseline} onChange={(e) => setIaBaseline(e.target.value)} />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.policyOptions')}</label>
                  {iaOptions.map((o, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={o}
                        onChange={(e) => updateListItem(iaOptions, setIaOptions, i, e.target.value)}
                        placeholder={`Option ${i}`} />
                      {iaOptions.length > 2 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(iaOptions, setIaOptions, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(iaOptions, setIaOptions, 8)}>{t('docGen.wizard.addOption')}</button>
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.preferredOptionHint')}</label>
                    <input type="text" value={iaPreferredHint}
                      onChange={(e) => setIaPreferredHint(e.target.value)}
                      placeholder="Leave blank for the AI to pick" />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={iaLanguage} onChange={(e) => setIaLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <StyleRefPanel
                  storageId={styleRefStorageId} setStorageId={setStyleRefStorageId}
                  filename={styleRefFilename} setFilename={setStyleRefFilename}
                  uploading={styleRefUploading} error={styleRefError}
                  onUpload={handleStyleRefUpload}
                  hint="Upload an example Commission IA (PDF) for Brubru to mirror its layout."
                />
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'presentation' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.presentationTitle')}</h3>
              <p className="doc-generator__form-hint">
                {t('docGen.wizard.presentationHint')}
              </p>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.presTitle')}</label>
                    <input type="text" value={presTitle} onChange={(e) => setPresTitle(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.presSubtitle')}</label>
                    <input type="text" value={presSubtitle} onChange={(e) => setPresSubtitle(e.target.value)} />
                  </div>
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.presAudience')}</label>
                    <select value={presAudience} onChange={(e) => setPresAudience(e.target.value as typeof presAudience)}>
                      <option value="commission_official">{t('docGen.wizard.audienceCommOfficials')}</option>
                      <option value="commission_cabinet">{t('docGen.wizard.audienceCommCabinet')}</option>
                      <option value="mep_office">{t('docGen.wizard.audienceMepOffice')}</option>
                      <option value="ep_committee_staff">{t('docGen.wizard.audienceEpStaff')}</option>
                      <option value="council_attache">{t('docGen.wizard.audienceCouncilAttache')}</option>
                      <option value="permrep">{t('docGen.wizard.audiencePermRep')}</option>
                      <option value="academic">{t('docGen.wizard.audienceAcademic')}</option>
                      <option value="industry">{t('docGen.wizard.audienceIndustry')}</option>
                      <option value="press">{t('docGen.wizard.audiencePress')}</option>
                      <option value="general">{t('docGen.wizard.audienceGeneral')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.audienceRefinement')}</label>
                    <input type="text" value={presAudienceLabel}
                      onChange={(e) => setPresAudienceLabel(e.target.value)}
                      placeholder="e.g. DG ENVI Unit B3" />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.presSlides')}</label>
                    <input type="number" min={4} max={30} value={presNumSlides}
                      onChange={(e) => setPresNumSlides(Number(e.target.value) || 10)} />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.presPurpose')}</label>
                  <textarea rows={2} value={presPurpose} onChange={(e) => setPresPurpose(e.target.value)}
                    placeholder="What this presentation should achieve." />
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.presKeyMessages')}</label>
                  {presKeyMessages.map((m, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={m}
                        onChange={(e) => updateListItem(presKeyMessages, setPresKeyMessages, i, e.target.value)}
                        placeholder={`Message ${i + 1}`} />
                      {presKeyMessages.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(presKeyMessages, setPresKeyMessages, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(presKeyMessages, setPresKeyMessages, 8)}>{t('docGen.wizard.addMessage')}</button>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.presSections')}</label>
                  {presSections.map((s, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={s}
                        onChange={(e) => updateListItem(presSections, setPresSections, i, e.target.value)}
                        placeholder={`Section ${i + 1}`} />
                      {presSections.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(presSections, setPresSections, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(presSections, setPresSections, 10)}>{t('docGen.wizard.addSection')}</button>
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={presLanguage} onChange={(e) => setPresLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <BrandingPanel
                  org={brOrgName} setOrg={setBrOrgName}
                  url={brOrgUrl} setUrl={setBrOrgUrl}
                  email={brContactEmail} setEmail={setBrContactEmail}
                  phone={brContactPhone} setPhone={setBrContactPhone}
                  transparencyId={brTransparencyId} setTransparencyId={setBrTransparencyId}
                  logoStorageId={brLogoStorageId} setLogoStorageId={setBrLogoStorageId}
                  logoFilename={brLogoFilename} setLogoFilename={setBrLogoFilename}
                  logoUploading={brLogoUploading} logoError={brLogoError}
                  onLogoUpload={handleBrLogoUpload}
                />
                <StyleRefPanel
                  storageId={styleRefStorageId} setStorageId={setStyleRefStorageId}
                  filename={styleRefFilename} setFilename={setStyleRefFilename}
                  uploading={styleRefUploading} error={styleRefError}
                  onUpload={handleStyleRefUpload}
                  hint="Upload an example deck (PPTX or PDF) for Brubru to mirror its slide style."
                />
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'event_poster' && (
            <div className="doc-generator__step">
              <h3>{t('docGen.wizard.eventPosterTitle')}</h3>
              <p className="doc-generator__form-hint">
                {t('docGen.wizard.eventPosterHint')}
              </p>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.eventTitle')}</label>
                    <input type="text" value={evpTitle} onChange={(e) => setEvpTitle(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.eventType')}</label>
                    <select value={evpEventType} onChange={(e) => setEvpEventType(e.target.value as typeof evpEventType)}>
                      <option value="conference">{t('docGen.wizard.typeConference')}</option>
                      <option value="panel">{t('docGen.wizard.typePanel')}</option>
                      <option value="webinar">{t('docGen.wizard.typeWebinar')}</option>
                      <option value="roundtable">{t('docGen.wizard.typeRoundtable')}</option>
                      <option value="workshop">{t('docGen.wizard.typeWorkshop')}</option>
                      <option value="launch">{t('docGen.wizard.typeLaunch')}</option>
                      <option value="other">{t('docGen.wizard.typeOther')}</option>
                    </select>
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.tagline')}</label>
                  <input type="text" value={evpTagline} onChange={(e) => setEvpTagline(e.target.value)} />
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.eventDate')}</label>
                    <input type="text" value={evpDate} onChange={(e) => setEvpDate(e.target.value)}
                      placeholder="e.g. 12 June 2026, 14:00 CET" />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.eventLocation')}</label>
                    <input type="text" value={evpLocation} onChange={(e) => setEvpLocation(e.target.value)}
                      placeholder="e.g. Résidence Palace, Brussels" />
                  </div>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.hosts')}</label>
                  {evpHosts.map((h, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={h}
                        onChange={(e) => updateListItem(evpHosts, setEvpHosts, i, e.target.value)} />
                      {evpHosts.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(evpHosts, setEvpHosts, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(evpHosts, setEvpHosts, 8)}>Add host</button>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.speakers')}</label>
                  {evpSpeakers.map((s, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={s}
                        onChange={(e) => updateListItem(evpSpeakers, setEvpSpeakers, i, e.target.value)}
                        placeholder='e.g. "Brando Benifei, MEP (S&D, IMCO)"' />
                      {evpSpeakers.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(evpSpeakers, setEvpSpeakers, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(evpSpeakers, setEvpSpeakers, 20)}>{t('docGen.wizard.addSpeaker')}</button>
                </div>
                <div className="doc-generator__form-group">
                  <label>{t('docGen.wizard.agendaPoints')}</label>
                  {evpAgenda.map((a, i) => (
                    <div key={i} className="doc-generator__list-item">
                      <input type="text" value={a}
                        onChange={(e) => updateListItem(evpAgenda, setEvpAgenda, i, e.target.value)} />
                      {evpAgenda.length > 1 && (
                        <button type="button" className="doc-generator__remove-btn"
                          onClick={() => removeListItem(evpAgenda, setEvpAgenda, i)}>×</button>
                      )}
                    </div>
                  ))}
                  <button type="button" className="doc-generator__add-btn"
                    onClick={() => addListItem(evpAgenda, setEvpAgenda, 12)}>{t('docGen.wizard.addAgendaPoint')}</button>
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.registrationUrl')}</label>
                    <input type="text" value={evpRegistrationUrl} onChange={(e) => setEvpRegistrationUrl(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.contactInfo')}</label>
                    <input type="text" value={evpContactInfo} onChange={(e) => setEvpContactInfo(e.target.value)} />
                  </div>
                </div>
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.format')}</label>
                    <select value={evpFormat} onChange={(e) => setEvpFormat(e.target.value as typeof evpFormat)}>
                      <option value="a4_portrait">{t('docGen.wizard.formatA4Portrait')}</option>
                      <option value="a4_landscape">{t('docGen.wizard.formatA4Landscape')}</option>
                      <option value="a3_portrait">{t('docGen.wizard.formatA3Portrait')}</option>
                      <option value="instagram_square">{t('docGen.wizard.formatInstagramSquare')}</option>
                      <option value="linkedin_landscape">{t('docGen.wizard.formatLinkedinLandscape')}</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.accentColour')}</label>
                    <input type="color" value={evpAccentColor} onChange={(e) => setEvpAccentColor(e.target.value)} />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>{t('docGen.wizard.language')}</label>
                    <select value={evpLanguage} onChange={(e) => setEvpLanguage(e.target.value as 'en' | 'fr')}>
                      <option value="en">{t('docGen.wizard.langEnglish')}</option>
                      <option value="fr">{t('docGen.wizard.langFrancais')}</option>
                    </select>
                  </div>
                </div>
                <BrandingPanel
                  org={brOrgName} setOrg={setBrOrgName}
                  url={brOrgUrl} setUrl={setBrOrgUrl}
                  email={brContactEmail} setEmail={setBrContactEmail}
                  phone={brContactPhone} setPhone={setBrContactPhone}
                  transparencyId={brTransparencyId} setTransparencyId={setBrTransparencyId}
                  logoStorageId={brLogoStorageId} setLogoStorageId={setBrLogoStorageId}
                  logoFilename={brLogoFilename} setLogoFilename={setBrLogoFilename}
                  logoUploading={brLogoUploading} logoError={brLogoError}
                  onLogoUpload={handleBrLogoUpload}
                />
                <StyleRefPanel
                  storageId={styleRefStorageId} setStorageId={setStyleRefStorageId}
                  filename={styleRefFilename} setFilename={setStyleRefFilename}
                  uploading={styleRefUploading} error={styleRefError}
                  onUpload={handleStyleRefUpload}
                  hint="Upload an example poster (PDF/PNG) for Brubru to mirror its layout."
                />
              </div>
            </div>
          )}

          {/* Step 3: Generating */}
          {step === 3 && (
            <div className="doc-generator__step doc-generator__step--generating">
              {isGenerating ? (
                <>
                  <Icon path={mdiLoading} size={3} spin color="#0066cc" />
                  <h3>{t('docGen.generatingTitle')}</h3>
                  <p>{t('docGen.generatingBody', { kind: selectedType ? t(KIND_KEY[selectedType]) : '' })}</p>
                </>
              ) : error ? (
                <>
                  <h3>{t('docGen.generationFailed')}</h3>
                  <p className="doc-generator__error">{error}</p>
                  <button
                    className="doc-generator__btn doc-generator__btn--primary"
                    onClick={() => { setError(null); handleGenerate(); }}
                  >
                    {t('docGen.tryAgain')}
                  </button>
                </>
              ) : (
                <>
                  <h3>{t('docGen.readyToGenerate')}</h3>
                  <p>{t('docGen.clickBelow')}</p>
                  <button
                    className="doc-generator__btn doc-generator__btn--primary"
                    onClick={handleGenerate}
                  >
                    {t('docGen.generateDocument')}
                  </button>
                </>
              )}
            </div>
          )}

          {/* Step 4: Preview */}
          {step === 4 && generatedDocument && (
            <div className="doc-generator__step doc-generator__step--preview">
              <div className="doc-generator__preview-header">
                <h3>{generatedDocument.title}</h3>
                <div className="doc-generator__preview-meta">
                  <span>{t('docGen.wordCount', { n: generatedDocument.word_count })}</span>
                </div>
              </div>
              <div className="doc-generator__preview-actions">
                <button className="doc-generator__preview-btn" onClick={handleCopy}>
                  <Icon path={mdiContentCopy} size={0.8} />
                  {t('docGen.copy')}
                </button>
                <button className="doc-generator__preview-btn" disabled>
                  <Icon path={mdiDownload} size={0.8} />
                  {t('docGen.exportSoon')}
                </button>
              </div>
              <div
                className="doc-generator__preview-content doc-generator__markdown"
                dangerouslySetInnerHTML={{ __html: marked.parse(generatedDocument.content) as string }}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="doc-generator__footer">
          {step > 1 && step < 4 && (
            <button
              className="doc-generator__btn doc-generator__btn--secondary"
              onClick={() => setStep(step - 1)}
              disabled={isGenerating}
            >
              <Icon path={mdiArrowLeft} size={0.8} />
              {t('docGen.back')}
            </button>
          )}

          <div className="doc-generator__footer-spacer" />

          {step < 3 && (
            <button
              className="doc-generator__btn doc-generator__btn--primary"
              onClick={() => setStep(step + 1)}
              disabled={!isStepValid()}
            >
              {step === 2 ? t('docGen.reviewAndGenerate') : t('docGen.next')}
              <Icon path={mdiArrowRight} size={0.8} />
            </button>
          )}

          {step === 4 && (
            <button
              className="doc-generator__btn doc-generator__btn--primary"
              onClick={() => { onDocumentGenerated(); handleClose(); }}
            >
              <Icon path={mdiCheck} size={0.8} />
              {t('docGen.done')}
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(wizardContent, document.body);
};
