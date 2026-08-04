import React from 'react';
import { HeadphonesIcon, KeyRoundIcon, PaletteIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { UsageMeter } from '../../../shared/ui/UsageMeter';
import { Button } from '../../../shared/ui/Button';
import { useAuth } from '../../../contexts/AuthContext';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import { planById } from '../../../data/plans';
import { formatQuota, planLabel } from '../../../utils/plan';

const ENTERPRISE_CARDS = [
{ icon: PaletteIcon, title: 'Custom branding', body: 'Your logo, colours and sending domain across every touchpoint.' },
{ icon: KeyRoundIcon, title: 'SSO / SAML', body: 'Connect Okta, Entra ID or any SAML 2.0 provider. (Setup pending)' },
{ icon: HeadphonesIcon, title: 'Account manager', body: 'Ines Cardoso — ines@crawlio.io · SLA response under 2 hours.' }];


export function Settings() {
  const { user } = useAuth();
  const { openUpgrade } = useDashboardChrome();
  if (!user) return null;

  const { workspace } = user;
  const plan = planById(workspace.plan);

  return (
    <div className="mx-auto w-full max-w-[900px]">
      <PageHeader
        title="Workspace settings"
        description="Plan, quotas and workspace identity. Changes apply to every member of this tenant." />


      <div className="space-y-4">
        <section aria-labelledby="workspace-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <h3 id="workspace-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
            Workspace
          </h3>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            {[
            { k: 'Workspace name', v: workspace.name },
            { k: 'Owner', v: `${user.name} (${user.email})` },
            { k: 'Your role', v: user.role },
            { k: 'Seats', v: `${workspace.seatsUsed} / ${formatQuota(workspace.seatQuota)}` }].
            map((row) =>
            <div key={row.k}>
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint">{row.k}</dt>
                <dd className="mt-1.5 text-[14px] text-chalk">{row.v}</dd>
              </div>
            )}
          </dl>
        </section>

        <section aria-labelledby="plan-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 id="plan-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
                Plan &amp; billing
              </h3>
              <p className="mt-1.5 text-[13.5px] text-chalk-dim">
                You&rsquo;re on <span className="text-chalk">{planLabel(workspace.plan)}</span> — {plan.leadQuota},{' '}
                {plan.seats.toLowerCase()}.
              </p>
            </div>
            <Button variant="outline" onClick={openUpgrade}>Change plan</Button>
          </div>

          <div className="mt-5">
            <UsageMeter label="Leads this cycle" used={workspace.leadsUsed} quota={workspace.leadQuota} />
          </div>
        </section>

        <section aria-labelledby="enterprise-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 id="enterprise-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
              Enterprise controls
            </h3>
            <span className="rounded bg-ink-800 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-chalk-faint">
              Enterprise
            </span>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {ENTERPRISE_CARDS.map((card) =>
            <div
              key={card.title}
              title="Upgrade to Enterprise to access"
              className="rounded-xl border border-ink-850 bg-ink-950 p-4 opacity-55">

                <card.icon className="h-4 w-4 text-signal" aria-hidden="true" />
                <p className="mt-3 text-[14px] font-medium text-chalk">{card.title}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-chalk-dim">{card.body}</p>
              </div>
            )}
          </div>

          <p className="mt-5 border-t border-ink-850 pt-4 text-[13px] text-chalk-faint">
            White-label, SSO and a dedicated account manager come with Enterprise.{' '}
            <button type="button" onClick={openUpgrade} className="text-signal hover:underline">
              Talk to sales
            </button>
            .
          </p>
        </section>

        <section className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <h3 className="font-display text-[16px] font-semibold tracking-tight text-chalk">Integrations</h3>
          <p className="mt-2 text-[13.5px] text-chalk-faint">
            CRM sync, webhooks and API keys — <span className="text-chalk-dim">(Coming soon)</span>
          </p>
        </section>
      </div>
    </div>);

}
