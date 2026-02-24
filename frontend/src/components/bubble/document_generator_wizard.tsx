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

import { useState } from 'react';
import { createPortal } from 'react-dom';
import Icon from '@mdi/react';
import {
  mdiFileDocumentOutline,
  mdiAccountTie,
  mdiMessageText,
  mdiScriptTextOutline,
  mdiCommentQuestionOutline,
  mdiArrowLeft,
  mdiArrowRight,
  mdiCheck,
  mdiLoading,
  mdiContentCopy,
  mdiDownload,
} from '@mdi/js';
import { marked } from 'marked';
import { useAuth } from '../../hooks/use_auth';
import './document_generator_wizard.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
type DocumentType = 'position_paper' | 'mep_briefing' | 'talking_points' | 'resolution' | 'ep_question';
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
}

// Document type cards for selection
const DOCUMENT_TYPES = [
  {
    id: 'position_paper' as DocumentType,
    title: 'Position Paper',
    description: 'Formal advocacy document with executive summary, detailed analysis, and specific recommendations',
    icon: mdiFileDocumentOutline,
    color: '#2e7d32',
  },
  {
    id: 'mep_briefing' as DocumentType,
    title: 'MEP Briefing Note',
    description: 'Concise briefing for engaging with a specific Member of the European Parliament',
    icon: mdiAccountTie,
    color: '#1565c0',
  },
  {
    id: 'talking_points' as DocumentType,
    title: 'Talking Points',
    description: 'Structured talking points and Q&A preparation for advocacy meetings',
    icon: mdiMessageText,
    color: '#7b1fa2',
  },
  {
    id: 'resolution' as DocumentType,
    title: 'EP Resolution',
    description: 'European Parliament resolution with having regards, whereas recitals, and numbered resolution points',
    icon: mdiScriptTextOutline,
    color: '#b91c1c',
  },
  {
    id: 'ep_question' as DocumentType,
    title: 'EP Written Question',
    description: 'Written parliamentary question from the EP to the European Commission, Council, or VP/HR',
    icon: mdiCommentQuestionOutline,
    color: '#0693e3',
  },
];

