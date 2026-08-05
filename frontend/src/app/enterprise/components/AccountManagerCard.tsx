import React from 'react';
import { HeadphonesIcon } from 'lucide-react';

export function AccountManagerCard() {
  return (
    <div className="rounded-xl border border-ink-800 bg-ink-950 p-4">
      <HeadphonesIcon className="h-4 w-4 text-signal" aria-hidden="true" />
      <p className="mt-3 text-[14px] font-medium text-chalk">Account manager</p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-chalk-dim">
        Ines Cardoso — ines@crawlio.io · SLA response under 2 hours.
      </p>
    </div>);

}
