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
import { RequireSuperAdmin } from './routes/RequireSuperAdmin';
import { PlanRedirect } from './routes/PlanRedirect';
import { AdminSessionProvider } from './contexts/AdminSessionContext';

// Admin is its own lazy chunk, entirely separate from the tier bundles below —
// a normal customer session never downloads it.
const AdminLayout = lazy(() => import('./admin/AdminLayout').then((m) => ({ default: m.AdminLayout })));
const AdminDashboard = lazy(() => import('./admin/pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const AdminWorkspaces = lazy(() => import('./admin/pages/Workspaces').then((m) => ({ default: m.Workspaces })));
const AdminPlanConfigs = lazy(() => import('./admin/pages/PlanConfigs').then((m) => ({ default: m.PlanConfigs })));
const AdminPlatformAdmins = lazy(() =>
  import('./admin/pages/PlatformAdmins').then((m) => ({ default: m.PlatformAdmins }))
);
const AdminAuditLog = lazy(() => import('./admin/pages/AuditLog').then((m) => ({ default: m.AuditLog })));
const AdminFeatureFlags = lazy(() =>
  import('./admin/pages/FeatureFlags').then((m) => ({ default: m.FeatureFlags }))
);
const AdminSystemSettings = lazy(() =>
  import('./admin/pages/SystemSettings').then((m) => ({ default: m.SystemSettings }))
);

// Each tier is its own lazy chunk: a Free session never downloads Pro/Enterprise code.
const FreeLayout = lazy(() => import('./app/free/FreeLayout').then((m) => ({ default: m.FreeLayout })));
const FreeOverview = lazy(() => import('./app/free/pages/Overview').then((m) => ({ default: m.Overview })));
const FreeLeads = lazy(() => import('./app/free/pages/Leads').then((m) => ({ default: m.Leads })));
const FreeAutomation = lazy(() => import('./app/free/pages/Automation').then((m) => ({ default: m.Automation })));
const FreeAnalytics = lazy(() => import('./app/free/pages/Analytics').then((m) => ({ default: m.Analytics })));
const FreeTeam = lazy(() => import('./app/free/pages/Team').then((m) => ({ default: m.Team })));
const FreeSettings = lazy(() => import('./app/free/pages/Settings').then((m) => ({ default: m.Settings })));

const ProLayout = lazy(() => import('./app/pro/ProLayout').then((m) => ({ default: m.ProLayout })));
const ProOverview = lazy(() => import('./app/pro/pages/Overview').then((m) => ({ default: m.Overview })));
const ProLeads = lazy(() => import('./app/pro/pages/Leads').then((m) => ({ default: m.Leads })));
const ProAutomation = lazy(() => import('./app/pro/pages/Automation').then((m) => ({ default: m.Automation })));
const ProEmailAgent = lazy(() => import('./app/pro/pages/EmailAgent').then((m) => ({ default: m.EmailAgent })));
const ProWhatsAppAgent = lazy(() =>
  import('./app/pro/pages/WhatsAppAgent').then((m) => ({ default: m.WhatsAppAgent }))
);
const ProAnalytics = lazy(() => import('./app/pro/pages/Analytics').then((m) => ({ default: m.Analytics })));
const ProTeam = lazy(() => import('./app/pro/pages/Team').then((m) => ({ default: m.Team })));
const ProSettings = lazy(() => import('./app/pro/pages/Settings').then((m) => ({ default: m.Settings })));

const EnterpriseLayout = lazy(() => import('./app/enterprise/EnterpriseLayout').then((m) => ({ default: m.EnterpriseLayout })));
const EnterpriseOverview = lazy(() => import('./app/enterprise/pages/Overview').then((m) => ({ default: m.Overview })));
const EnterpriseLeads = lazy(() => import('./app/enterprise/pages/Leads').then((m) => ({ default: m.Leads })));
const EnterpriseAutomation = lazy(() => import('./app/enterprise/pages/Automation').then((m) => ({ default: m.Automation })));
const EnterpriseEmailAgent = lazy(() =>
  import('./app/enterprise/pages/EmailAgent').then((m) => ({ default: m.EmailAgent }))
);
const EnterpriseWhatsAppAgent = lazy(() =>
  import('./app/enterprise/pages/WhatsAppAgent').then((m) => ({ default: m.WhatsAppAgent }))
);
const EnterpriseAnalytics = lazy(() => import('./app/enterprise/pages/Analytics').then((m) => ({ default: m.Analytics })));
const EnterpriseTeam = lazy(() => import('./app/enterprise/pages/Team').then((m) => ({ default: m.Team })));
const EnterpriseSettings = lazy(() => import('./app/enterprise/pages/Settings').then((m) => ({ default: m.Settings })));

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
                    <FreeLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<FreeOverview />} />
              <Route path="leads" element={<FreeLeads />} />
              <Route path="automation" element={<FreeAutomation />} />
              <Route path="analytics" element={<FreeAnalytics />} />
              <Route path="team" element={<FreeTeam />} />
              <Route path="settings" element={<FreeSettings />} />
            </Route>

            <Route
              path="/app/pro"
              element={
              <RequireAuth>
                  <RequirePlan tier="pro">
                    <ProLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<ProOverview />} />
              <Route path="leads" element={<ProLeads />} />
              <Route path="automation" element={<ProAutomation />} />
              <Route path="automation/email-agent" element={<ProEmailAgent />} />
              <Route path="automation/whatsapp-agent" element={<ProWhatsAppAgent />} />
              <Route path="analytics" element={<ProAnalytics />} />
              <Route path="team" element={<ProTeam />} />
              <Route path="settings" element={<ProSettings />} />
            </Route>

            <Route
              path="/app/enterprise"
              element={
              <RequireAuth>
                  <RequirePlan tier="enterprise">
                    <EnterpriseLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<EnterpriseOverview />} />
              <Route path="leads" element={<EnterpriseLeads />} />
              <Route path="automation" element={<EnterpriseAutomation />} />
              <Route path="automation/email-agent" element={<EnterpriseEmailAgent />} />
              <Route path="automation/whatsapp-agent" element={<EnterpriseWhatsAppAgent />} />
              <Route path="analytics" element={<EnterpriseAnalytics />} />
              <Route path="team" element={<EnterpriseTeam />} />
              <Route path="settings" element={<EnterpriseSettings />} />
            </Route>

            <Route
              path="/admin"
              element={
                <RequireAuth>
                  <AdminSessionProvider>
                    <RequireSuperAdmin>
                      <AdminLayout />
                    </RequireSuperAdmin>
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
            </Route>

            <Route path="/dashboard/*" element={<Navigate to="/app" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      </SessionProvider>
    </ClerkProvider>);

}
