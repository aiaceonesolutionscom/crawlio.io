import type { PlanId } from '../types';

export type FeatureKey =
'whatsapp' |
'automationBuilder' |
'aiReports' |
'team' |
'branding' |
'sso' |
'accountManager';

const MATRIX: Record<FeatureKey, PlanId[]> = {
  whatsapp: ['pro', 'enterprise'],
  automationBuilder: ['pro', 'enterprise'],
  aiReports: ['pro', 'enterprise'],
  team: ['pro', 'enterprise'],
  branding: ['enterprise'],
  sso: ['enterprise'],
  accountManager: ['enterprise']
};

export function can(plan: PlanId, feature: FeatureKey): boolean {
  return MATRIX[feature].includes(plan);
}

export function planLabel(plan: PlanId): string {
  return plan === 'free' ? 'Free' : plan === 'pro' ? 'Pro' : 'Enterprise';
}

export function formatQuota(value: number): string {
  return Number.isFinite(value) ? value.toLocaleString('en-US') : 'Unlimited';
}