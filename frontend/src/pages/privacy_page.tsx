// frontend/src/pages/privacy_page.tsx
import { Link } from 'react-router-dom';
import './policy_pages.css';

export const PrivacyPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">Privacy Policy</h1>

        <section className="policy-page__section">
          <p className="policy-page__intro">
            <strong>Effective Date:</strong> November 2025<br />
            <strong>Last Updated:</strong> 6 November 2026
          </p>
          <p>
            Beresol BV ("we," "us," or "our") operates Brubru (https://brubru.beresol.eu), an AI-powered
            strategic advocacy assistant for EU policy professionals. This Privacy Policy explains how we
            collect, use, disclose, and safeguard your information when you use our service.
          </p>
          <p>
            We are committed to protecting your privacy and complying with the General Data Protection
            Regulation (GDPR) and other applicable data protection laws.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>1. Data Controller</h2>
          <p>
            <strong>Beresol BV</strong><br />
            Apeldoorn, Netherlands<br />
            European Union<br />
            Email: <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>2. Information We Collect</h2>

          <h3>2.1 Information You Provide Directly</h3>
          <ul>
            <li><strong>Account Information:</strong> Email address, full name, organization, country</li>
            <li><strong>Authentication:</strong> Password (encrypted), OAuth tokens from Google or LinkedIn</li>
            <li><strong>Profile Settings:</strong> Policy interests, language preference, timezone, background preferences</li>
            <li><strong>Payment Information:</strong> Billing details processed securely through Stripe (we do not store credit card numbers)</li>
            <li><strong>User Content:</strong> Chat messages, amendments, uploaded documents (PDF, DOCX), saved RSS entries, feedback submissions</li>
          </ul>

          <h3>2.2 Information Collected Automatically</h3>
          <ul>
            <li><strong>Usage Data:</strong> Pages visited, features used, time spent, amendment creation/editing activity</li>
            <li><strong>Technical Data:</strong> IP address, browser type, device information, operating system</li>
            <li><strong>Authentication Logs:</strong> Login timestamps, session duration</li>
            <li><strong>API Usage:</strong> Number of AI requests, tokens consumed, rate limiting data</li>
          </ul>

          <h3>2.3 Information from Third Parties</h3>
          <ul>
            <li><strong>OAuth Providers:</strong> Profile information from Google or LinkedIn when you use social login</li>
            <li><strong>Payment Processor:</strong> Subscription status and payment events from Stripe</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>3. How We Use Your Information</h2>
          <p>We process your personal data for the following purposes:</p>

          <h3>3.1 Service Provision (Legal Basis: Contract Performance)</h3>
          <ul>
            <li>Provide access to Brubru's features (chat, amendator, compliance checking, RSS feeds)</li>
            <li>Process AI requests and generate responses</li>
            <li>Store and retrieve your amendments, documents, and chat history</li>
            <li>Manage subscriptions and billing</li>
            <li>Provide customer support</li>
          </ul>

          <h3>3.2 Service Improvement (Legal Basis: Legitimate Interest)</h3>
          <ul>
            <li>Analyze usage patterns to improve features and user experience</li>
            <li>Develop new features based on user needs</li>
            <li>Conduct research and analytics</li>
            <li>Train and improve AI models (anonymized data only)</li>
          </ul>

          <h3>3.3 Communication (Legal Basis: Consent / Legitimate Interest)</h3>
          <ul>
            <li>Send service-related notifications (downtime, updates, policy changes)</li>
            <li>Respond to your inquiries and support requests</li>
            <li>Send marketing communications (with your consent, opt-out available)</li>
          </ul>

          <h3>3.4 Legal Compliance (Legal Basis: Legal Obligation)</h3>
          <ul>
            <li>Comply with applicable laws and regulations</li>
            <li>Respond to legal requests and prevent fraud</li>
            <li>Enforce our Terms of Service</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>4. How We Share Your Information</h2>
          <p>We do not sell your personal data. We may share your information with:</p>

          <h3>4.1 Service Providers (Data Processors)</h3>
          <p>
            We use third-party service providers to help us operate our business. These providers
            process data only on our behalf and are contractually obligated to protect your data.
          </p>
          <ul>
            <li><strong>Supabase:</strong> Database hosting, authentication, file storage (EU/US servers)</li>
            <li><strong>Anthropic:</strong> AI model processing for chat responses (US)</li>
            <li><strong>OpenAI:</strong> Backup AI model processing (US)</li>
            <li><strong>Hugging Face:</strong> Specialized legal AI models and embeddings (EU/US)</li>
            <li><strong>Stripe:</strong> Payment processing (EU/US)</li>
            <li><strong>Railway:</strong> Backend infrastructure hosting (EU/US)</li>
            <li><strong>SiteGround:</strong> Frontend hosting and CDN (EU)</li>
            <li><strong>Google Cloud:</strong> Optional translation services (EU/US)</li>
          </ul>
          <p>
            For a complete list of subprocessors, see our <Link to="/subprocessors" className="policy-page__link">Subprocessors page</Link>.
          </p>

          <h3>4.2 Legal Requirements</h3>
          <p>
            We may disclose your information if required by law, court order, or government regulation,
            or if we believe disclosure is necessary to protect our rights or the safety of users.
          </p>

          <h3>4.3 Business Transfers</h3>
          <p>
            In the event of a merger, acquisition, or sale of assets, your information may be transferred
            to the acquiring entity. We will notify you via email if this occurs.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>5. AI Processing and Your Content</h2>

          <h3>5.1 Chat Messages</h3>
          <p>
            Your chat messages are sent to AI providers (Anthropic Claude, OpenAI GPT-4) for processing.
            These providers use your messages solely to generate responses and do not train their models
            on your data (per our contracts with them). However, content sent to AI APIs leaves the EU.
          </p>

          <h3>5.2 Documents</h3>
          <p>
            Documents you upload for compliance checking or chat context are processed on our secure backend
            servers (Railway, EU/US). Text extracted from documents may be sent to AI APIs for analysis.
          </p>

          <h3>5.3 Amendments</h3>
          <p>
            Amendments created using the Amendator are stored in our EU-based database and are not shared
            with third parties unless you explicitly export and share them.
          </p>
        </section>

        <section className="policy-page__section" id="public-data">
          <h2>6. Public Data About People Who Are Not Our Users (GDPR Article 14)</h2>
          <p>
            Brubru is built from the public record of the European Union. Some of that record names people
            who have not given their data to us: Members of the European Parliament, Commissioners and EU
            officials, interest representatives, people listed under EU sanctions, and others who take part
            in public EU decision-making. Because we did not collect this data from you directly, Article 14
            of the GDPR asks us to tell you what we hold, why, and what you can do about it. Contacting each
            person individually would require a disproportionate effort, so this notice is the measure we take
            under Article 14(5)(b) GDPR.
          </p>

          <h3>6.1 Who is responsible</h3>
          <p>
            Beresol BV is the controller of this data (contact details in section 1). We have not appointed a
            Data Protection Officer; write to <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a> with
            the subject line "GDPR Request".
          </p>

          <h3>6.2 What we hold, and where it comes from</h3>
          <ul>
            <li><strong>Members of the European Parliament:</strong> name, political group, country, committee roles, roll-call votes, tabled amendments, reports and opinions, parliamentary questions, declared meetings with interest representatives, and contributions to public committee and plenary debates. Sources: the European Parliament's websites and open data, and public vote records derived from them.</li>
            <li><strong>Commissioners, Commission staff and other EU officials:</strong> name, role and service as published in the EU Who is Who directory and the institutions' organisation charts, and meetings with interest representatives as published by the European Commission.</li>
            <li><strong>Interest representatives:</strong> the organisation data and the contact details published in the EU Transparency Register, and the news items that registered organisations publish on their own websites.</li>
            <li><strong>People listed under EU restrictive measures (sanctions):</strong> the identifying details and reasons for listing published in the Official Journal of the European Union.</li>
            <li><strong>Recipients of EU funds and public contracts:</strong> names of beneficiaries and contractors as published by the European Commission (Financial Transparency System, Funding and Tenders Portal) and by TED.</li>
            <li><strong>Public social media posts:</strong> posts published on public accounts of EU institutions, their members and officials, and EU-affairs journalists (Bluesky, Mastodon, YouTube and X). We do not collect posts from Instagram, LinkedIn or TikTok.</li>
            <li><strong>Authors and parties named in official documents:</strong> for example rapporteurs, speakers, authors of institutional studies, and parties named in published court judgments.</li>
            <li><strong>Professionals we plan to contact:</strong> where we prepare a Brubru profile for a professional before inviting them, we use their name, organisation, role and public professional profile.</li>
          </ul>
          <p>
            All of these sources are publicly accessible. We do not buy personal data and we do not collect it
            from private sources.
          </p>

          <h3>6.3 Why we use it, and on what legal basis</h3>
          <ul>
            <li><strong>Showing users the EU public record</strong> (who proposed, voted, met, said or decided what) in Brubru's products and API, so that EU decision-making is easier to follow and to scrutinise. Legal basis: our legitimate interests and those of our users in knowing and analysing public institutional activity (Article 6(1)(f) GDPR).</li>
            <li><strong>Sending EU news alerts to organisations</strong> listed in the EU Transparency Register, at the contact address they published there, on topics matching their declared policy interests. Legal basis: legitimate interests (Article 6(1)(f) GDPR). Every alert carries an unsubscribe link.</li>
            <li><strong>Preparing an invitation</strong> for a professional we plan to contact. Legal basis: legitimate interests (Article 6(1)(f) GDPR).</li>
          </ul>
          <p>
            Votes, political group membership and public statements can reveal political opinions. We process
            that data only where the person has manifestly made it public in their public role (Article 9(2)(e)
            GDPR), and only in that role. We make no decision about any person based solely on automated
            processing with legal or similarly significant effects (Article 22 GDPR). Brubru computes analyses
            such as group voting patterns and forecasts of legislative outcomes; these describe public roles and
            public decisions, not anyone's private life.
          </p>

          <h3>6.4 Who sees it</h3>
          <p>
            Brubru's users and API customers, who see the public record as Brubru presents it; our service
            providers (hosting and AI processing, see section 4 and the <Link to="/subprocessors" className="policy-page__link">Subprocessors page</Link>),
            which process it only on our behalf. Some of these providers are outside the EEA; section 10 explains
            how those transfers are protected.
          </p>

          <h3>6.5 How long we keep it</h3>
          <ul>
            <li><strong>Public-record data:</strong> as part of our archive of the EU public record, for as long as it remains relevant to that record. When the source corrects or removes an item, we correct or remove it too.</li>
            <li><strong>Contact details from the Transparency Register:</strong> while the organisation is registered, and no longer once it unsubscribes or objects.</li>
            <li><strong>Profiles prepared for an invitation:</strong> deleted on request, or if the invitation is declined.</li>
          </ul>

          <h3>6.6 Your rights</h3>
          <p>
            You have the right of access, rectification and erasure, the right to restrict processing, and the
            right to object at any time to processing based on our legitimate interests (Article 21 GDPR); for
            news alerts, unsubscribing is enough. Where data is part of the public record we may keep the record
            itself (for example a roll-call vote), but we will correct anything that does not match its official
            source. You can also lodge a complaint with the data protection authority of your EU country, or with
            the Dutch Autoriteit Persoonsgegevens, the authority where we are established
            (<a href="https://www.autoriteitpersoonsgegevens.nl" target="_blank" rel="noopener noreferrer" className="policy-page__link">autoriteitpersoonsgegevens.nl</a>).
          </p>
        </section>

        <section className="policy-page__section">
          <h2>7. Data Retention</h2>
          <p>We retain your personal data as follows:</p>
          <ul>
            <li><strong>Account Data:</strong> Until you delete your account, plus 90 days for backup recovery</li>
            <li><strong>Chat History:</strong> Indefinitely until you delete conversations</li>
            <li><strong>Amendments:</strong> Indefinitely until you delete them</li>
            <li><strong>Uploaded Documents:</strong> Until you delete them, or when your subscription lapses (30-day grace period)</li>
            <li><strong>Payment Records:</strong> 7 years (legal requirement for accounting)</li>
            <li><strong>Usage Logs:</strong> 90 days for operational purposes</li>
            <li><strong>Marketing Communications:</strong> Until you unsubscribe, plus 3 years for compliance</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>8. Your Rights Under GDPR</h2>
          <p>As an EU data subject, you have the following rights:</p>

          <h3>8.1 Right of Access</h3>
          <p>You can request a copy of all personal data we hold about you.</p>

          <h3>8.2 Right to Rectification</h3>
          <p>You can update your account information in your Profile settings.</p>

          <h3>8.3 Right to Erasure ("Right to be Forgotten")</h3>
          <p>You can delete your account at any time in Profile → Account Settings → Delete Account.</p>

          <h3>8.4 Right to Restrict Processing</h3>
          <p>You can request that we limit how we use your data.</p>

          <h3>8.5 Right to Data Portability</h3>
          <p>You can export your data (chat history, amendments, documents) in machine-readable formats (JSON, XML).</p>

          <h3>8.6 Right to Object</h3>
          <p>You can object to processing based on legitimate interest, including marketing communications.</p>

          <h3>8.7 Right to Withdraw Consent</h3>
          <p>Where processing is based on consent, you can withdraw it at any time.</p>

          <h3>8.8 Right to Lodge a Complaint</h3>
          <p>
            You have the right to lodge a complaint with your national data protection authority
            if you believe we have violated GDPR. Beresol BV is established in the Netherlands, so the authority
            that supervises us is the Dutch Autoriteit Persoonsgegevens
            (<a href="https://www.autoriteitpersoonsgegevens.nl" target="_blank" rel="noopener noreferrer" className="policy-page__link">autoriteitpersoonsgegevens.nl</a>).
            You may also complain in the EU country where you live or work; in Belgium, this is the Data Protection Authority
            (<a href="https://www.dataprotectionauthority.be" target="_blank" rel="noopener noreferrer" className="policy-page__link">dataprotectionauthority.be</a>).
          </p>

          <p className="policy-page__note">
            To exercise any of these rights, contact us at <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a>.
            We will respond within 30 days.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>9. Data Security</h2>
          <p>We implement industry-standard security measures to protect your data:</p>
          <ul>
            <li><strong>Encryption in Transit:</strong> HTTPS/TLS 1.3+ for all communications</li>
            <li><strong>Encryption at Rest:</strong> Database encryption via Supabase</li>
            <li><strong>Authentication:</strong> JWT tokens with secure storage, bcrypt password hashing</li>
            <li><strong>Access Control:</strong> Role-based access control (RBAC), principle of least privilege</li>
            <li><strong>Infrastructure Security:</strong> Firewalls, regular security updates, DDoS protection</li>
            <li><strong>Monitoring:</strong> Real-time error tracking, suspicious activity detection</li>
          </ul>
          <p className="policy-page__note">
            Despite our best efforts, no method of transmission over the internet is 100% secure.
            We cannot guarantee absolute security of your data.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>10. International Data Transfers</h2>
          <p>
            Your data may be transferred to and processed in countries outside the European Economic Area (EEA),
            specifically the United States, where some of our service providers are located (Anthropic, OpenAI, Stripe).
          </p>
          <p>
            We ensure adequate protection for these transfers through:
          </p>
          <ul>
            <li><strong>Standard Contractual Clauses (SCCs):</strong> EU-approved data transfer agreements with processors</li>
            <li><strong>Adequacy Decisions:</strong> Transfers to countries deemed adequate by the European Commission</li>
            <li><strong>Data Processing Agreements (DPAs):</strong> Binding contracts with all processors</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>11. Cookies and Tracking</h2>
          <p>
            We use cookies and similar tracking technologies to enhance your experience.
            For detailed information, see our <Link to="/cookies" className="policy-page__link">Cookie Policy</Link>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>12. Children's Privacy</h2>
          <p>
            Brubru is not intended for individuals under the age of 16. We do not knowingly collect
            personal data from children. If you believe a child has provided us with personal data,
            please contact us immediately, and we will delete it.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>13. Changes to This Privacy Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify you of material changes
            by email (to your registered address) and by posting a notice on our website at least 30 days
            before the changes take effect.
          </p>
          <p>
            Your continued use of Brubru after the effective date constitutes acceptance of the updated policy.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>14. Contact Information</h2>
          <p>
            For privacy-related questions, concerns, or to exercise your rights under GDPR:
          </p>
          <p>
            <strong>Email:</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a><br />
            <strong>Subject Line:</strong> "Privacy Inquiry" or "GDPR Request"
          </p>
          <p>
            We will respond to all legitimate requests within 30 days.
          </p>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: 6 November 2026</p>
          <p>
            <Link to="/about" className="policy-page__link">About</Link> ·
            <Link to="/terms" className="policy-page__link">Terms of Service</Link> ·
            <Link to="/cookies" className="policy-page__link">Cookies</Link> ·
            <Link to="/subprocessors" className="policy-page__link">Subprocessors</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
