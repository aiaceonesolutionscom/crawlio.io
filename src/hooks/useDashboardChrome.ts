import { useOutletContext } from 'react-router-dom';

export interface DashboardChrome {
  openUpgrade: () => void;
}

export function useDashboardChrome(): DashboardChrome {
  return useOutletContext<DashboardChrome>();
}