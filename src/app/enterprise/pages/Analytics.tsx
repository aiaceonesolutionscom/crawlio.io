import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AnalyticsCharts } from '../components/AnalyticsCharts';

export function Analytics() {
  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Analytics"
        description="Channel performance, source mix and reply quality across the whole workspace." />

      <AnalyticsCharts />
    </div>);

}
