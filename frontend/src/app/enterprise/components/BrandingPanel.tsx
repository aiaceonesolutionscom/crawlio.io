import React from 'react';
import { PaletteIcon } from 'lucide-react';

export function BrandingPanel() {
  return (
    <div className="rounded-xl border border-ink-800 bg-ink-950 p-4">
      <PaletteIcon className="h-4 w-4 text-signal" aria-hidden="true" />
      <p className="mt-3 text-[14px] font-medium text-chalk">Custom branding</p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-chalk-dim">
        Your logo, colours and sending domain across every touchpoint.
      </p>
    </div>);

}
