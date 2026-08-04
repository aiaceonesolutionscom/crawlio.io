import React from 'react';

interface Props {
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function PageHeader({ title, description, action }: Props) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="font-display text-[24px] font-semibold tracking-tight text-chalk sm:text-[28px]">{title}</h2>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-chalk-dim">{description}</p>
      </div>
      {action}
    </div>);

}