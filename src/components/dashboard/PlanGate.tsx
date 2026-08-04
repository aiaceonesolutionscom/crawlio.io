import React from 'react';
import { LockIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../../utils/cn';

interface PlanGateProps {
  /** Whether the current plan allows this feature. */
  allowed: boolean;
  requiredPlan?: 'Pro' | 'Enterprise';
  title: string;
  description: string;
  onUpgrade: () => void;
  children: React.ReactNode;
  className?: string;
}

/** Renders children when allowed; otherwise blurs them behind an upgrade prompt. */
export function PlanGate({
  allowed,
  requiredPlan = 'Pro',
  title,
  description,
  onUpgrade,
  children,
  className
}: PlanGateProps) {
  if (allowed) return <>{children}</>;

  return (
    <div className={cn('relative overflow-hidden rounded-2xl border border-ink-800', className)}>
      <div aria-hidden="true" className="pointer-events-none select-none opacity-25 blur-[3px] grayscale">
        {children}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink-950/70 px-6 text-center">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-ink-700 bg-ink-850 text-signal">
          <LockIcon className="h-4 w-4" />
        </span>
        <div>
          <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">{title}</p>
          <p className="mx-auto mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-chalk-dim">{description}</p>
        </div>
        <Button size="sm" onClick={onUpgrade} title={`Upgrade to ${requiredPlan} to access`}>
          Upgrade to {requiredPlan}
        </Button>
      </div>
    </div>);

}