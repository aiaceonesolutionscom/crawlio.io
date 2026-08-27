import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2Icon, Loader2Icon } from 'lucide-react';
import { useAuth } from '@clerk/clerk-react';
import { Logo } from '../shared/ui/Logo';
import { Button } from '../shared/ui/Button';
import { useSession } from '../contexts/SessionContext';
import { getSubscription } from '../lib/api/billing';

// Stripe/Safepay redirect here after checkout. Payment confirmation itself
// happens via webhook (which may land a moment before or after this page
// loads), so this polls briefly for the subscription to flip to "active"
// rather than assuming success just because the redirect happened.
export function BillingSuccess() {
  const { getToken } = useAuth();
  const { refreshWorkspace } = useSession();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'checking' | 'active' | 'pending'>('checking');

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const poll = async () => {
      const token = await getToken();
      const sub = await getSubscription(token);
      if (cancelled) return;
      if (sub && sub.status === 'active') {
        await refreshWorkspace();
        setStatus('active');
        return;
      }
      attempts += 1;
      if (attempts >= 10) {
        setStatus('pending');
        return;
      }
      window.setTimeout(() => void poll(), 1500);
    };

    void poll();
    return () => {
      cancelled = true;
    };
  }, [getToken, refreshWorkspace]);

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-ink-950 px-5 text-center">
      <Logo />
      <div className="mt-10 max-w-sm">
        {status === 'checking' && (
          <>
            <Loader2Icon className="mx-auto h-8 w-8 animate-spin text-signal" />
            <p className="mt-4 text-[15px] text-chalk-dim">Confirming your payment…</p>
          </>
        )}
        {status === 'active' && (
          <>
            <CheckCircle2Icon className="mx-auto h-10 w-10 text-signal" />
            <h1 className="mt-4 font-display text-[22px] font-semibold text-chalk">You&rsquo;re on Pro</h1>
            <p className="mt-2 text-[14px] text-chalk-dim">
              Your payment went through and your workspace has been upgraded.
            </p>
            <Button className="mt-6" onClick={() => navigate('/app/pro', { replace: true })}>
              Go to dashboard
            </Button>
          </>
        )}
        {status === 'pending' && (
          <>
            <p className="text-[15px] text-chalk-dim">
              Payment is still processing — this can take a minute. Refresh this page shortly, or check Settings for
              your plan status.
            </p>
            <Button className="mt-6" variant="outline" onClick={() => navigate('/app', { replace: true })}>
              Go to dashboard
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
