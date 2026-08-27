import React, { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { LockIcon, Loader2Icon } from 'lucide-react';
import { Logo } from '../shared/ui/Logo';
import { Button } from '../shared/ui/Button';
import { apiFetch, ApiError } from '../lib/api/client';

function formatCardNumber(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 16);
  return digits.replace(/(.{4})/g, '$1 ').trim();
}

function formatExpiry(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

function formatAmount(amount: number, currency: string): string {
  const major = amount / 100;
  return currency === 'PKR' ? `PKR ${major.toLocaleString('en-PK')}` : `$${major.toFixed(2)}`;
}

/** Staging-only stand-in for Stripe's/Safepay's own hosted checkout — only
 * ever reachable when the real provider key isn't configured yet (the
 * backend refuses to activate anything through here once it is, see
 * complete_mock_checkout's guard). Collects nothing real; any input "pays". */
export function MockCheckoutPage() {
  const { checkoutId } = useParams<{ checkoutId: string }>();
  const [searchParams] = useSearchParams();
  const { getToken } = useAuth();
  const navigate = useNavigate();

  const provider = searchParams.get('provider') ?? 'stripe';
  const cycle = searchParams.get('cycle') ?? 'monthly';
  const amount = Number(searchParams.get('amount') ?? 0);
  const currency = searchParams.get('currency') ?? 'USD';

  const [cardName, setCardName] = useState('');
  const [cardNumber, setCardNumber] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvc, setCvc] = useState('');
  const [isPaying, setIsPaying] = useState(false);
  const [error, setError] = useState('');

  const handlePay = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPaying(true);
    setError('');
    try {
      const token = await getToken();
      await apiFetch(`/api/v1/billing/mock-checkout/${checkoutId}/complete`, token, { method: 'POST' });
      navigate('/billing/success', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Payment failed. Please try again.');
      setIsPaying(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-ink-950 px-5 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <Logo />
          <span className="rounded-full border border-amber-400/40 bg-amber-400/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-amber-300">
            Test mode
          </span>
        </div>

        <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-chalk-faint">
            {provider === 'stripe' ? 'Card payment' : 'Safepay checkout'}
          </p>
          <p className="mt-2 font-display text-[26px] font-semibold text-chalk">
            {amount > 0 ? formatAmount(amount, currency) : ''}
          </p>
          <p className="text-[13px] text-chalk-dim">Crawlio Pro — billed {cycle}</p>

          <form onSubmit={(e) => void handlePay(e)} className="mt-6 space-y-4">
            <div>
              <label htmlFor="card-name" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                Cardholder name
              </label>
              <input
                id="card-name"
                required
                value={cardName}
                onChange={(e) => setCardName(e.target.value)}
                placeholder="Jane Doe"
                autoComplete="cc-name"
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="card-number" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                Card number
              </label>
              <input
                id="card-number"
                required
                value={cardNumber}
                onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                placeholder="4242 4242 4242 4242"
                inputMode="numeric"
                autoComplete="cc-number"
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="card-expiry" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Expiry
                </label>
                <input
                  id="card-expiry"
                  required
                  value={expiry}
                  onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                  placeholder="MM/YY"
                  inputMode="numeric"
                  autoComplete="cc-exp"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="card-cvc" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  CVC
                </label>
                <input
                  id="card-cvc"
                  required
                  value={cvc}
                  onChange={(e) => setCvc(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="123"
                  inputMode="numeric"
                  autoComplete="cc-csc"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                />
              </div>
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={isPaying}>
              {isPaying && <Loader2Icon className="h-4 w-4 animate-spin" />}
              {isPaying ? 'Processing…' : `Pay ${amount > 0 ? formatAmount(amount, currency) : ''}`}
            </Button>

            <p className="flex items-center justify-center gap-1.5 text-[11.5px] text-chalk-faint">
              <LockIcon className="h-3 w-3" />
              Test mode — no real payment provider is connected yet.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
