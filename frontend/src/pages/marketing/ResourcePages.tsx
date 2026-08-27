import React from 'react';
import { CheckCircle2Icon, ExternalLinkIcon } from 'lucide-react';
import { MarketingLayout, Section } from '../../components/marketing/MarketingLayout';

export function DocsPage() {
  return (
    <MarketingLayout
      eyebrow="Resources"
      title="Docs"
      intro="A short guide to the actual workflow, until a full documentation site exists.">
      <Section title="1. Find leads">
        <p>
          From Lead Center, open "Find leads," pick a niche and a city, and set how many results you want. The
          search runs in the background — you'll see live progress while it searches Google Maps, OpenStreetMap, and
          business directories, then review and add the ones you want to your CRM.
        </p>
      </Section>
      <Section title="2. Qualify">
        <p>
          Every lead is scored automatically on data completeness. Use the AI filter in Lead Center to split your
          list into leads worth reaching out to now versus ones that need enrichment first.
        </p>
      </Section>
      <Section title="3. Reach out">
        <p>
          From the Automation page, connect a Gmail account and/or a WhatsApp Business number, then draft outreach to
          selected leads. Nothing sends without your review first.
        </p>
      </Section>
      <Section title="4. Export">
        <p>
          Both Lead Center and the CRM view have a "Download CSV" option any time you want your data outside
          Crawlio — full lead detail, no lock-in.
        </p>
      </Section>
    </MarketingLayout>
  );
}

export function ApiReferencePage() {
  const apiUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
  return (
    <MarketingLayout
      eyebrow="Resources"
      title="API reference"
      intro="The backend is a FastAPI service, which means a full interactive API reference is generated automatically from the live schema — no separate docs to keep in sync.">
      <Section title="Interactive reference">
        <p>
          Every endpoint, request/response shape, and auth requirement is browsable at{' '}
          <code className="rounded bg-ink-900 px-1.5 py-0.5 text-[13px] text-chalk">/docs</code> on the API host, and
          the raw OpenAPI schema is at{' '}
          <code className="rounded bg-ink-900 px-1.5 py-0.5 text-[13px] text-chalk">/openapi.json</code>.
        </p>
        {apiUrl && (
          <a
            href={`${apiUrl}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1.5 text-signal hover:underline">
            Open the interactive reference
            <ExternalLinkIcon className="h-3.5 w-3.5" />
          </a>
        )}
      </Section>
      <Section title="Access">
        <p>
          Public API access for your own integrations is an Enterprise-plan feature and isn't self-serve yet — email{' '}
          <a href="mailto:sales@crawlio.io" className="text-signal hover:underline">sales@crawlio.io</a> if you need
          it.
        </p>
      </Section>
    </MarketingLayout>
  );
}

const CHANGES: { date: string; items: string[] }[] = [
  {
    date: 'Recent',
    items: [
      'Plan limits (lead quota, daily send caps) are now admin-configurable without a redeploy.',
      'Fixed a bug where skipped leads disappeared from the import review screen instead of showing why they were skipped.'
    ]
  },
  {
    date: 'Earlier',
    items: [
      'Hardened lead discovery: fixed a location-filter leak that let results from the wrong city slip through, and tightened source health checks.',
      'Rebuilt discovery for worldwide coverage with a 5-layer safety system so a search either returns real, validated leads or fails clearly — never silent partial results.',
      'Ported the WhatsApp outreach agent onto the main platform.',
      'Mobile-responsive pass across the dashboard and touch-target sizing.'
    ]
  }
];

export function ChangelogPage() {
  return (
    <MarketingLayout eyebrow="Resources" title="Changelog" intro="What's shipped recently, in plain language.">
      {CHANGES.map((group) => (
        <Section key={group.date} title={group.date}>
          <ul className="space-y-2">
            {group.items.map((item) => (
              <li key={item} className="flex gap-2.5">
                <CheckCircle2Icon className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>
      ))}
    </MarketingLayout>
  );
}

export function StatusPage() {
  return (
    <MarketingLayout eyebrow="Resources" title="Status" intro="Current status of Crawlio's core services.">
      <Section>
        <div className="flex items-center gap-2.5 rounded-xl border border-emerald-400/30 bg-emerald-400/5 px-4 py-3">
          <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
          <span className="text-[14px] text-chalk">All systems operational</span>
        </div>
        <p className="mt-4">
          This page is updated manually for now — automated uptime monitoring with incident history is on the
          roadmap. If something feels down, email{' '}
          <a href="mailto:support@crawlio.io" className="text-signal hover:underline">support@crawlio.io</a> and
          we'll respond directly.
        </p>
      </Section>
    </MarketingLayout>
  );
}
