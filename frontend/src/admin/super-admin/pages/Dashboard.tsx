import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { StatCard } from '../../../shared/ui/StatCard';
import { useAdminSession } from '../../../contexts/AdminSessionContext';
import { getAdminDashboardOverview, type AdminDashboardOverviewDTO } from '../../../lib/api/admin/dashboard';

const TOOLTIP_STYLE = {
  background: '#131617',
  border: '1px solid #242A2C',
  borderRadius: 10,
  fontSize: 12,
  color: '#F1F4F0'
};

export function Dashboard() {
  const { admin } = useAdminSession();
  const { getToken } = useAuth();
  const [data, setData] = useState<AdminDashboardOverviewDTO | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await getToken();
      const overview = await getAdminDashboardOverview(token);
      if (!cancelled) setData(overview);
    })();
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  return (
    <div>
      <PageHeader title="Admin dashboard" description={`Signed in as ${admin?.email ?? ''}`} />

      {!data ? (
        <p className="text-[14px] text-chalk-dim">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Total workspaces" value={data.total_workspaces.toLocaleString('en-US')} />
            <StatCard label="Total leads (platform-wide)" value={data.total_leads.toLocaleString('en-US')} />
            <StatCard label="Active platform admins" value={data.active_platform_admins.toLocaleString('en-US')} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section aria-labelledby="plan-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
              <h3 id="plan-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
                Workspaces by plan
              </h3>
              {data.workspaces_by_plan.length === 0 ? (
                <p className="mt-5 text-[13.5px] text-chalk-faint">No workspaces yet.</p>
              ) : (
                <div className="mt-5 h-[240px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.workspaces_by_plan} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke="#242A2C" vertical={false} />
                      <XAxis dataKey="plan" stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                      <YAxis stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#A5ADA7' }} cursor={{ fill: '#191D1F' }} />
                      <Bar dataKey="count" fill="#CBFF4D" radius={[6, 6, 0, 0]} name="Workspaces" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            <section aria-labelledby="growth-title" className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
              <h3 id="growth-title" className="font-display text-[16px] font-semibold tracking-tight text-chalk">
                New workspaces (last 8 weeks)
              </h3>
              <div className="mt-5 h-[240px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.new_workspaces_over_time} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#242A2C" vertical={false} />
                    <XAxis dataKey="week" stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis stroke="#6D7772" tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#A5ADA7' }} cursor={{ fill: '#191D1F' }} />
                    <Bar dataKey="count" fill="#7FD3E8" radius={[6, 6, 0, 0]} name="New workspaces" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
