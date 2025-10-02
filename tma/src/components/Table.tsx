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
      <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400 border border-gray-700">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-gray-800 border border-gray-700 rounded-lg">
        <thead>
          <tr className="border-b border-gray-700">
            {columns.map((col, idx) => (
              <th
                key={idx}
                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIdx) => (
            <tr key={rowIdx} className="border-b border-gray-700 last:border-b-0 hover:bg-gray-750">
              {columns.map((col, colIdx) => (
                <td key={colIdx} className="px-4 py-3 text-sm">
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
