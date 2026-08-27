import React from 'react';
import { SiteHeader } from '../landing/SiteHeader';
import { SiteFooter } from '../landing/SiteFooter';

interface Props {
  eyebrow: string;
  title: string;
  intro?: string;
  children: React.ReactNode;
}

// Shared shell for every footer-linked page (Product/Company/Resources/Legal)
// so they read as one consistent site instead of 16 one-off layouts.
export function MarketingLayout({ eyebrow, title, intro, children }: Props) {
  return (
    <div className="w-full bg-ink-950">
      <SiteHeader />
      <main className="mx-auto w-full max-w-[820px] px-5 pb-24 pt-16 sm:px-8 sm:pt-20">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">{eyebrow}</p>
        <h1 className="mt-3 font-display text-[34px] font-semibold tracking-tight text-chalk sm:text-[42px]">
          {title}
        </h1>
        {intro && <p className="mt-4 max-w-[640px] text-[16px] leading-relaxed text-chalk-dim">{intro}</p>}
        <div className="prose-marketing mt-10 space-y-8">{children}</div>
      </main>
      <SiteFooter />
    </div>
  );
}

export function Section({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section>
      {title && <h2 className="font-display text-[19px] font-semibold tracking-tight text-chalk">{title}</h2>}
      <div className="mt-3 space-y-3 text-[14.5px] leading-relaxed text-chalk-dim">{children}</div>
    </section>
  );
}
