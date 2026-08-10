import { useCallback, useEffect, useState } from 'react';

/** List/refresh state for one admin resource screen. Mutations (create/update/
 * delete) are left to each concrete api/*.ts function — this hook only owns
 * the list, so callers just `await refresh()` after a mutation. */
export function useAdminResource<T>(fetchList: () => Promise<T[]>) {
  const [items, setItems] = useState<T[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchList();
      setItems(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setIsLoading(false);
    }
  }, [fetchList]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, isLoading, error, refresh };
}
