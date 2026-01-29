import { useState, useMemo } from 'react';

interface ResultsTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
}

export function ResultsTable({ columns, rows, rowCount }: ResultsTableProps) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const sortedRows = useMemo(() => {
    if (!sortColumn) return rows;

    return [...rows].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      const comparison = String(aVal).localeCompare(String(bVal), undefined, {
        numeric: true,
      });

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [rows, sortColumn, sortDirection]);

  const paginatedRows = useMemo(() => {
    const start = page * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, page]);

  const totalPages = Math.ceil(rows.length / pageSize);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'NULL';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  if (columns.length === 0) {
    return (
      <div className="text-gray-400 text-sm py-4">No columns to display</div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-800">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  onClick={() => handleSort(column)}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-300 uppercase tracking-wider cursor-pointer hover:bg-gray-700 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    {column}
                    {sortColumn === column && (
                      <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-gray-900 divide-y divide-gray-800">
            {paginatedRows.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-800 transition-colors">
                {columns.map((column) => (
                  <td
                    key={column}
                    className="px-4 py-2 text-sm text-gray-300 whitespace-nowrap max-w-xs truncate"
                    title={formatValue(row[column])}
                  >
                    {formatValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center text-sm text-gray-400">
        <span>
          Showing {page * pageSize + 1}-
          {Math.min((page + 1) * pageSize, rows.length)} of {rowCount} rows
        </span>

        {totalPages > 1 && (
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 bg-gray-800 rounded disabled:opacity-50 hover:bg-gray-700 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 bg-gray-800 rounded disabled:opacity-50 hover:bg-gray-700 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
