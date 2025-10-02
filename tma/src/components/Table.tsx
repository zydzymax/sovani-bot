interface TableColumn {
  header: string;
  accessor: string;
  render?: (value: any, row: any) => React.ReactNode;
}

interface TableProps {
  columns: TableColumn[];
  data: any[];
  emptyMessage?: string;
}

export default function Table({ columns, data, emptyMessage = 'No data' }: TableProps) {
  if (data.length === 0) {
    return (
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-8 text-center text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full bg-white dark:bg-gray-800">
        <thead className="sticky top-0 bg-gray-100 dark:bg-gray-700">
          <tr className="border-b border-gray-200 dark:border-gray-600">
            {columns.map((col, idx) => (
              <th
                key={idx}
                className="px-4 py-3 text-left text-xs font-medium text-gray-700 dark:text-gray-300 uppercase tracking-wider"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIdx) => (
            <tr
              key={rowIdx}
              className="border-b border-gray-200 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-750"
            >
              {columns.map((col, colIdx) => (
                <td key={colIdx} className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                  {col.render ? col.render(row[col.accessor], row) : row[col.accessor]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
