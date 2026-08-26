import React from 'react';
import { MarketingLayout, Section } from '../../components/marketing/MarketingLayout';

function LastUpdated() {
  return <p className="text-[12.5px] text-chalk-faint">Last updated: August 2026</p>;
}

export function PrivacyPage() {
  return (
    <MarketingLayout eyebrow="Legal" title="Privacy Policy">
      <LastUpdated />
      <Section title="What we collect">
        <p>
          Account data (name, email, workspace details) comes from your sign-in provider (Clerk). Lead data you
          discover or import — business names, emails, phone numbers, addresses, and website/social links — is
          sourced from public sources (Google Maps, OpenStreetMap, public business directories) or entered by you
          directly, never fabricated.
        </p>
      </Section>
      <Section title="How we use it">
        <p>
          Your account and lead data is used to operate the product for you: showing your leads, running outreach
          you initiate, and scoring/enrichment to make that data more useful. We don't sell your data or your leads'
          data to third parties.
        </p>
      </Section>
      <Section title="Who else sees it">
        <p>
          Service providers we use to run Crawlio can process data on our behalf: Clerk (authentication), Brevo
          (transactional email delivery), Google (if you connect Gmail for outreach), Meta (if you connect WhatsApp
          Business), and Mistral AI (for AI-assisted compose/scoring features). Each only receives what's needed to
          perform its function.
        </p>
      </Section>
      <Section title="Data deletion">
        <p>
          You can delete individual leads or your entire lead list from within the app at any time. To request full
          workspace or account deletion, email{' '}
          <a href="mailto:privacy@crawlio.io" className="text-signal hover:underline">privacy@crawlio.io</a> — we'll
          confirm once it's done.
        </p>
      </Section>
      <Section title="Questions">
        <p>
          Reach us at <a href="mailto:privacy@crawlio.io" className="text-signal hover:underline">privacy@crawlio.io</a>.
          This policy may be updated as the product changes; material changes will be reflected here with a new date.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function TermsPage() {
  return (
    <MarketingLayout eyebrow="Legal" title="Terms of Service">
      <LastUpdated />
      <Section title="Using Crawlio">
        <p>
          Crawlio is provided to help you find, qualify, and reach out to business leads. You're responsible for
          how you use outreach features (email and WhatsApp) — that means complying with applicable
          anti-spam law (e.g. CAN-SPAM, GDPR) and WhatsApp's own platform policies for any messages you send through
          the product.
        </p>
      </Section>
      <Section title="Plans and limits">
        <p>
          Free, Pro, and Enterprise plans carry different lead-discovery, seat, and daily-send limits, shown in your
          workspace at all times. We may adjust plan limits going forward; existing customers will be notified of
          material changes affecting their plan.
        </p>
      </Section>
      <Section title="Acceptable use">
        <p>
          Don't use Crawlio to harvest data for resale as a standalone dataset, to harass or defraud the businesses
          in your lead list, or to send outreach that misrepresents who it's from.
        </p>
      </Section>
      <Section title="Availability">
        <p>
          We aim for reliable uptime but don't currently guarantee a formal SLA outside an Enterprise agreement. See
          the <a href="/status" className="text-signal hover:underline">status page</a> for current service state.
        </p>
      </Section>
      <Section title="Contact">
        <p>
          Questions about these terms: <a href="mailto:support@crawlio.io" className="text-signal hover:underline">support@crawlio.io</a>.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function DpaPage() {
  return (
    <MarketingLayout
      eyebrow="Legal"
      title="Data Processing Agreement"
      intro="If your organization needs a signed DPA to use Crawlio (common for GDPR-covered teams), we're glad to put one in place.">
      <Section title="What it covers">
        <p>
          A DPA sets out how Crawlio processes personal data on your behalf as a data processor — the categories of
          data involved, the subprocessors listed on our{' '}
          <a href="/privacy" className="text-signal hover:underline">Privacy Policy</a>, and the security and
          deletion commitments that apply to it.
        </p>
      </Section>
      <Section title="Requesting one">
        <p>
          Email <a href="mailto:privacy@crawlio.io" className="text-signal hover:underline">privacy@crawlio.io</a>{' '}
          with your workspace name and we'll send a DPA for signature — this is currently handled per-request rather
          than a self-serve click-through, so an Enterprise plan isn't required to ask.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function SecurityPage() {
  return (
    <MarketingLayout eyebrow="Legal" title="Security">
      <Section title="Authentication">
        <p>
          Sign-in is handled by Clerk rather than a homegrown password system, and every API request is verified
          against a signed session token. Admin-panel access uses a separate, restricted login.
        </p>
      </Section>
      <Section title="Data storage">
        <p>
          Application data is stored in a managed Postgres database with encryption in transit (TLS) for all traffic
          between your browser, the app, and our services. We're actively working through hardening connected
          third-party credentials (e.g. Gmail/WhatsApp connections) further at rest.
        </p>
      </Section>
      <Section title="Reporting an issue">
        <p>
          If you find a security issue, please email{' '}
          <a href="mailto:security@crawlio.io" className="text-signal hover:underline">security@crawlio.io</a>{' '}
          directly rather than filing it publicly — we respond to every report.
        </p>
      </Section>
    </MarketingLayout>
  );
}
