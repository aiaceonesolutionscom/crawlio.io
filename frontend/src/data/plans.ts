import type { Plan, PlanId } from '../types';

export const PLANS: Plan[] = [
{
  id: 'free',
  name: 'Free',
  price: 'Free',
  priceNote: 'forever, no card required',
  tagline: 'For solo operators testing the waters',
  bestFor: 'Best for founders validating a single outbound motion.',
  leadQuota: '500 leads / month',
  seats: '1 seat',
  features: [
  { label: '500 leads per month', included: true },
  { label: '1 workspace, 1 seat', included: true },
  { label: 'AI lead scoring (standard model)', included: true },
  { label: 'Email outreach — 1 sequence', included: true },
  { label: 'WhatsApp automation', included: false },
  { label: 'Automation Builder', included: false },
  { label: 'AI reports & attribution', included: false },
  { label: 'Custom branding & SSO', included: false }],

  cta: 'Start free'
},
{
  id: 'pro',
  name: 'Pro',
  price: '$79',
  priceNote: 'per month, billed annually',
  tagline: 'For growing revenue teams',
  bestFor: 'Best for teams running multi-channel outbound at volume.',
  leadQuota: '5,000 leads / month',
  seats: 'Up to 10 seats',
  features: [
  { label: '5,000 leads per month', included: true },
  { label: 'Up to 10 seats with roles', included: true },
  { label: 'AI lead scoring (tuned model)', included: true },
  { label: 'Unlimited email sequences', included: true },
  { label: 'WhatsApp automation', included: true },
  { label: 'Automation Builder', included: true },
  { label: 'AI reports & attribution', included: true },
  { label: 'Custom branding & SSO', included: false }],

  cta: 'Upgrade to Pro',
  highlighted: true
},
{
  id: 'enterprise',
  name: 'Enterprise',
  price: 'Custom',
  priceNote: 'annual contract, quoted',
  tagline: 'For large, multi-region organisations',
  bestFor: 'Best for enterprises needing white-label, SSO and dedicated support.',
  leadQuota: 'Unlimited leads',
  seats: 'Unlimited seats',
  features: [
  { label: 'Unlimited leads', included: true },
  { label: 'Unlimited seats & custom roles', included: true },
  { label: 'AI scoring on your own data', included: true },
  { label: 'Unlimited email sequences', included: true },
  { label: 'WhatsApp automation', included: true },
  { label: 'Automation Builder + API access', included: true },
  { label: 'AI reports & attribution', included: true },
  { label: 'White-label, SSO, dedicated CSM', included: true }],

  cta: 'Contact sales'
}];


export const PLAN_LIMITS: Record<PlanId, {leads: number;seats: number;}> = {
  free: { leads: 500, seats: 1 },
  pro: { leads: 5000, seats: 10 },
  enterprise: { leads: Number.POSITIVE_INFINITY, seats: Number.POSITIVE_INFINITY }
};

export const COMPARISON: {group: string;rows: {label: string;values: Record<PlanId, string>;}[];}[] = [
{
  group: 'Volume',
  rows: [
  { label: 'Leads per month', values: { free: '500', pro: '5,000', enterprise: 'Unlimited' } },
  { label: 'Workspaces', values: { free: '1', pro: '3', enterprise: 'Unlimited' } },
  { label: 'Seats', values: { free: '1', pro: '10', enterprise: 'Unlimited' } }]

},
{
  group: 'Automation',
  rows: [
  { label: 'Email sequences', values: { free: '1', pro: 'Unlimited', enterprise: 'Unlimited' } },
  { label: 'WhatsApp automation', values: { free: '—', pro: 'Included', enterprise: 'Included' } },
  { label: 'Automation Builder', values: { free: '—', pro: 'Included', enterprise: 'Included + API' } }]

},
{
  group: 'Intelligence & support',
  rows: [
  { label: 'AI reports', values: { free: '—', pro: 'Included', enterprise: 'Custom models' } },
  { label: 'Branding', values: { free: 'Crawlio', pro: 'Remove badge', enterprise: 'Full white-label' } },
  { label: 'Support', values: { free: 'Community', pro: 'Priority email', enterprise: 'Dedicated CSM + SLA' } }]

}];


export function planById(id: PlanId): Plan {
  return PLANS.find((p) => p.id === id) ?? PLANS[0];
}