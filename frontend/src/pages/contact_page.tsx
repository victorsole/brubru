// frontend/src/pages/contact_page.tsx
import './policy_pages.css';

export const ContactPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">Contact Brubru</h1>

        <section className="policy-page__section">
          <h2>Get in Touch</h2>
          <p>
            We're here to help. Whether you have questions about our platform, need technical support,
            or want to explore custom enterprise solutions, our team is ready to assist you.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>General Inquiries</h2>
          <div className="policy-page__contact-box">
            <p><strong>Email:</strong> <a href="mailto:helloberesol@gmail.com" className="policy-page__link">helloberesol@gmail.com</a></p>
            <p><strong>Website:</strong> <a href="https://brubru.beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">brubru.beresol.eu</a></p>
            <p><strong>Company:</strong> <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">Beresol BV</a></p>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>Support</h2>

          <div className="policy-page__feature">
            <h3>White Tier (Free) Users</h3>
            <p>
              Community support is available through our documentation and FAQ resources.
              For technical issues, please email us with your account details and a description
              of the problem you're experiencing.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>Yellow Tier (Professional) Users</h3>
            <p>
              Email support with 48-hour response time during business days.
              Send your inquiries to <a href="mailto:helloberesol@gmail.com" className="policy-page__link">helloberesol@gmail.com</a>
              with "Yellow Support" in the subject line.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>Blue Tier (Enterprise) Users</h3>
            <p>
              Priority 24/7 support with dedicated account manager.
              Contact your assigned account manager directly or email
              <a href="mailto:helloberesol@gmail.com" className="policy-page__link"> helloberesol@gmail.com</a>
              with "Blue Priority" in the subject line for immediate escalation.
            </p>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>Sales & Enterprise Solutions</h2>
          <p>
            Interested in Brubru for your organization? We offer customized enterprise packages,
            multi-user accounts, white-label solutions, and dedicated training sessions.
          </p>
          <p>
            <strong>Contact our sales team:</strong> <a href="mailto:helloberesol@gmail.com?subject=Enterprise%20Inquiry" className="policy-page__link">helloberesol@gmail.com</a>
          </p>
          <p className="policy-page__note">
            Please include information about your organization, team size, and specific requirements
            in your initial email so we can provide you with a tailored proposal.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Partnership & Integration Opportunities</h2>
          <p>
            We're always interested in collaborating with complementary services, EU institutional partners,
            and technology providers. If you'd like to explore partnership opportunities or API integration,
            please reach out to us.
          </p>
          <p>
            <strong>Partnership inquiries:</strong> <a href="mailto:helloberesol@gmail.com?subject=Partnership%20Opportunity" className="policy-page__link">helloberesol@gmail.com</a>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Press & Media</h2>
          <p>
            For press inquiries, media kits, interview requests, or information about Brubru for publication,
            please contact our communications team.
          </p>
          <p>
            <strong>Press contact:</strong> <a href="mailto:helloberesol@gmail.com?subject=Press%20Inquiry" className="policy-page__link">helloberesol@gmail.com</a>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Data Protection & Privacy Inquiries</h2>
          <p>
            Questions about how we handle your data, GDPR rights, or privacy concerns?
            We take data protection seriously and are committed to transparency.
          </p>
          <p>
            <strong>Privacy inquiries:</strong> <a href="mailto:helloberesol@gmail.com?subject=Privacy%20Inquiry" className="policy-page__link">helloberesol@gmail.com</a>
          </p>
          <p>
            For detailed information about our data practices, please review our <a href="/privacy" className="policy-page__link">Privacy Policy</a>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Bug Reports & Feature Requests</h2>
          <p>
            Found a bug or have an idea for a new feature? We value your feedback and use it to
            continuously improve Brubru.
          </p>
          <p>
            <strong>Feedback email:</strong> <a href="mailto:helloberesol@gmail.com?subject=Bug%20Report" className="policy-page__link">helloberesol@gmail.com</a>
          </p>
          <p className="policy-page__note">
            Please include as much detail as possible: steps to reproduce (for bugs), expected vs. actual behavior,
            screenshots if applicable, and your subscription tier.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Business Address</h2>
          <p>
            <strong>Beresol BV</strong><br />
            Brussels, Belgium<br />
            European Union
          </p>
          <p className="policy-page__note">
            Brubru is a registered trademark of Beresol BV, registered with the
            European Union Intellectual Property Office (EUIPO).
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Response Times</h2>
          <ul>
            <li><strong>General Inquiries:</strong> 3-5 business days</li>
            <li><strong>Yellow Tier Support:</strong> 48 hours (business days)</li>
            <li><strong>Blue Tier Support:</strong> 24/7 priority response</li>
            <li><strong>Enterprise Sales:</strong> 2 business days</li>
            <li><strong>Privacy/GDPR Requests:</strong> 30 days (as required by GDPR)</li>
          </ul>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: November 2025</p>
        </div>
      </div>
    </div>
  );
};
