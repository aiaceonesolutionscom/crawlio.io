import React from 'react';
import { MailIcon } from 'lucide-react';
import { cn } from '../utils/cn';
import type { EmailQuotaDTO } from '../../lib/api/emailAgent';

interface Props {
  quota: EmailQuotaDTO | null;
}

export function EmailQuotaBar({ quota }: Props) {
  if (!quota) return null;

  const percent = Math.min(100, (quota.total_sent / quota.limit) * 100);
  const isWarning = percent >= 80;
  const isCritical = percent >= 95;

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <MailIcon className="h-4 w-4 text-chalk-faint" />
          <span className="text-[11px] font-medium text-chalk-dim">Daily Quota</span>
        </div>
        <span className={cn(
          'text-[11px] font-mono',
          isCritical ? 'text-ember' : isWarning ? 'text-amber-400' : 'text-signal'
        )}>
          {quota.total_sent}/{quota.limit}
        </span>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-ink-800">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300',
            isCritical ? 'bg-ember' : isWarning ? 'bg-amber-400' : 'bg-signal'
          )}
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-[10px] text-chalk-faint">
        <span>Composed: {quota.composed_count}</span>
        <span>AI: {quota.ai_generated_count}</span>
        <span>Remaining: {quota.remaining}</span>
      </div>

      {isWarning && (
        <p className={cn(
          'mt-2 text-[10px]',
          isCritical ? 'text-ember' : 'text-amber-400'
        )}>
          {isCritical ? 'Daily limit almost reached!' : 'Approaching daily limit'}
        </p>
      )}
    </div>
  );
}
