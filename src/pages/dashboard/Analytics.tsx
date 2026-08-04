import React from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { PageHeader } from '../../components/dashboard/PageHeader';
import { PlanGate } from '../../components/dashboard/PlanGate';
import { StatCard } from '../../components/dashboard/StatCard';
import { useAuth } from '../../contexts/AuthContext';
import { useDashboardChrome } from '../../hooks/useDashboardChrome';
import { CHANNEL_PERFORMANCE, SOURCE_SPLIT } from '../../data/metrics';
import { can } from '../../utils/plan';

const PIE_COLORS = ['#CBFF4D', '#7FD3E8', '#FF8A4C', '#4B5457'];

const TOOLTIP_STYLE = {
  background: '#131617',
  border: '1px solid #242A2C',
  borderRadius: 10,
  fontSize: 12,
  color: '#F1F4F0'
};

export function Analytics() {
  const { user } = useAuth();
  const { openUpgrade } = useDashboardChrome();
  if (!user) return null;

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Analytics"
        description="Channel performance, source mix and reply quality across the whole workspace." />
      

      <PlanGate
        allowed={can(user.workspace.plan, 'aiReports')}
        title="Analytics is a Pro feature"
        description="Full channel attribution and source reporting unlock on Pro and above."
        onUpgrade={openUpgrade}>
        
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Replies (30d)" value="1,063" delta={{ value: '+19.2%', direction: 'up' }} />
            <StatCard label="Meetings booked" value="198" delta={{ value: '+6.4%', direction: 'up' }} />
            <StatCard label="Cost per qualified lead" value="$3.42" delta={{ value: '-11.0%', direction: 'down' }} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
            <section aria-labelledby="channel-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
              <h3 id="channel-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
                Replies by channel
              </h3>
              <div className="mt-5 h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={CHANNEL_PERFORMANCE} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#242A2C" vertical={false} />
                    <XAxis dataKey="channel" stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#A5ADA7' }} cursor={{ fill: '#191D1F' }} />
                    <Bar dataKey="replies" fill="#CBFF4D" radius={[6, 6, 0, 0]} name="Replies" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section aria-labelledby="source-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
              <h3 id="source-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
                Lead source mix
              </h3>
              <div className="mt-5 h-[200px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={SOURCE_SPLIT} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} stroke="none">
                      {SOURCE_SPLIT.map((entry, i) =>
                      <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      )}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-4 space-y-2">
                {SOURCE_SPLIT.map((entry, i) =>
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
            </section>
          </div>

          <p className="rounded-2xl border border-ink-800 bg-ink-900 p-5 text-[13.5px] text-chalk-faint">
            Cohort retention and forecast accuracy reports — <span className="text-chalk-dim">(Coming soon)</span>
          </p>
        </div>
      </PlanGate>
    </div>);

}