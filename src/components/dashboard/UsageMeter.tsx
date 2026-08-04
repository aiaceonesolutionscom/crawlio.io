import React from 'react';
import { motion } from 'framer-motion';
import { Button } from '../ui/Button';
import { formatQuota } from '../../utils/plan';
import { cn } from '../../utils/cn';

interface Props {
  used: number;
  quota: number;
  label: string;
  onUpgrade?: () => void;
}

export function UsageMeter({ used, quota, label, onUpgrade }: Props) {
  const unlimited = !Number.isFinite(quota);
  const pct = unlimited ? 12 : Math.min(100, Math.round(used / quota * 100));
  const nearLimit = !unlimited && pct >= 75;

  return (
    <div className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[14px] font-medium text-chalk">{label}</p>
        <p className="font-mono text-[12.5px] text-chalk-dim">
          {used.toLocaleString('en-US')} / {formatQuota(quota)}
        </p>
      </div>

      <div className="mt-3.5 h-2 w-full overflow-hidden rounded-full bg-ink-800">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className={cn('h-full rounded-full', nearLimit ? 'bg-ember' : 'bg-signal')} />
        
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12.5px] text-chalk-faint">
          {unlimited ?
          'Unlimited on your plan — no cap enforced.' :
          nearLimit ?
          `You’ve used ${pct}% of this cycle’s allowance.` :
          `${formatQuota(quota - used)} remaining this cycle.`}
        </p>
        {onUpgrade && !unlimited &&
        <Button size="sm" variant="outline" onClick={onUpgrade}>
            Raise limit
          </Button>
        }
      </div>
    </div>);

}