// frontend/src/pages/terms_page.tsx
import { Link } from 'react-router-dom';
import './policy_pages.css';

export const TermsPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">Terms of Service</h1>

        <section className="policy-page__section">
          <p className="policy-page__intro">
            <strong>Effective Date:</strong> November 2025<br />
            <strong>Last Updated:</strong> November 2025
          </p>
          <p>
            These Terms of Service ("Terms") govern your access to and use of Brubru
            (https://brubru.beresol.eu), operated by Beresol BV ("we," "us," or "our").
            By accessing or using Brubru, you agree to be bound by these Terms.
          </p>
          <p className="policy-page__note">
            <strong>Important:</strong> These Terms contain an arbitration clause and class action waiver
            that affect your legal rights. Please read them carefully.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>1. Acceptance of Terms</h2>
          <p>
            By creating an account, accessing, or using any part of Brubru, you agree to these Terms,
            our <Link to="/privacy" className="policy-page__link">Privacy Policy</Link>, and our
            <Link to="/cookies" className="policy-page__link"> Cookie Policy</Link>.
            If you do not agree, do not use our services.
          </p>
          <p>
            You must be at least 16 years old to use Brubru. By using our service, you represent
            that you meet this age requirement and have the legal capacity to enter into these Terms.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>2. Description of Service</h2>
          <p>
            Brubru is an AI-powered strategic advocacy assistant for EU policy professionals.
            Our services include:
          </p>
          <ul>
            <li>AI chat interface for EU policy analysis</li>
            <li>Amendator: Legislative amendment authoring tool</li>
            <li>My EU Bubble: RSS feed aggregation from EU institutional sources</li>
            <li>EU Law Comply: Compliance gap analysis</li>
            <li>Legislative tracking and monitoring</li>
          </ul>
          <p>
            We reserve the right to modify, suspend, or discontinue any aspect of the service
            at any time, with or without notice.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>3. Account Registration and Security</h2>

          <h3>3.1 Account Creation</h3>
          <p>
            You must create an account to use Brubru. You agree to:
          </p>
          <ul>
            <li>Provide accurate, complete, and current information</li>
            <li>Maintain and promptly update your account information</li>
            <li>Keep your password secure and confidential</li>
            <li>Notify us immediately of any unauthorized access</li>
          </ul>

          <h3>3.2 Account Responsibility</h3>
          <p>
            You are responsible for all activities that occur under your account.
            We are not liable for any loss or damage arising from your failure to
            maintain account security.
          </p>

          <h3>3.3 Account Termination</h3>
          <p>
            We reserve the right to suspend or terminate your account at any time for:
          </p>
          <ul>
            <li>Violation of these Terms</li>
            <li>Fraudulent or illegal activity</li>
            <li>Non-payment of fees</li>
            <li>Abuse of our services or infrastructure</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>4. Subscription Plans and Billing</h2>

          <h3>4.1 Subscription Plans</h3>
          <p>
            Brubru offers a modular pricing model:
          </p>
          <ul>
            <li><strong>Free Trial:</strong> 14-day access to any plan</li>
            <li><strong>Individual Modules:</strong> from &euro;19/month (Amendator, AI Chat, My EU Bubble, EU Law Comply, Tenderator)</li>
            <li><strong>Bundles:</strong> from &euro;39/month (Starter, Advocate, Professional)</li>
            <li><strong>EP Plan:</strong> &euro;49/month (for verified APAs and MEPs)</li>
          </ul>
          <p>
            See our <Link to="/subscription" className="policy-page__link">Subscription page</Link> for current pricing and features.
            All prices are indicative and may be updated; the Subscription page reflects the most current pricing.
          </p>

          <h3>4.2 Payment Terms</h3>
          <ul>
            <li>Subscriptions are billed in advance on a monthly or annual basis</li>
            <li>All fees are in Euros (EUR) and exclude applicable taxes (VAT)</li>
            <li>Payment is processed through Stripe</li>
            <li>You authorize us to charge your payment method on each billing cycle</li>
          </ul>

          <h3>4.3 Refunds</h3>
          <p>
            We offer a <strong>14-day money-back guarantee</strong> for first-time paid subscriptions.
            To request a refund, contact us at <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a>
            within 14 days of your initial payment.
          </p>
          <p>
            Renewal payments are non-refundable. Annual subscriptions are non-refundable after 14 days.
          </p>

          <h3>4.4 Plan Changes and Cancellations</h3>
          <ul>
            <li>You can upgrade your plan at any time; the new rate applies immediately with prorated billing</li>
            <li>Downgrades take effect at the end of your current billing period</li>
            <li>You can cancel your subscription at any time; access continues until the end of the billing period</li>
            <li>No refunds are provided for partial billing periods</li>
          </ul>

          <h3>4.5 Price Changes</h3>
          <p>
            We may change our pricing with 30 days' notice. Price changes do not affect your current
            billing period but apply to subsequent renewals. If you do not agree to a price increase,
            you may cancel your subscription.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>5. Acceptable Use Policy</h2>

          <h3>5.1 Permitted Use</h3>
          <p>
            You may use Brubru only for lawful purposes and in accordance with these Terms.
          </p>

          <h3>5.2 Prohibited Activities</h3>
          <p>You agree NOT to:</p>
          <ul>
            <li>Use the service for any illegal purpose or in violation of any laws</li>
            <li>Attempt to gain unauthorized access to our systems or other users' accounts</li>
            <li>Interfere with or disrupt our services or servers</li>
            <li>Use automated scripts or bots to access the service (except via our official API)</li>
            <li>Scrape or harvest data from our service</li>
            <li>Reverse engineer, decompile, or disassemble any part of our software</li>
            <li>Share your account credentials with others</li>
            <li>Use the service to generate spam, phishing content, or malware</li>
            <li>Resell or redistribute our services without written permission</li>
            <li>Upload malicious code, viruses, or harmful content</li>
            <li>Violate the intellectual property rights of others</li>
            <li>Harass, abuse, or harm others</li>
          </ul>

          <h3>5.3 Rate Limits and Fair Use</h3>
          <p>
            We enforce rate limits and usage quotas based on your subscription tier.
            Excessive use that degrades service quality for other users may result in throttling or suspension.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>6. User Content and Intellectual Property</h2>

          <h3>6.1 Your Content</h3>
          <p>
            You retain ownership of all content you create, upload, or submit to Brubru
            (chat messages, amendments, documents). By uploading content, you grant us a
            limited, worldwide, non-exclusive license to:
          </p>
          <ul>
            <li>Store and process your content to provide the service</li>
            <li>Use anonymized, aggregated data for analytics and service improvement</li>
            <li>Display your content to you and authorized users of your account</li>
          </ul>
          <p>
            We do not claim ownership of your content and will not share it with third parties
            except as described in our <Link to="/privacy" className="policy-page__link">Privacy Policy</Link>.
          </p>

          <h3>6.2 Our Intellectual Property</h3>
          <p>
            Brubru and all related software, trademarks, logos, and content are the exclusive
            property of Beresol BV. You may not:
          </p>
          <ul>
            <li>Copy, modify, or create derivative works of our software</li>
            <li>Use our trademarks without written permission</li>
            <li>Remove copyright or proprietary notices</li>
          </ul>

          <h3>6.3 Third-Party Content</h3>
          <p>
            Brubru aggregates content from EU institutional sources (EUR-Lex, OEIL, European Parliament, etc.).
            This content remains the property of the respective institutions and is used in accordance with
            their terms and applicable EU law.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>7. AI-Generated Content</h2>

          <h3>7.1 No Warranties on Accuracy</h3>
          <p>
            Brubru uses AI models (Anthropic Claude, OpenAI GPT-4) to generate responses.
            AI-generated content may contain errors, inaccuracies, or outdated information.
            <strong> We do not warrant the accuracy, completeness, or reliability of AI outputs.</strong>
          </p>

          <h3>7.2 Not Legal or Professional Advice</h3>
          <p>
            Brubru provides informational tools and does not constitute legal, or financial advice.
          </p>

          <h3>7.3 User Responsibility</h3>
          <p>
            You are solely responsible for:
          </p>
          <ul>
            <li>Verifying the accuracy of AI-generated content</li>
            <li>Reviewing and editing amendments before submission</li>
            <li>Ensuring compliance with applicable laws and regulations</li>
            <li>Any decisions made based on information from Brubru</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>8. Service Availability and Support</h2>

          <h3>8.1 Uptime</h3>
          <p>
            We strive for high availability but do not guarantee uninterrupted access.
            Scheduled maintenance will be announced in advance when possible.
          </p>
          <ul>
            <li><strong>Free Trial:</strong> Best-effort availability, no SLA</li>
            <li><strong>Individual Modules and Bundles (Starter, Advocate, EP Plan):</strong> 99% uptime target (excluding scheduled maintenance)</li>
            <li><strong>Professional:</strong> 99.9% uptime SLA with service credits for violations</li>
          </ul>

          <h3>8.2 Support</h3>
          <ul>
            <li><strong>Free Trial:</strong> Community support and documentation</li>
            <li><strong>Individual Modules and Bundles (Starter, Advocate, EP Plan):</strong> Email support with 48-hour response time (business days)</li>
            <li><strong>Professional:</strong> Dedicated support with 24-hour response time</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>9. Limitation of Liability</h2>

          <h3>9.1 Disclaimer of Warranties</h3>
          <p>
            BRUBRU IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND,
            EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY,
            FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.
          </p>

          <h3>9.2 Limitation of Damages</h3>
          <p>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, BERESOL BV SHALL NOT BE LIABLE FOR:
          </p>
          <ul>
            <li>Indirect, incidental, special, consequential, or punitive damages</li>
            <li>Loss of profits, revenue, data, or business opportunities</li>
            <li>Service interruptions or data loss</li>
            <li>Errors or inaccuracies in AI-generated content</li>
            <li>Actions taken in reliance on our service</li>
          </ul>
          <p>
            OUR TOTAL LIABILITY SHALL NOT EXCEED THE AMOUNT YOU PAID US IN THE 12 MONTHS
            PRECEDING THE CLAIM, OR €100, WHICHEVER IS GREATER.
          </p>

          <h3>9.3 Exceptions</h3>
          <p>
            Nothing in these Terms excludes or limits our liability for:
          </p>
          <ul>
            <li>Death or personal injury caused by our negligence</li>
            <li>Fraud or fraudulent misrepresentation</li>
            <li>Any liability that cannot be excluded under applicable law</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>10. Indemnification</h2>
          <p>
            You agree to indemnify, defend, and hold harmless Beresol BV, its officers, directors,
            employees, and agents from any claims, liabilities, damages, and expenses (including
            legal fees) arising from:
          </p>
          <ul>
            <li>Your use of Brubru</li>
            <li>Your violation of these Terms</li>
            <li>Your violation of any third-party rights</li>
            <li>Your content or conduct</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>11. Dispute Resolution</h2>

          <h3>11.1 Informal Resolution</h3>
          <p>
            Before filing a claim, you agree to contact us at
            <a href="mailto:hello@beresol.eu" className="policy-page__link"> hello@beresol.eu</a>
            {' '}to resolve the dispute informally. We will attempt to resolve within 60 days.
          </p>

          <h3>11.2 Governing Law</h3>
          <p>
            These Terms are governed by the laws of the Netherlands and the European Union,
            without regard to conflict of law principles.
          </p>

          <h3>11.3 Jurisdiction</h3>
          <p>
            Any disputes arising from these Terms shall be subject to the exclusive jurisdiction
            of the courts of Brussels, Belgium.
          </p>

          <h3>11.4 Class Action Waiver</h3>
          <p>
            You agree to resolve disputes individually and waive any right to participate in
            class actions or class-wide arbitration.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>12. Changes to Terms</h2>
          <p>
            We may update these Terms from time to time. Material changes will be communicated via:
          </p>
          <ul>
            <li>Email notification to your registered address</li>
            <li>Prominent notice on our website</li>
            <li>In-app notification</li>
          </ul>
          <p>
            Changes will take effect 30 days after notice. Continued use after the effective date
            constitutes acceptance. If you do not agree to the new Terms, you must stop using Brubru
            and may cancel your subscription.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>13. Termination</h2>

          <h3>13.1 By You</h3>
          <p>
            You may terminate your account at any time by deleting it in Profile → Account Settings.
            Paid subscriptions continue until the end of the billing period (no refunds).
          </p>

          <h3>13.2 By Us</h3>
          <p>
            We may suspend or terminate your account immediately if you:
          </p>
          <ul>
            <li>Violate these Terms</li>
            <li>Engage in fraudulent or illegal activity</li>
            <li>Fail to pay fees</li>
            <li>Abuse our service or infrastructure</li>
          </ul>

          <h3>13.3 Effect of Termination</h3>
          <p>
            Upon termination:
          </p>
          <ul>
            <li>Your access to Brubru is immediately revoked</li>
            <li>We will delete your account data within 90 days (backup retention)</li>
            <li>You may export your data before termination (if account is accessible)</li>
            <li>Outstanding fees remain due and payable</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>14. Miscellaneous</h2>

          <h3>14.1 Entire Agreement</h3>
          <p>
            These Terms, together with our Privacy Policy and Cookie Policy, constitute the
            entire agreement between you and Beresol BV.
          </p>

          <h3>14.2 Severability</h3>
          <p>
            If any provision of these Terms is found to be unenforceable, the remaining provisions
            will remain in effect.
          </p>

          <h3>14.3 Waiver</h3>
          <p>
            Our failure to enforce any provision does not waive our right to enforce it later.
          </p>

          <h3>14.4 Assignment</h3>
          <p>
            You may not assign these Terms without our written consent. We may assign our rights
            and obligations to any successor entity (e.g., in a merger or acquisition).
          </p>

          <h3>14.5 Force Majeure</h3>
          <p>
            We are not liable for delays or failures caused by events beyond our reasonable control
            (natural disasters, war, pandemics, government actions, internet outages, etc.).
          </p>
        </section>

        <section className="policy-page__section">
          <h2>15. Contact Information</h2>
          <p>
            For questions about these Terms:
          </p>
          <p>
            <strong>Email:</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a><br />
            <strong>Subject:</strong> "Terms of Service Inquiry"
          </p>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: November 2025</p>
          <p>
            <Link to="/about" className="policy-page__link">About</Link> ·
            <Link to="/privacy" className="policy-page__link">Privacy Policy</Link> ·
            <Link to="/cookies" className="policy-page__link">Cookies</Link> ·
            <Link to="/subprocessors" className="policy-page__link">Subprocessors</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
