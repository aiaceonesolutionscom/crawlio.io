import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { CrmBox } from '../../../shared/automation/CrmBox';
import { AutomationTemplateGallery } from '../../../shared/automation/AutomationTemplateGallery';
import { AutomationFlow } from '../components/AutomationFlow';

export function Automation() {
  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Automation Builder"
        description="Chain triggers, conditions and channel actions into a flow that works leads without a rep touching them." />

      <CrmBox />
      <AutomationTemplateGallery emailAgentPath="/app/pro/automation/email-agent" whatsappAgentPath="/app/pro/automation/whatsapp-agent" />
      <AutomationFlow />
    </div>);

}
