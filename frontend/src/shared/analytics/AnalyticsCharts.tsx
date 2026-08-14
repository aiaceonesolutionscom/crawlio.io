import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { StatCard } from '../ui/StatCard';
import { getAnalyticsOverview, type AnalyticsOverviewDTO } from '../../lib/api/analytics';
import type { PlanId } from '../../types';

const PIE_COLORS = ['#CBFF4D', '#7FD3E8', '#FF8A4C', '#4B5457'];

const TOOLTIP_STYLE = {
  background: '#131617',
  border: '1px solid #242A2C',
  borderRadius: 10,
  fontSize: 12,
  color: '#F1F4F0'
};

interface Props {
  tier: PlanId;
}

export function AnalyticsCharts({ tier }: Props) {
  const { getToken } = useAuth();
  const [data, setData] = useState<AnalyticsOverviewDTO | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await getToken();
      const overview = await getAnalyticsOverview(token);
      if (!cancelled) setData(overview);
    })();
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  if (!data) {
    return <p className="text-[14px] text-chalk-dim">Loading…</p>;
  }

  const conversionRate = data.total_leads > 0 ? Math.round(data.qualified_leads / data.total_leads * 100) : 0;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total leads" value={data.total_leads.toLocaleString('en-US')} />
        <StatCard label="Qualified leads" value={data.qualified_leads.toLocaleString('en-US')} note={`${conversionRate}% of total`} />
        <StatCard label="Average AI score" value={data.avg_score.toFixed(1)} note="across scored leads" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <section aria-labelledby="status-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <h3 id="status-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
            Leads by status
          </h3>
          <div className="mt-5 h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.status_breakdown} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#242A2C" vertical={false} />
                <XAxis dataKey="status" stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#A5ADA7' }} cursor={{ fill: '#191D1F' }} />
                <Bar dataKey="count" fill="#CBFF4D" radius={[6, 6, 0, 0]} name="Leads" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section aria-labelledby="source-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <h3 id="source-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
            Lead source mix
          </h3>
          {data.source_split.length === 0 ?
          <p className="mt-5 text-[13.5px] text-chalk-faint">No leads captured yet.</p> :

          <>
              <div className="mt-5 h-[200px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={data.source_split} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} stroke="none">
                      {data.source_split.map((entry, i) =>
                    <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    )}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-4 space-y-2">
                {data.source_split.map((entry, i) =>
              <li key={entry.name} className="flex items-center justify-between text-[13px]">
                    <span className="flex items-center gap-2 text-chalk-dim">
                      <span
                    aria-hidden="true"
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />

                      {entry.name}
                    </span>
                    <span className="font-mono text-chalk">{entry.value}%</span>
                  </li>
              )}
              </ul>
            </>
          }
        </section>
      </div>

      <p className="rounded-2xl border border-ink-800 bg-ink-900 p-5 text-[13.5px] text-chalk-faint">
        {tier === 'enterprise' ?
        <>Custom scoring models trained on your own historical data —{' '}
          <span className="text-chalk-dim">talk to your account manager to configure</span>.</> :
        <>Cohort retention and forecast accuracy reports — <span className="text-chalk-dim">(Coming soon)</span></>}
      </p>
    </div>);

}