import React from 'react';
import { motion } from 'framer-motion';
import { BrainCircuitIcon, MailIcon, MessageSquareIcon } from 'lucide-react';
import { FEATURES, LOGOS, PIPELINE_STEPS } from '../../data/content';

const ICONS = {
  brain: BrainCircuitIcon,
  mail: MailIcon,
  message: MessageSquareIcon
} as const;

export function Features() {
  return (
    <>
      <section aria-label="Customers" className="overflow-hidden border-b border-ink-800 py-8">
        <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
          <p className="mb-6 text-center font-mono text-[11px] uppercase tracking-[0.2em] text-chalk-faint">
            Running pipeline for teams at
          </p>
        </div>
        <div className="relative flex w-full">
          <div className="flex w-max animate-marquee items-center gap-14 pr-14">
            {[...LOGOS, ...LOGOS].map((logo, i) =>
            <span
              key={`${logo}-${i}`}
              className="font-display text-[19px] font-medium tracking-tight text-chalk-faint">
              
                {logo}
              </span>
            )}
          </div>
        </div>
      </section>

      <section id="product" className="border-b border-ink-800 py-20 sm:py-28">
        <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
          <div className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-signal">The platform</p>
            <h2 className="mt-4 font-display text-[32px] font-semibold leading-tight tracking-tight text-chalk sm:text-[42px]">
              Three engines, one pipeline
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-chalk-dim">
              Every lead moves through the same path — enriched, ranked, then worked automatically across the
              channels your buyers actually answer.
            </p>
          </div>

          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {FEATURES.map((feature, i) => {
              const Icon = ICONS[feature.icon];
              return (
                <motion.article
                  key={feature.id}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-80px' }}
                  transition={{ duration: 0.5, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                  className="flex flex-col rounded-2xl border border-ink-800 bg-ink-900 p-6 transition-colors hover:border-ink-600">
                  
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-ink-700 bg-ink-850 text-signal">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-5 font-display text-[19px] font-semibold tracking-tight text-chalk">
                    {feature.name}
                  </h3>
                  <p className="mt-3 flex-1 text-[14.5px] leading-relaxed text-chalk-dim">{feature.description}</p>
                  <p className="mt-5 border-t border-ink-800 pt-4 font-mono text-[11px] uppercase tracking-wider text-chalk-faint">
                    {feature.detail}
                  </p>
                </motion.article>);

            })}
          </div>
        </div>
      </section>

      <section id="pipeline" className="border-b border-ink-800 py-20 sm:py-24">
        <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
          <h2 className="font-display text-[28px] font-semibold tracking-tight text-chalk sm:text-[34px]">
            How it works
          </h2>
          <ol className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-ink-800 bg-ink-800 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE_STEPS.map((step) =>
            <li key={step.step} className="bg-ink-900 p-6">
                <span className="font-mono text-[12px] text-signal">{step.step}</span>
                <h3 className="mt-3 font-display text-[18px] font-semibold tracking-tight text-chalk">
                  {step.label}
                </h3>
                <p className="mt-2 text-[14px] leading-relaxed text-chalk-dim">{step.copy}</p>
              </li>
            )}
          </ol>
        </div>
      </section>
    </>);

}