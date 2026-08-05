import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { UsageMeter } from '../../../shared/ui/UsageMeter';
import { useSession } from '../../../contexts/SessionContext';
import { planById } from '../../../data/plans';
import { formatQuota, planLabel } from '../../../utils/plan';
import { BrandingPanel } from '../components/BrandingPanel';
import { SSOSettings } from '../components/SSOSettings';
import { AccountManagerCard } from '../components/AccountManagerCard';

export function Settings() {
  const { user } = useSession();
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
          <div>
            <h3 id="plan-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
              Plan &amp; billing
            </h3>
            <p className="mt-1.5 text-[13.5px] text-chalk-dim">
              You&rsquo;re on <span className="text-chalk">{planLabel(workspace.plan)}</span> — {plan.leadQuota},{' '}
              {plan.seats.toLowerCase()}. Contact your account manager for contract changes.
            </p>
          </div>

          <div className="mt-5">
            <UsageMeter label="Leads this cycle" used={workspace.leadsUsed} quota={workspace.leadQuota} />
          </div>
        </section>

        <section aria-labelledby="enterprise-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <h3 id="enterprise-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
            Enterprise controls
          </h3>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <BrandingPanel />
            <SSOSettings />
            <AccountManagerCard />
          </div>
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
