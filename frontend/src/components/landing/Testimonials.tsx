import React from 'react';
import { TESTIMONIALS } from '../../data/content';

export function Testimonials() {
  return (
    <section aria-labelledby="testimonials-title" className="border-b border-ink-800 py-20 sm:py-24">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <h2
          id="testimonials-title"
          className="font-display text-[28px] font-semibold tracking-tight text-chalk sm:text-[34px]">
          
          What teams say
        </h2>

        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {TESTIMONIALS.map((item) =>
          <figure
            key={item.name}
            className="flex flex-col justify-between rounded-2xl border border-ink-800 bg-ink-900 p-6">
            
              <blockquote className="text-[15px] leading-relaxed text-chalk">&ldquo;{item.quote}&rdquo;</blockquote>
              <figcaption className="mt-6 flex items-center gap-3 border-t border-ink-800 pt-5">
                <span
                aria-hidden="true"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-ink-700 bg-ink-850 font-display text-[13px] font-semibold text-signal">
                
                  {item.name.
                split(' ').
                map((n) => n[0]).
                join('')}
                </span>
                <span>
                  <span className="block text-[14px] font-medium text-chalk">{item.name}</span>
                  <span className="block text-[12.5px] text-chalk-faint">{item.role}</span>
                </span>
              </figcaption>
            </figure>
          )}
        </div>
      </div>
    </section>);

}