import React from 'react';
import { MarketingLayout, Section } from '../../components/marketing/MarketingLayout';

export function AboutPage() {
  return (
    <MarketingLayout
      eyebrow="Company"
      title="About Crawlio"
      intro="Crawlio is an AI-powered lead automation platform: it finds real local businesses, scores them, and runs email and WhatsApp follow-up so revenue teams spend their time closing instead of prospecting.">
      <Section title="What we build">
        <p>
          Lead discovery pulls from Google Maps, OpenStreetMap, and public business directories — never fabricated
          data. Every result is validated for a real contact channel (email or phone) before it reaches your CRM.
          From there, the Email and WhatsApp agents handle outreach with a human reviewing before anything sends.
        </p>
      </Section>
      <Section title="Who's behind it">
        <p>
          Crawlio is built and operated by{' '}
          <a
            href="mailto:hello@aiaceonesolutions.com"
            className="text-signal hover:underline">
            Aceone Solutions
          </a>
          . We're a small team shipping fast — if something's rough around the edges, that's a "not yet" and not a
          "no."
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function CareersPage() {
  return (
    <MarketingLayout
      eyebrow="Company"
      title="Careers"
      intro="We're not running a formal hiring process right now, but we're always open to hearing from people who want to build this with us.">
      <Section>
        <p>
          If you're interested in working on lead discovery, outreach automation, or the platform/infra side of a
          product like this, send a short note and anything you've built to{' '}
          <a href="mailto:careers@crawlio.io" className="text-signal hover:underline">careers@crawlio.io</a>. We read
          everything, even without an open role posted.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function BlogPage() {
  return (
    <MarketingLayout
      eyebrow="Company"
      title="Blog"
      intro="We haven't published our first post yet — the team's time has gone into the product first.">
      <Section>
        <p>
          When we do start writing, it'll be about what we're actually learning building lead discovery and outreach
          automation — not filler content. Check the{' '}
          <a href="/changelog" className="text-signal hover:underline">changelog</a> in the meantime for what's
          shipping.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function ContactSalesPage() {
  return (
    <MarketingLayout
      eyebrow="Company"
      title="Contact sales"
      intro="Looking at Crawlio for a team, or want an Enterprise plan with a higher lead volume and seat count? We'd like to hear about what you're trying to do.">
      <Section title="Reach us">
        <p>
          Email{' '}
          <a href="mailto:sales@crawlio.io" className="text-signal hover:underline">sales@crawlio.io</a> with a
          little about your team size and what you're trying to automate, and we'll reply directly — no scheduling
          maze first.
        </p>
      </Section>
      <Section title="Not ready to talk yet?">
        <p>
          The Free plan (700 leads/month, no card required) and self-serve Pro plan cover most teams without a sales
          conversation at all — you can start from the signup page any time.
        </p>
      </Section>
    </MarketingLayout>
  );
}
