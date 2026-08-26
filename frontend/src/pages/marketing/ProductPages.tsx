import React from 'react';
import { ArrowRightIcon } from 'lucide-react';
import { ButtonLink } from '../../shared/ui/Button';
import { MarketingLayout, Section } from '../../components/marketing/MarketingLayout';

function ProductCta() {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-ink-800 bg-ink-900/60 p-5 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-[14px] text-chalk-dim">Free plan includes 700 leads/month — no credit card required.</p>
      <ButtonLink to="/signup" size="sm">
        Get started
        <ArrowRightIcon className="h-4 w-4" />
      </ButtonLink>
    </div>
  );
}

export function AiQualificationPage() {
  return (
    <MarketingLayout
      eyebrow="Product"
      title="AI Qualification"
      intro="Every lead Crawlio finds or imports is scored automatically, so your team works the businesses most likely to convert first instead of guessing from a flat list.">
      <Section title="How scoring works">
        <p>
          Each lead is scored on data completeness and quality signals — a verified email and phone number, a real
          website, a complete address, and industry match — into a 0–100 score. Leads that fail basic contact
          validation (no working email or phone) are filtered out before they ever reach your list.
        </p>
      </Section>
      <Section title="Where it shows up">
        <p>
          Scores appear directly in the Lead Center table and on every lead's detail view, and the CRM view splits
          your qualified leads into "with website" and "without website" groups so outreach can be tailored
          accordingly.
        </p>
      </Section>
      <Section title="Plan availability">
        <p>
          Scoring runs on every plan. Pro and Enterprise unlock AI-assisted contact enrichment during discovery, which
          improves the data feeding the score for a higher share of fully-qualified leads per search.
        </p>
      </Section>
      <ProductCta />
    </MarketingLayout>
  );
}

export function EmailOutreachPage() {
  return (
    <MarketingLayout
      eyebrow="Product"
      title="Email Outreach"
      intro="Connect a Gmail account, let the agent draft and send outreach to your qualified leads, and keep every reply in one threaded conversation view.">
      <Section title="How it works">
        <p>
          Connect your Gmail account once via OAuth. From there, Crawlio's Email Agent can draft outreach for a
          selected lead or batch of leads, you review and approve before anything sends, and replies land back in a
          per-lead conversation thread inside the app — not scattered across your inbox.
        </p>
      </Section>
      <Section title="Daily sending limits">
        <p>
          To protect deliverability and your Gmail account's sending reputation, Pro and Enterprise plans carry a
          daily send quota. The remaining quota for the day is always visible before you send.
        </p>
      </Section>
      <Section title="What's next">
        <p>
          Email Outreach is actively being hardened ahead of general availability — if you hit a rough edge, tell us
          at <a href="mailto:support@crawlio.io" className="text-signal hover:underline">support@crawlio.io</a> and
          we'll prioritize it.
        </p>
      </Section>
      <ProductCta />
    </MarketingLayout>
  );
}

export function WhatsAppAutomationPage() {
  return (
    <MarketingLayout
      eyebrow="Product"
      title="WhatsApp Automation"
      intro="Reach leads on WhatsApp through the official Meta Cloud API, with the same review-before-send workflow as email outreach.">
      <Section title="How it works">
        <p>
          Connect a WhatsApp Business phone number through Meta's Embedded Signup, then send template or
          conversational messages to leads with a phone number on file directly from their lead record. Conversations
          thread per lead, the same way email does.
        </p>
      </Section>
      <Section title="Availability">
        <p>
          WhatsApp Automation is a Pro and Enterprise feature, gated by a daily message quota per plan to keep
          sending patterns compliant with WhatsApp's own platform policies.
        </p>
      </Section>
      <ProductCta />
    </MarketingLayout>
  );
}

export function AutomationBuilderPage() {
  return (
    <MarketingLayout
      eyebrow="Product"
      title="Automation Builder"
      intro="The place Email and WhatsApp outreach, lead scoring, and your CRM view come together into one working pipeline instead of separate tools.">
      <Section title="What it brings together">
        <p>
          The Automation workspace combines the Email Agent, WhatsApp Agent, and a built-in CRM view of your
          AI-qualified leads (split into "with website" and "without website" segments) in one page — so moving a
          lead from "just discovered" to "actively being followed up with" doesn't mean switching tools.
        </p>
      </Section>
      <Section title="Where this is headed">
        <p>
          Today, outreach steps are triggered per-lead or per-batch with a human reviewing before send. A fully
          rules-based, multi-step automation builder (e.g. "if no reply in 3 days, send WhatsApp follow-up") is on
          the roadmap — this page will be updated as that ships.
        </p>
      </Section>
      <ProductCta />
    </MarketingLayout>
  );
}
