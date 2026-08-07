import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';

export function Leads() {
  const { openUpgrade } = useDashboardChrome();
  return (
    <LeadCenterPage
      tier="free"
      pageLimit={20}
      searchEnabled={false}
      whatsappEnabled={false}
      bulkExportEnabled
      discoveryCap={50}
      discoveryEnhanced={false}
      aiFilterEnabled={false}
      onUpgrade={openUpgrade} />
  );
}
