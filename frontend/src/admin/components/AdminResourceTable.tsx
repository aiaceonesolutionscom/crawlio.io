import React from 'react';
import { cn } from '../../shared/utils/cn';

export interface AdminColumn<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  align?: 'left' | 'right';
}

interface Props<T> {
  columns: AdminColumn<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  isLoading: boolean;
  emptyMessage?: string;
  renderActions?: (row: T) => React.ReactNode;
  onRowClick?: (row: T) => void;
  renderExpanded?: (row: T) => React.ReactNode;
}

/** Generic column-config-driven table. Reuses the same markup/classes as
 * app/pro/components/TeamTable.tsx so every admin screen looks consistent
 * with the rest of the product for free, without hand-building a table per
 * resource. */
export function AdminResourceTable<T>({
  columns,
  rows,
  getRowId,
  isLoading,
  emptyMessage = 'Nothing here yet.',
  renderActions,
  onRowClick,
  renderExpanded
}: Props<T>) {
  const headers = renderActions ? [...columns, { key: '__actions', header: 'Actions', align: 'right' as const }] : columns;

  return (
    <div className="overflow-x-auto rounded-2xl border border-ink-800 bg-ink-900 scrollbar-slim">
      <table className="w-full min-w-[620px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ink-800">
            {headers.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={cn(
                  'px-5 py-3.5 font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint',
                  col.align === 'right' && 'text-right'
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={headers.length} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                Loading…
              </td>
            </tr>
          )}
          {!isLoading && rows.length === 0 && (
            <tr>
              <td colSpan={headers.length} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                {emptyMessage}
              </td>
            </tr>
          )}
          {!isLoading &&
            rows.map((row) => (
              <React.Fragment key={getRowId(row)}>
                <tr
                  className={cn(
                    'border-b border-ink-850 last:border-0',
                    onRowClick && 'cursor-pointer hover:bg-ink-850/60'
                  )}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'px-5 py-4 text-[13.5px] text-chalk-dim',
                        col.align === 'right' && 'text-right'
                      )}
                    >
                      {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '—')}
                    </td>
                  ))}
                  {renderActions && <td className="px-5 py-4 text-right">{renderActions(row)}</td>}
                </tr>
                {renderExpanded && (
                  <tr className="border-b border-ink-850 bg-ink-950/60 last:border-0">
                    <td colSpan={headers.length}>{renderExpanded(row)}</td>
                  </tr>
                )}
              </React.Fragment>
            ))}
        </tbody>
      </table>
    </div>
  );
}
