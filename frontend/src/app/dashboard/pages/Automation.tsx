import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { LockedFeatureCard } from '../../../shared/ui/LockedFeatureCard';
import { CrmBox } from '../../../shared/automation/crm/CrmBox';
import { AutomationTemplateGallery } from '../../../shared/automation/sequences/AutomationTemplateGallery';
import { AutomationFlow } from '../../../shared/automation/sequences/AutomationFlow';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

export function Automation({ tier }: Props) {
  const { openUpgrade } = useDashboardChrome();

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Automation Builder"
        description="Chain triggers, conditions and channel actions into a flow that works leads without a rep touching them." />

      {tier === 'free' ?
      <LockedFeatureCard
        title="Automation Builder is a Pro feature"
        description="Build multi-channel flows with conditions, delays and human handoff on Pro and above."
        onUpgrade={openUpgrade} /> :
      <>
        <CrmBox />
        <AutomationTemplateGallery emailAgentPath={`/app/${tier}/automation/email-agent`} whatsappAgentPath={`/app/${tier}/automation/whatsapp-agent`} />
        <AutomationFlow />
      </>
      }
    </div>);

}