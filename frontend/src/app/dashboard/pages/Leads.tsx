import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

const TIER_CONFIG: Record<PlanId, {
  pageLimit?: number;
  searchEnabled: boolean;
  whatsappEnabled: boolean;
  discoveryCap: number;
  discoveryEnhanced: boolean;
  aiFilterEnabled: boolean;
}> = {
  free: {
    pageLimit: 20,
    searchEnabled: false,
    whatsappEnabled: false,
    discoveryCap: 50,
    discoveryEnhanced: false,
    aiFilterEnabled: false,
  },
  pro: {
    searchEnabled: true,
    whatsappEnabled: true,
    discoveryCap: 100,
    discoveryEnhanced: true,
    aiFilterEnabled: true,
  },
  enterprise: {
    searchEnabled: true,
    whatsappEnabled: true,
    discoveryCap: 200,
    discoveryEnhanced: true,
    aiFilterEnabled: true,
  },
};

export function Leads({ tier }: Props) {
  const { openUpgrade } = useDashboardChrome();
  const config = TIER_CONFIG[tier];
  return (
    <LeadCenterPage
      tier={tier}
      pageLimit={config.pageLimit}
      searchEnabled={config.searchEnabled}
      whatsappEnabled={config.whatsappEnabled}
      bulkExportEnabled
      discoveryCap={config.discoveryCap}
      discoveryEnhanced={config.discoveryEnhanced}
      aiFilterEnabled={config.aiFilterEnabled}
      onUpgrade={tier === 'free' ? openUpgrade : undefined} />
  );
}