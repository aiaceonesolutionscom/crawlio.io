import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';

export function Leads() {
  return (
    <LeadCenterPage
      tier="enterprise"
      searchEnabled
      whatsappEnabled
      bulkExportEnabled
      discoveryCap={50}
      discoveryEnhanced
      aiFilterEnabled />
  );
}
