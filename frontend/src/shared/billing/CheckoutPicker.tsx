import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { CreditCardIcon, Loader2Icon, MapPinIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../utils/cn';
import { createCheckout, type BillingCycle, type BillingProvider } from '../../lib/api/billing';
import { ApiError } from '../../lib/api/client';

interface Props {
  onError: (message: string) => void;
}

const YEARLY_MONTHLY_EQUIVALENT = 79; // matches PLANS pro price in data/plans.ts
const YEARLY_TOTAL = 790; // 10x monthly = 2 months free, matches backend PRO_PRICE_USD_CENTS

/** Cycle + gateway picker shown once "Pro" is selected — the actual checkout
 * happens on Stripe's or Safepay's hosted page, this just decides which one
 * and for how long, then redirects. Free/Enterprise never reach this: Free
 * has no payment, Enterprise is sales-quoted. */
export function CheckoutPicker({ onError }: Props) {
  const { getToken } = useAuth();
  const [cycle, setCycle] = useState<BillingCycle>('monthly');
  const [provider, setProvider] = useState<BillingProvider>('stripe');
  const [isRedirecting, setIsRedirecting] = useState(false);

  const handleContinue = async () => {
    setIsRedirecting(true);
    onError('');
    try {
      const token = await getToken();
      const res = await createCheckout(token, cycle, provider);
      window.location.href = res.checkout_url;
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not start checkout. Please try again.');
      setIsRedirecting(false);
    }
  };

  return (
    <div className="rounded-xl border border-signal/30 bg-signal/5 p-4">
      <p className="text-[13px] font-medium text-chalk">Pro checkout</p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setCycle('monthly')}
          className={cn(
            'rounded-lg border px-3 py-2.5 text-left transition-colors',
            cycle === 'monthly' ? 'border-signal bg-ink-900' : 'border-ink-700 bg-ink-950 hover:border-ink-600'
          )}
        >
          <span className="block text-[13.5px] font-medium text-chalk">Monthly</span>
          <span className="block text-[12px] text-chalk-faint">${YEARLY_MONTHLY_EQUIVALENT}/mo</span>
        </button>
        <button
          type="button"
          onClick={() => setCycle('yearly')}
          className={cn(
            'relative rounded-lg border px-3 py-2.5 text-left transition-colors',
            cycle === 'yearly' ? 'border-signal bg-ink-900' : 'border-ink-700 bg-ink-950 hover:border-ink-600'
          )}
        >
          <span className="absolute -top-2 right-2 rounded-full bg-signal px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase text-signal-deep">
            Save 2mo
          </span>
          <span className="block text-[13.5px] font-medium text-chalk">Yearly</span>
          <span className="block text-[12px] text-chalk-faint">${YEARLY_TOTAL}/yr</span>
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setProvider('stripe')}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors',
            provider === 'stripe' ? 'border-signal bg-ink-900' : 'border-ink-700 bg-ink-950 hover:border-ink-600'
          )}
        >
          <CreditCardIcon className="h-4 w-4 shrink-0 text-chalk-dim" />
          <span>
            <span className="block text-[13px] font-medium text-chalk">Card</span>
            <span className="block text-[11px] text-chalk-faint">International — Stripe</span>
          </span>
        </button>
        <button
          type="button"
          onClick={() => setProvider('safepay')}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors',
            provider === 'safepay' ? 'border-signal bg-ink-900' : 'border-ink-700 bg-ink-950 hover:border-ink-600'
          )}
        >
          <MapPinIcon className="h-4 w-4 shrink-0 text-chalk-dim" />
          <span>
            <span className="block text-[13px] font-medium text-chalk">Local (PKR)</span>
            <span className="block text-[11px] text-chalk-faint">Cards, JazzCash, EasyPaisa — Safepay</span>
          </span>
        </button>
      </div>

      <Button className="mt-3 w-full" onClick={() => void handleContinue()} disabled={isRedirecting}>
        {isRedirecting && <Loader2Icon className="h-4 w-4 animate-spin" />}
        {isRedirecting ? 'Redirecting to payment…' : 'Continue to payment'}
      </Button>
    </div>
  );
}
