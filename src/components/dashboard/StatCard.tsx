import React from 'react';
import { TrendingDownIcon, TrendingUpIcon } from 'lucide-react';
import { cn } from '../../utils/cn';

interface Props {
  label: string;
  value: string;
  delta?: {value: string;direction: 'up' | 'down';};
  note?: string;
  muted?: boolean;
}

export function StatCard({ label, value, delta, note, muted = false }: Props) {
  const Icon = delta?.direction === 'down' ? TrendingDownIcon : TrendingUpIcon;

  return (
    <div className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
      <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint">{label}</p>
      <p
        className={cn(
          'mt-3 font-display text-[30px] font-semibold tracking-tightest',
          muted ? 'text-chalk-faint' : 'text-chalk'
        )}>
        
        {value}
      </p>
      <div className="mt-2 flex items-center gap-2">
        {delta &&
        <span
          className={cn(
            'inline-flex items-center gap-1 text-[12.5px] font-medium',
            delta.direction === 'up' ? 'text-signal' : 'text-ember'
          )}>
          
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {delta.value}
          </span>
        }
        {note && <span className="text-[12.5px] text-chalk-faint">{note}</span>}
      </div>
    </div>);

}