import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { PlusIcon } from 'lucide-react';
import { FAQS } from '../../data/content';

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="border-b border-ink-800 py-20 sm:py-24">
      <div className="mx-auto grid max-w-[1200px] gap-10 px-5 sm:px-8 lg:grid-cols-[0.8fr_1.2fr]">
        <h2 className="font-display text-[28px] font-semibold tracking-tight text-chalk sm:text-[34px]">
          Frequently asked
        </h2>

        <dl className="divide-y divide-ink-850 border-y border-ink-850">
          {FAQS.map((faq, i) => {
            const isOpen = open === i;
            return (
              <div key={faq.q}>
                <dt>
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : i)}
                    aria-expanded={isOpen}
                    className="flex w-full items-center justify-between gap-6 py-5 text-left">
                    
                    <span className="text-[16px] font-medium text-chalk">{faq.q}</span>
                    <PlusIcon
                      className={`h-4 w-4 shrink-0 text-chalk-faint transition-transform duration-300 ${
                      isOpen ? 'rotate-45 text-signal' : ''}`
                      }
                      aria-hidden="true" />
                    
                  </button>
                </dt>
                <AnimatePresence initial={false}>
                  {isOpen &&
                  <motion.dd
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden">
                    
                      <p className="max-w-2xl pb-5 pr-10 text-[14.5px] leading-relaxed text-chalk-dim">{faq.a}</p>
                    </motion.dd>
                  }
                </AnimatePresence>
              </div>);

          })}
        </dl>
      </div>
    </section>);

}