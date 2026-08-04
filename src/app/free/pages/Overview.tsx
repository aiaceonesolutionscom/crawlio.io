import React from 'react';
import { Link } from 'react-router-dom';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis } from
'recharts';
import { ArrowRightIcon, SparklesIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { StatCard } from '../../../shared/ui/StatCard';
import { UsageMeter } from '../../../shared/ui/UsageMeter';
import { Button } from '../../../shared/ui/Button';
import { useSession } from '../../../contexts/SessionContext';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import { ACTIVITY, LEADS_OVER_TIME } from '../../../data/metrics';
import { LockedFeatureCard } from '../components/LockedFeatureCard';

export function Overview() {
  const { user } = useSession();
  const { openUpgrade } = useDashboardChrome();
  if (!user) return null;

  const { workspace } = user;
  const qualified = Math.round(workspace.leadsUsed * 0.42);

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title={`Welcome back, ${user.name.split(' ')[0]}`}
        description="Here's how your pipeline moved over the last 8 weeks."
        action={
        <Button onClick={openUpgrade}>
            Upgrade to Pro
            <ArrowRightIcon className="h-4 w-4" />
          </Button>
        } />


      <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-signal/40 bg-signal/[0.06] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <SparklesIcon className="mt-0.5 h-4 w-4 shrink-0 text-signal" aria-hidden="true" />
          <div>
            <p className="text-[14.5px] font-medium text-chalk">
              You&rsquo;ve used {workspace.leadsUsed} of {workspace.leadQuota} free leads
            </p>
            <p className="mt-1 text-[13.5px] text-chalk-dim">
              Upgrade to Pro for 5,000 leads a month, WhatsApp automation and AI reports.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={openUpgrade}>
          See plans
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total leads" value={workspace.leadsUsed.toLocaleString('en-US')} delta={{ value: '+12.4%', direction: 'up' }} note="vs last cycle" />
        <StatCard label="Qualified leads" value={qualified.toLocaleString('en-US')} delta={{ value: '+8.1%', direction: 'up' }} note="AI score ≥ 70" />
        <StatCard label="Conversion rate" value="18.6%" delta={{ value: '-1.2%', direction: 'down' }} note="reply → meeting" />
        <StatCard label="Avg. response time" value="—" note="Pro metric" muted />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <section
          aria-labelledby="leads-chart-title"
          className="rounded-2xl border border-ink-800 bg-ink-900 p-5">

          <div className="mb-4 flex items-baseline justify-between gap-3">
            <h3 id="leads-chart-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
              Leads over time
            </h3>
            <span className="font-mono text-[11px] uppercase tracking-wider text-chalk-faint">Last 8 weeks</span>
          </div>

          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={LEADS_OVER_TIME} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="leadsFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#CBFF4D" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#CBFF4D" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#242A2C" vertical={false} />
                <XAxis dataKey="week" stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: '#131617',
                    border: '1px solid #242A2C',
                    borderRadius: 10,
                    fontSize: 12,
                    color: '#F1F4F0'
                  }}
                  labelStyle={{ color: '#A5ADA7' }} />

                <Area type="monotone" dataKey="leads" stroke="#CBFF4D" strokeWidth={2} fill="url(#leadsFill)" name="Leads" />
                <Line
                  type="monotone"
                  dataKey="qualified"
                  stroke="#4B5457"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="4 4"
                  name="Qualified" />

              </AreaChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-3 border-t border-ink-850 pt-3 text-[12.5px] text-chalk-faint">
            Qualified-lead trend is sampled on Free.{' '}
            <button type="button" onClick={openUpgrade} className="text-signal hover:underline">
              Upgrade for full resolution
            </button>
            .
          </p>
        </section>

        <div className="flex flex-col gap-4">
          <UsageMeter
            label="Leads this cycle"
            used={workspace.leadsUsed}
            quota={workspace.leadQuota}
            onUpgrade={openUpgrade} />


          <section aria-labelledby="activity-title" className="flex-1 rounded-2xl border border-ink-800 bg-ink-900 p-5">
            <h3 id="activity-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
              Recent activity
            </h3>
            <ul className="mt-4 space-y-4">
              {ACTIVITY.map((item) =>
              <li key={item.id} className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-signal" aria-hidden="true" />
                  <span>
                    <span className="block text-[13.5px] leading-relaxed text-chalk-dim">{item.text}</span>
                    <span className="mt-0.5 block font-mono text-[11px] text-chalk-faint">{item.time}</span>
                  </span>
                </li>
              )}
            </ul>
            <Link
              to="/app/free/leads"
              className="mt-5 inline-flex items-center gap-1.5 border-t border-ink-850 pt-4 text-[13px] text-signal hover:underline">

              Go to Lead Center
              <ArrowRightIcon className="h-3.5 w-3.5" />
            </Link>
          </section>
        </div>
      </div>

      <div className="mt-4">
        <LockedFeatureCard
          title="AI reports are a Pro feature"
          description="Attribution, channel lift and forecast quality analysis unlock on Pro and above."
          onUpgrade={openUpgrade} />

      </div>
    </div>);

}
