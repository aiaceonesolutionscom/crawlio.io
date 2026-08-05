import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';

const FREE_ROW_LIMIT = 6;

export function Leads() {
  const { openUpgrade } = useDashboardChrome();
  return (
    <LeadCenterPage
      tier="free"
      pageLimit={FREE_ROW_LIMIT}
      searchEnabled={false}
      whatsappEnabled={false}
      discoveryCap={50}
      discoveryEnhanced={false}
      onUpgrade={openUpgrade} />
  );
}