export const DocumentGeneratorWizard = ({
  isOpen,
  onClose,
  onDocumentGenerated,
}: DocumentGeneratorWizardProps) => {
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
      if (selectedType === 'resolution') {
        return resolutionTopic.trim() && contextDescription.trim();
      }
      if (selectedType === 'ep_question') {
        return epqTopic.trim() && epqContext.trim();
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
          <h2>Generate Document with AI</h2>
          <button className="doc-generator__close" onClick={handleClose}>×</button>
        </div>

        {/* Progress */}
        <div className="doc-generator__progress">
          <div className={`doc-generator__progress-step ${step >= 1 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">1</span>
            <span className="doc-generator__progress-label">Type</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 2 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">2</span>
            <span className="doc-generator__progress-label">Details</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 3 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">3</span>
            <span className="doc-generator__progress-label">Generate</span>
          </div>
          <div className={`doc-generator__progress-step ${step >= 4 ? 'active' : ''}`}>
            <span className="doc-generator__progress-number">4</span>
            <span className="doc-generator__progress-label">Preview</span>
          </div>
        </div>

        {/* Content */}
        <div className="doc-generator__content">
          {/* Step 1: Select Document Type */}
          {step === 1 && (
            <div className="doc-generator__step">
              <h3>What would you like to generate?</h3>
              <div className="doc-generator__type-grid">
                {DOCUMENT_TYPES.map((type) => {
                  const isLocked = (type.id === 'resolution' || type.id === 'ep_question') && !canUseResolution;
                  return (
                    <div
                      key={type.id}
                      className={`doc-generator__type-card ${selectedType === type.id ? 'selected' : ''} ${isLocked ? 'doc-generator__type-card--locked' : ''}`}
                      onClick={() => !isLocked && setSelectedType(type.id)}
                      style={{ borderColor: selectedType === type.id ? type.color : undefined }}
                    >
                      <Icon path={type.icon} size={2} color={isLocked ? '#9ca3af' : type.color} />
                      <h4>{type.title}</h4>
                      <p>{isLocked ? 'Subscription required' : type.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 2: Form based on document type */}
          {step === 2 && selectedType === 'position_paper' && (
            <div className="doc-generator__step">
              <h3>Position Paper Details</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>Legislation Title *</label>
                  <input
                    type="text"
                    value={legislationTitle}
                    onChange={(e) => setLegislationTitle(e.target.value)}
                    placeholder="e.g., Artificial Intelligence Act"
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Procedure Reference</label>
                    <input
                      type="text"
                      value={procedureReference}
                      onChange={(e) => setProcedureReference(e.target.value)}
                      placeholder="e.g., 2021/0106(COD)"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Your Position *</label>
                    <select value={position} onChange={(e) => setPosition(e.target.value as PositionStance)}>
                      <option value="support">Support</option>
                      <option value="support_with_amendments">Support with Amendments</option>
                      <option value="oppose">Oppose</option>
                      <option value="neutral">Neutral / Monitoring</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Key Asks (1-5) *</label>
                  {keyAsks.map((ask, index) => (
                    <div key={index} className="doc-generator__key-ask">
                      <input
                        type="text"
                        value={ask.summary}
                        onChange={(e) => updateKeyAsk(index, 'summary', e.target.value)}
                        placeholder={`Ask ${index + 1}: e.g., Extend SME exemption threshold`}
                      />
                      <input
                        type="text"
                        value={ask.article_reference || ''}
                        onChange={(e) => updateKeyAsk(index, 'article_reference', e.target.value)}
                        placeholder="Article reference (optional)"
                        className="doc-generator__key-ask-ref"
                      />
                      {keyAsks.length > 1 && (
                        <button type="button" onClick={() => removeKeyAsk(index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyAsks.length < 5 && (
                    <button type="button" onClick={addKeyAsk} className="doc-generator__add-btn">+ Add another ask</button>
                  )}
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Organisation Name *</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder="Your organisation"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Organisation Type *</label>
                    <select value={organisationType} onChange={(e) => setOrganisationType(e.target.value as OrganisationType)}>
                      <option value="company">Company</option>
                      <option value="industry_association">Industry Association</option>
                      <option value="ngo">NGO</option>
                      <option value="think_tank">Think Tank</option>
                      <option value="law_firm">Law Firm</option>
                      <option value="consultancy">Consultancy</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Document Tone</label>
                  <select value={tone} onChange={(e) => setTone(e.target.value as DocumentTone)}>
                    <option value="constructive">Constructive</option>
                    <option value="critical">Critical</option>
                    <option value="technical">Technical</option>
                    <option value="diplomatic">Diplomatic</option>
                  </select>
                </div>

                <div className="doc-generator__form-group">
                  <label>Sector Impact (optional)</label>
                  <textarea
                    value={sectorImpact}
                    onChange={(e) => setSectorImpact(e.target.value)}
                    placeholder="Describe how this legislation affects your sector..."
                    rows={3}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'mep_briefing' && (
            <div className="doc-generator__step">
              <h3>MEP Briefing Details</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>MEP Name *</label>
                    <input
                      type="text"
                      value={mepName}
                      onChange={(e) => setMepName(e.target.value)}
                      placeholder="e.g., Brando Benifei"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Political Group</label>
                    <select value={politicalGroup} onChange={(e) => setPoliticalGroup(e.target.value)}>
                      <option value="">Select...</option>
                      <option value="EPP">EPP (European People's Party)</option>
                      <option value="S&D">S&D (Socialists & Democrats)</option>
                      <option value="Renew">Renew Europe</option>
                      <option value="Greens/EFA">Greens/EFA</option>
                      <option value="ECR">ECR</option>
                      <option value="ID">ID</option>
                      <option value="The Left">The Left</option>
                      <option value="NI">Non-Inscrits</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Nationality</label>
                    <input
                      type="text"
                      value={nationality}
                      onChange={(e) => setNationality(e.target.value)}
                      placeholder="e.g., Italian"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Committee</label>
                    <input
                      type="text"
                      value={committee}
                      onChange={(e) => setCommittee(e.target.value)}
                      placeholder="e.g., IMCO, ITRE"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Legislation Title *</label>
                  <input
                    type="text"
                    value={legislationTitle}
                    onChange={(e) => setLegislationTitle(e.target.value)}
                    placeholder="e.g., Artificial Intelligence Act"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>The Ask (What specific action do you want?) *</label>
                  <input
                    type="text"
                    value={theAsk}
                    onChange={(e) => setTheAsk(e.target.value)}
                    placeholder="e.g., Support Amendment 123 on SME exemptions"
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Your Position *</label>
                    <select value={position} onChange={(e) => setPosition(e.target.value as PositionStance)}>
                      <option value="support">Support</option>
                      <option value="support_with_amendments">Support with Amendments</option>
                      <option value="oppose">Oppose</option>
                      <option value="neutral">Neutral / Monitoring</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Organisation Name *</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder="Your organisation"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Key Points (1-5)</label>
                  {keyPoints.map((point, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={point}
                        onChange={(e) => updateListItem(keyPoints, setKeyPoints, index, e.target.value)}
                        placeholder={`Key point ${index + 1}`}
                      />
                      {keyPoints.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyPoints, setKeyPoints, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyPoints.length < 5 && (
                    <button type="button" onClick={() => addListItem(keyPoints, setKeyPoints, 5)} className="doc-generator__add-btn">+ Add point</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>National Angle (relevance to their country)</label>
                  <textarea
                    value={nationalAngle}
                    onChange={(e) => setNationalAngle(e.target.value)}
                    placeholder="How does this affect their member state or constituency?"
                    rows={2}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'talking_points' && (
            <div className="doc-generator__step">
              <h3>Talking Points Details</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Meeting With *</label>
                    <input
                      type="text"
                      value={meetingWith}
                      onChange={(e) => setMeetingWith(e.target.value)}
                      placeholder="e.g., Commissioner Vestager"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Institution</label>
                    <select value={meetingInstitution} onChange={(e) => setMeetingInstitution(e.target.value)}>
                      <option value="">Select...</option>
                      <option value="European Commission">European Commission</option>
                      <option value="European Parliament">European Parliament</option>
                      <option value="Council of the EU">Council of the EU</option>
                      <option value="Permanent Representation">Permanent Representation</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Meeting Purpose *</label>
                  <input
                    type="text"
                    value={meetingPurpose}
                    onChange={(e) => setMeetingPurpose(e.target.value)}
                    placeholder="e.g., Discuss SME provisions in the AI Act"
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Topic *</label>
                    <input
                      type="text"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g., Artificial Intelligence Act"
                    />
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Organisation Name *</label>
                    <input
                      type="text"
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      placeholder="Your organisation"
                    />
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Key Messages (1-5) *</label>
                  {keyMessages.map((msg, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={msg}
                        onChange={(e) => updateListItem(keyMessages, setKeyMessages, index, e.target.value)}
                        placeholder={`Message ${index + 1}`}
                      />
                      {keyMessages.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyMessages, setKeyMessages, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyMessages.length < 5 && (
                    <button type="button" onClick={() => addListItem(keyMessages, setKeyMessages, 5)} className="doc-generator__add-btn">+ Add message</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>Key Asks for the Meeting (1-3)</label>
                  {meetingKeyAsks.map((ask, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={ask}
                        onChange={(e) => updateListItem(meetingKeyAsks, setMeetingKeyAsks, index, e.target.value)}
                        placeholder={`Ask ${index + 1}`}
                      />
                      {meetingKeyAsks.length > 1 && (
                        <button type="button" onClick={() => removeListItem(meetingKeyAsks, setMeetingKeyAsks, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {meetingKeyAsks.length < 3 && (
                    <button type="button" onClick={() => addListItem(meetingKeyAsks, setMeetingKeyAsks, 3)} className="doc-generator__add-btn">+ Add ask</button>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'resolution' && (
            <div className="doc-generator__step">
              <h3>EP Resolution Details</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>Resolution Topic / Title *</label>
                  <input
                    type="text"
                    value={resolutionTopic}
                    onChange={(e) => setResolutionTopic(e.target.value)}
                    placeholder="e.g., The situation of human rights in Iran"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>Procedure Reference</label>
                  <input
                    type="text"
                    value={procedureReference}
                    onChange={(e) => setProcedureReference(e.target.value)}
                    placeholder="e.g., 2025/2500(RSP)"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>Context Description (for "whereas" recitals) *</label>
                  <textarea
                    value={contextDescription}
                    onChange={(e) => setContextDescription(e.target.value)}
                    placeholder="Describe the situation, background facts, and context that should form the basis of the recitals..."
                    rows={4}
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>Key Demands (up to 10)</label>
                  <p className="doc-generator__form-hint">
                    Optional. Each demand becomes a numbered resolution point. Leave empty and the AI will infer from the context.
                  </p>
                  {keyDemands.map((demand, index) => (
                    <div key={index} className="doc-generator__list-item">
                      <input
                        type="text"
                        value={demand}
                        onChange={(e) => updateListItem(keyDemands, setKeyDemands, index, e.target.value)}
                        placeholder={`Demand ${index + 1}: e.g., Ban the export of surveillance technology`}
                      />
                      {keyDemands.length > 1 && (
                        <button type="button" onClick={() => removeListItem(keyDemands, setKeyDemands, index)} className="doc-generator__remove-btn">×</button>
                      )}
                    </div>
                  ))}
                  {keyDemands.length < 10 && (
                    <button type="button" onClick={() => addListItem(keyDemands, setKeyDemands, 10)} className="doc-generator__add-btn">+ Add demand</button>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>Additional References (optional)</label>
                  <p className="doc-generator__form-hint">
                    Specific treaties, regulations, or prior resolutions to cite. The AI will also infer references automatically.
                  </p>
                  {additionalReferences.length === 0 ? (
                    <button type="button" onClick={() => setAdditionalReferences([''])} className="doc-generator__add-btn">+ Add reference</button>
                  ) : (
                    <>
                      {additionalReferences.map((ref, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={ref}
                            onChange={(e) => updateListItem(additionalReferences, setAdditionalReferences, index, e.target.value)}
                            placeholder={`e.g., Regulation (EU) 2024/1689 (AI Act)`}
                          />
                          <button type="button" onClick={() => {
                            const updated = additionalReferences.filter((_, i) => i !== index);
                            setAdditionalReferences(updated);
                          }} className="doc-generator__remove-btn">×</button>
                        </div>
                      ))}
                      {additionalReferences.length < 5 && (
                        <button type="button" onClick={() => addListItem(additionalReferences, setAdditionalReferences, 5)} className="doc-generator__add-btn">+ Add reference</button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 2 && selectedType === 'ep_question' && (
            <div className="doc-generator__step">
              <h3>EP Written Question Details</h3>
              <div className="doc-generator__form">
                <div className="doc-generator__form-group">
                  <label>Topic / Title *</label>
                  <input
                    type="text"
                    value={epqTopic}
                    onChange={(e) => setEpqTopic(e.target.value)}
                    placeholder="e.g., Security risks associated with flush car door handles"
                    maxLength={200}
                  />
                  <span className="doc-generator__char-count">{epqTopic.length}/200</span>
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Addressee *</label>
                    <select value={epqAddressee} onChange={(e) => setEpqAddressee(e.target.value as 'commission' | 'council' | 'vp_hr')}>
                      <option value="commission">European Commission</option>
                      <option value="council">Council of the EU</option>
                      <option value="vp_hr">VP/HR (Foreign Affairs)</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Question Type</label>
                    <select value={epqQuestionType} onChange={(e) => setEpqQuestionType(e.target.value as 'standard' | 'priority')}>
                      <option value="standard">Standard (E-) -- 6-week reply</option>
                      <option value="priority">Priority (P-) -- 3-week reply</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Context and Evidence *</label>
                  <p className="doc-generator__form-hint">
                    Describe the facts, concerns, and evidence you want included. The AI will structure this into 2-4 formal paragraphs citing EU legislation.
                  </p>
                  <textarea
                    value={epqContext}
                    onChange={(e) => setEpqContext(e.target.value)}
                    placeholder="e.g., Recent audit by the European Court of Auditors found that the EU is unlikely to secure sufficient critical raw materials by 2030. Continued dependency on non-EU countries, limited progress on domestic extraction..."
                    rows={5}
                  />
                </div>

                <div className="doc-generator__form-row">
                  <div className="doc-generator__form-group">
                    <label>Number of Sub-questions</label>
                    <select value={epqNumSubQuestions} onChange={(e) => setEpqNumSubQuestions(Number(e.target.value))}>
                      <option value={1}>1 sub-question</option>
                      <option value={2}>2 sub-questions</option>
                      <option value={3}>3 sub-questions</option>
                    </select>
                  </div>
                  <div className="doc-generator__form-group">
                    <label>Tone</label>
                    <select value={epqTone} onChange={(e) => setEpqTone(e.target.value as 'assertive' | 'diplomatic' | 'technical')}>
                      <option value="assertive">Assertive (direct pressure)</option>
                      <option value="diplomatic">Diplomatic (measured probing)</option>
                      <option value="technical">Technical (legal precision)</option>
                    </select>
                  </div>
                </div>

                <div className="doc-generator__form-group">
                  <label>Procedure Reference</label>
                  <input
                    type="text"
                    value={procedureReference}
                    onChange={(e) => setProcedureReference(e.target.value)}
                    placeholder="e.g., 2021/0106(COD)"
                  />
                </div>

                <div className="doc-generator__form-group">
                  <label>Legislation References (optional)</label>
                  <p className="doc-generator__form-hint">
                    Specific EU laws to cite. The AI will also infer relevant legislation from context.
                  </p>
                  {epqLegislationRefs.length === 0 ? (
                    <button type="button" onClick={() => setEpqLegislationRefs([''])} className="doc-generator__add-btn">+ Add legislation reference</button>
                  ) : (
                    <>
                      {epqLegislationRefs.map((ref, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={ref}
                            onChange={(e) => updateListItem(epqLegislationRefs, setEpqLegislationRefs, index, e.target.value)}
                            placeholder="e.g., Regulation (EU) 2021/2116"
                          />
                          <button type="button" onClick={() => {
                            const updated = epqLegislationRefs.filter((_, i) => i !== index);
                            setEpqLegislationRefs(updated);
                          }} className="doc-generator__remove-btn">x</button>
                        </div>
                      ))}
                      {epqLegislationRefs.length < 5 && (
                        <button type="button" onClick={() => addListItem(epqLegislationRefs, setEpqLegislationRefs, 5)} className="doc-generator__add-btn">+ Add reference</button>
                      )}
                    </>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>Evidence Sources (optional)</label>
                  <p className="doc-generator__form-hint">
                    News articles, audit reports, or other evidence to footnote.
                  </p>
                  {epqSources.length === 0 ? (
                    <button type="button" onClick={() => setEpqSources([''])} className="doc-generator__add-btn">+ Add source</button>
                  ) : (
                    <>
                      {epqSources.map((src, index) => (
                        <div key={index} className="doc-generator__list-item">
                          <input
                            type="text"
                            value={src}
                            onChange={(e) => updateListItem(epqSources, setEpqSources, index, e.target.value)}
                            placeholder="e.g., European Court of Auditors report on critical minerals, 2025"
                          />
                          <button type="button" onClick={() => {
                            const updated = epqSources.filter((_, i) => i !== index);
                            setEpqSources(updated);
                          }} className="doc-generator__remove-btn">x</button>
                        </div>
                      ))}
                      {epqSources.length < 5 && (
                        <button type="button" onClick={() => addListItem(epqSources, setEpqSources, 5)} className="doc-generator__add-btn">+ Add source</button>
                      )}
                    </>
                  )}
                </div>

                <div className="doc-generator__form-group">
                  <label>Policy Area</label>
                  <select value={epqPolicyArea} onChange={(e) => setEpqPolicyArea(e.target.value)}>
                    <option value="">Select (optional)...</option>
                    <option value="Digital">Digital / AI / Data</option>
                    <option value="Trade">Trade / International</option>
                    <option value="Industry">Industry / Competitiveness</option>
                    <option value="Environment">Environment / Climate</option>
                    <option value="Agriculture">Agriculture / Food</option>
                    <option value="Transport">Transport / Safety</option>
                    <option value="Justice">Justice / Rule of Law</option>
                    <option value="Health">Health / Pharmaceuticals</option>
                    <option value="Foreign Affairs">Foreign Affairs / Security</option>
                    <option value="Energy">Energy</option>
                    <option value="Employment">Employment / Social</option>
                    <option value="Internal Market">Internal Market</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Generating */}
          {step === 3 && (
            <div className="doc-generator__step doc-generator__step--generating">
              {isGenerating ? (
                <>
                  <Icon path={mdiLoading} size={3} spin color="#0066cc" />
                  <h3>Generating your document...</h3>
                  <p>This may take a moment. Brubru is crafting your {selectedType?.replace('_', ' ')}.</p>
                </>
              ) : error ? (
                <>
                  <h3>Generation Failed</h3>
                  <p className="doc-generator__error">{error}</p>
                  <button
                    className="doc-generator__btn doc-generator__btn--primary"
                    onClick={() => { setError(null); handleGenerate(); }}
                  >
                    Try Again
                  </button>
                </>
              ) : (
                <>
                  <h3>Ready to Generate</h3>
                  <p>Click the button below to generate your document.</p>
                  <button
                    className="doc-generator__btn doc-generator__btn--primary"
                    onClick={handleGenerate}
                  >
                    Generate Document
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
                  <span>{generatedDocument.word_count} words</span>
                </div>
              </div>
              <div className="doc-generator__preview-actions">
                <button className="doc-generator__preview-btn" onClick={handleCopy}>
                  <Icon path={mdiContentCopy} size={0.8} />
                  Copy
                </button>
                <button className="doc-generator__preview-btn" disabled>
                  <Icon path={mdiDownload} size={0.8} />
                  Export (coming soon)
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
              Back
            </button>
          )}

          <div className="doc-generator__footer-spacer" />

          {step < 3 && (
            <button
              className="doc-generator__btn doc-generator__btn--primary"
              onClick={() => setStep(step + 1)}
              disabled={!isStepValid()}
            >
              {step === 2 ? 'Review & Generate' : 'Next'}
              <Icon path={mdiArrowRight} size={0.8} />
            </button>
          )}

          {step === 4 && (
            <button
              className="doc-generator__btn doc-generator__btn--primary"
              onClick={() => { onDocumentGenerated(); handleClose(); }}
            >
              <Icon path={mdiCheck} size={0.8} />
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(wizardContent, document.body);
};
