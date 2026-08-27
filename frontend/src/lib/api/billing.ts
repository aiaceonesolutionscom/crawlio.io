import { apiFetch } from './client';

export type BillingProvider = 'stripe' | 'safepay';
export type BillingCycle = 'monthly' | 'yearly';

export interface CheckoutResponseDTO {
  checkout_url: string;
  provider: BillingProvider;
}

export interface SubscriptionDTO {
  id: string;
  provider: BillingProvider;
  plan: string;
  billing_cycle: BillingCycle;
  status: string;
  current_period_end: string | null;
  canceled_at: string | null;
  created_at: string;
}

export function createCheckout(
  token: string | null,
  billingCycle: BillingCycle,
  provider: BillingProvider
) {
  return apiFetch<CheckoutResponseDTO>('/api/v1/billing/checkout', token, {
    method: 'POST',
    body: JSON.stringify({ plan: 'pro', billing_cycle: billingCycle, provider })
  });
}

export function getSubscription(token: string | null) {
  return apiFetch<SubscriptionDTO | null>('/api/v1/billing/subscription', token);
}

export function cancelSubscription(token: string | null) {
  return apiFetch<{ status: string }>('/api/v1/billing/cancel', token, { method: 'POST' });
}
