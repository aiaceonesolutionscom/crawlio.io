import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ClerkProvider } from '@clerk/clerk-react';
import { SessionProvider } from './contexts/SessionContext';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { SelectPlan } from './pages/SelectPlan';
import { RequireAuth } from './routes/RequireAuth';
import { RequirePlan } from './routes/RequirePlan';
import { RequireAdmin } from './routes/RequireAdmin';
import { PlanRedirect } from './routes/PlanRedirect';
import { AdminSessionProvider } from './contexts/AdminSessionContext';

// Admin is its own lazy chunk, entirely separate from the tier bundles below —
// a normal customer session never downloads it.
const AdminHomeRedirect = lazy(() =>
  import('./admin/AdminHomeRedirect').then((m) => ({ default: m.AdminHomeRedirect }))
);
const SuperAdminLayout = lazy(() =>
  import('./admin/super-admin/SuperAdminLayout').then((m) => ({ default: m.SuperAdminLayout }))
);
const SubAdminLayout = lazy(() =>
  import('./admin/sub-admin/SubAdminLayout').then((m) => ({ default: m.SubAdminLayout }))
);
const AdminDashboard = lazy(() => import('./admin/super-admin/pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const AdminWorkspaces = lazy(() =>
  import('./admin/super-admin/pages/Workspaces').then((m) => ({ default: m.Workspaces }))
);
const AdminPlanConfigs = lazy(() =>
  import('./admin/super-admin/pages/PlanConfigs').then((m) => ({ default: m.PlanConfigs }))
);
const AdminPlatformAdmins = lazy(() =>
  import('./admin/super-admin/pages/PlatformAdmins').then((m) => ({ default: m.PlatformAdmins }))
);
const AdminAuditLog = lazy(() => import('./admin/super-admin/pages/AuditLog').then((m) => ({ default: m.AuditLog })));
const AdminFeatureFlags = lazy(() =>
  import('./admin/super-admin/pages/FeatureFlags').then((m) => ({ default: m.FeatureFlags }))
);
const AdminSystemSettings = lazy(() =>
  import('./admin/super-admin/pages/SystemSettings').then((m) => ({ default: m.SystemSettings }))
);
const AdminIntegrations = lazy(() =>
  import('./admin/super-admin/pages/Integrations').then((m) => ({ default: m.Integrations }))
);
const SubAdminDashboard = lazy(() => import('./admin/sub-admin/pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const SubAdminWorkspaces = lazy(() =>
  import('./admin/sub-admin/pages/Workspaces').then((m) => ({ default: m.Workspaces }))
);
const SubAdminAuditLog = lazy(() => import('./admin/sub-admin/pages/AuditLog').then((m) => ({ default: m.AuditLog })));
const SubAdminIntegrations = lazy(() =>
  import('./admin/sub-admin/pages/Integrations').then((m) => ({ default: m.Integrations }))
);

// Single parameterized dashboard chunk. A Free session only ever renders the
// locked/limited variants of the same pages — no duplicated tier code.
const DashboardLayout = lazy(() => import('./app/dashboard/DashboardLayout').then((m) => ({ default: m.DashboardLayout })));
const DashboardOverview = lazy(() => import('./app/dashboard/pages/Overview').then((m) => ({ default: m.Overview })));
const DashboardLeads = lazy(() => import('./app/dashboard/pages/Leads').then((m) => ({ default: m.Leads })));
const DashboardAutomation = lazy(() => import('./app/dashboard/pages/Automation').then((m) => ({ default: m.Automation })));
const DashboardEmailAgent = lazy(() => import('./app/dashboard/pages/EmailAgent').then((m) => ({ default: m.EmailAgent })));
const DashboardWhatsAppAgent = lazy(() => import('./app/dashboard/pages/WhatsAppAgent').then((m) => ({ default: m.WhatsAppAgent })));
const DashboardAnalytics = lazy(() => import('./app/dashboard/pages/Analytics').then((m) => ({ default: m.Analytics })));
const DashboardTeam = lazy(() => import('./app/dashboard/pages/Team').then((m) => ({ default: m.Team })));
const DashboardSettings = lazy(() => import('./app/dashboard/pages/Settings').then((m) => ({ default: m.Settings })));

function TierFallback() {
  return <div className="flex min-h-screen w-full items-center justify-center bg-ink-950 text-chalk-faint text-[13px]">Loading…</div>;
}

const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!CLERK_PUBLISHABLE_KEY) {
  throw new Error('Missing VITE_CLERK_PUBLISHABLE_KEY — set it in .env (see .env.example).');
}

export function App() {
  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} signInUrl="/login" signUpUrl="/signup">
      <SessionProvider>
      <BrowserRouter>
        <Suspense fallback={<TierFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login/*" element={<Login />} />
            <Route path="/signup/*" element={<Signup />} />

            <Route path="/app" element={<RequireAuth><PlanRedirect /></RequireAuth>} />
            <Route path="/select-plan" element={<RequireAuth><SelectPlan /></RequireAuth>} />

            <Route
              path="/app/free"
              element={
              <RequireAuth>
                  <RequirePlan tier="free">
                    <DashboardLayout tier="free" />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<DashboardOverview tier="free" />} />
              <Route path="leads" element={<DashboardLeads tier="free" />} />
              <Route path="automation" element={<DashboardAutomation tier="free" />} />
              <Route path="analytics" element={<DashboardAnalytics tier="free" />} />
              <Route path="team" element={<DashboardTeam tier="free" />} />
              <Route path="settings" element={<DashboardSettings tier="free" />} />
            </Route>

            <Route
              path="/app/pro"
              element={
              <RequireAuth>
                  <RequirePlan tier="pro">
                    <DashboardLayout tier="pro" />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<DashboardOverview tier="pro" />} />
              <Route path="leads" element={<DashboardLeads tier="pro" />} />
              <Route path="automation" element={<DashboardAutomation tier="pro" />} />
              <Route path="automation/email-agent" element={<DashboardEmailAgent tier="pro" />} />
              <Route path="automation/whatsapp-agent" element={<DashboardWhatsAppAgent tier="pro" />} />
              <Route path="analytics" element={<DashboardAnalytics tier="pro" />} />
              <Route path="team" element={<DashboardTeam tier="pro" />} />
              <Route path="settings" element={<DashboardSettings tier="pro" />} />
            </Route>

            <Route
              path="/app/enterprise"
              element={
              <RequireAuth>
                  <RequirePlan tier="enterprise">
                    <DashboardLayout tier="enterprise" />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<DashboardOverview tier="enterprise" />} />
              <Route path="leads" element={<DashboardLeads tier="enterprise" />} />
              <Route path="automation" element={<DashboardAutomation tier="enterprise" />} />
              <Route path="automation/email-agent" element={<DashboardEmailAgent tier="enterprise" />} />
              <Route path="automation/whatsapp-agent" element={<DashboardWhatsAppAgent tier="enterprise" />} />
              <Route path="analytics" element={<DashboardAnalytics tier="enterprise" />} />
              <Route path="team" element={<DashboardTeam tier="enterprise" />} />
              <Route path="settings" element={<DashboardSettings tier="enterprise" />} />
            </Route>

            <Route
              path="/admin"
              element={
                <RequireAuth>
                  <AdminSessionProvider>
                    <RequireAdmin>
                      <AdminHomeRedirect />
                    </RequireAdmin>
                  </AdminSessionProvider>
                </RequireAuth>
              }
            />

            <Route
              path="/admin/super-admin"
              element={
                <RequireAuth>
                  <AdminSessionProvider>
                    <RequireAdmin>
                      <SuperAdminLayout />
                    </RequireAdmin>
                  </AdminSessionProvider>
                </RequireAuth>
              }
            >
              <Route index element={<AdminDashboard />} />
              <Route path="workspaces" element={<AdminWorkspaces />} />
              <Route path="plan-configs" element={<AdminPlanConfigs />} />
              <Route path="platform-admins" element={<AdminPlatformAdmins />} />
              <Route path="audit-log" element={<AdminAuditLog />} />
              <Route path="feature-flags" element={<AdminFeatureFlags />} />
              <Route path="system-settings" element={<AdminSystemSettings />} />
              <Route path="integrations" element={<AdminIntegrations />} />
            </Route>

            <Route
              path="/admin/sub-admin"
              element={
                <RequireAuth>
                  <AdminSessionProvider>
                    <RequireAdmin>
                      <SubAdminLayout />
                    </RequireAdmin>
                  </AdminSessionProvider>
                </RequireAuth>
              }
            >
              <Route index element={<SubAdminDashboard />} />
              <Route path="workspaces" element={<SubAdminWorkspaces />} />
              <Route path="audit-log" element={<SubAdminAuditLog />} />
              <Route path="integrations" element={<SubAdminIntegrations />} />
            </Route>

            <Route path="/dashboard/*" element={<Navigate to="/app" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      </SessionProvider>
    </ClerkProvider>);

}
