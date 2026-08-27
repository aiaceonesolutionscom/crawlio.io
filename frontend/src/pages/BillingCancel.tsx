import React from 'react';
import { useNavigate } from 'react-router-dom';
import { XCircleIcon } from 'lucide-react';
import { Logo } from '../shared/ui/Logo';
import { Button } from '../shared/ui/Button';

export function BillingCancel() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-ink-950 px-5 text-center">
      <Logo />
      <div className="mt-10 max-w-sm">
        <XCircleIcon className="mx-auto h-10 w-10 text-chalk-faint" />
        <h1 className="mt-4 font-display text-[22px] font-semibold text-chalk">Checkout canceled</h1>
        <p className="mt-2 text-[14px] text-chalk-dim">
          No charge was made. You can pick a plan again any time from Settings.
        </p>
        <Button className="mt-6" onClick={() => navigate('/app', { replace: true })}>
          Back to dashboard
        </Button>
      </div>
    </div>
  );
}
