import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AutomationFlow } from '../components/AutomationFlow';

export function Automation() {
  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Automation Builder"
        description="Chain triggers, conditions and channel actions into a flow that works leads without a rep touching them." />

      <AutomationFlow />
    </div>);

}
