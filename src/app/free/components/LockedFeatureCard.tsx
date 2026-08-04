import React from 'react';
import { LockIcon } from 'lucide-react';
import { Button } from '../../../shared/ui/Button';

interface Props {
  title: string;
  description: string;
  onUpgrade: () => void;
}

/** Full-page "this is a Pro feature" state — Free never receives the real feature's code at all, so there's nothing to blur. */
export function LockedFeatureCard({ title, description, onUpgrade }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-ink-800 bg-ink-900 px-6 py-16 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-ink-700 bg-ink-850 text-signal">
        <LockIcon className="h-4 w-4" />
      </span>
      <div>
        <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">{title}</p>
        <p className="mx-auto mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-chalk-dim">{description}</p>
      </div>
      <Button size="sm" onClick={onUpgrade} title="Upgrade to Pro to access">
        Upgrade to Pro
      </Button>
    </div>);

}
