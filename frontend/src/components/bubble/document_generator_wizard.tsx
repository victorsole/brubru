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
type DocumentType = 'position_paper' | 'mep_briefing' | 'talking_points';
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
];

export const DocumentGeneratorWizard = ({
  isOpen,
  onClose,
  onDocumentGenerated,
}: DocumentGeneratorWizardProps) => {
  const { token, user } = useAuth();

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
                {DOCUMENT_TYPES.map((type) => (
                  <div
                    key={type.id}
                    className={`doc-generator__type-card ${selectedType === type.id ? 'selected' : ''}`}
                    onClick={() => setSelectedType(type.id)}
                    style={{ borderColor: selectedType === type.id ? type.color : undefined }}
                  >
                    <Icon path={type.icon} size={2} color={type.color} />
                    <h4>{type.title}</h4>
                    <p>{type.description}</p>
                  </div>
                ))}
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
