import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { LockedFeatureCard } from '../../../shared/ui/LockedFeatureCard';
import { AnalyticsCharts } from '../../../shared/analytics/AnalyticsCharts';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

export function Analytics({ tier }: Props) {
  const { openUpgrade } = useDashboardChrome();

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Analytics"
        description="Channel performance, source mix and reply quality across the whole workspace." />

      {tier === 'free' ?
      <LockedFeatureCard
        title="Analytics is a Pro feature"
        description="Full channel attribution and source reporting unlock on Pro and above."
        onUpgrade={openUpgrade} /> :
      <AnalyticsCharts tier={tier} />
      }
    </div>);

}