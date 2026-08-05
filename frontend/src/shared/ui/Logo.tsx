import React from 'react';
import { cn } from '../utils/cn';

export function Logo({ className, showWord = true }: {className?: string;showWord?: boolean;}) {
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <span
        aria-hidden="true"
        className="relative flex h-7 w-7 items-center justify-center rounded-[9px] bg-signal">

        <svg viewBox="0 0 24 24" className="h-4 w-4 text-signal-deep" fill="none" stroke="currentColor" strokeWidth="2.2">
          <circle cx="6" cy="6" r="2.3" />
          <circle cx="18" cy="9" r="2.3" />
          <circle cx="10" cy="18" r="2.3" />
          <path d="M7.9 7.2 16 8.6M16.6 11 11.6 15.9M8.2 8.1 9.4 15.7" strokeLinecap="round" />
        </svg>
      </span>
      {showWord &&
      <span className="font-display text-[17px] font-semibold tracking-tight text-chalk">
          Crawlio<span className="text-chalk-faint">.io</span>
        </span>
      }
    </span>);

}
