import { useEffect, useState } from 'react';
import { apiGet } from '../api';
import Header from '../components/Header';
import Table from '../components/Table';

interface AdviceRow {
  sku_id: number;
  sku_key: string | null;
  marketplace: string | null;
  warehouse: string | null;
  window_days: number;
  recommended_qty: number;
  sv: number | null;
  on_hand: number | null;
  in_transit: number | null;
  explain: string | null;
}

export default function Inventory() {
  const [advice, setAdvice] = useState<AdviceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [window, setWindow] = useState<14 | 28>(14);

  const today = new Date().toISOString().split('T')[0];
  const [adviceDate, setAdviceDate] = useState(today);

  useEffect(() => {
    loadAdvice();
  }, [window, adviceDate]);

  const loadAdvice = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await apiGet<AdviceRow[]>('/api/v1/advice', {
        date: adviceDate,
        window,
        limit: 100,
      });
      setAdvice(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load advice');
    } finally {
      setLoading(false);
    }
  };

  if (loading && advice.length === 0) {
    return <div className="text-center py-8">Loading inventory data...</div>;
  }

  if (error) {
    return <div className="text-red-400 text-center py-8">{error}</div>;
  }

  return (
    <div>
      <Header
        title="Inventory & Recommendations"
        subtitle="Supply recommendations based on sales velocity"
      />

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Date</label>
          <input
            type="date"
            value={adviceDate}
            onChange={(e) => setAdviceDate(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Planning Window</label>
          <select
            value={window}
            onChange={(e) => setWindow(Number(e.target.value) as 14 | 28)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          >
            <option value={14}>14 days</option>
            <option value={28}>28 days</option>
          </select>
        </div>
        <div className="flex items-end">
          <button
            onClick={loadAdvice}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Recommendations Table */}
      <Table
        columns={[
          { header: 'Marketplace', accessor: 'marketplace' },
          { header: 'SKU', accessor: 'sku_key' },
          { header: 'Warehouse', accessor: 'warehouse' },
          {
            header: 'SV',
            accessor: 'sv',
            render: (val) => (val ? val.toFixed(2) + '/day' : '—'),
          },
          { header: 'On Hand', accessor: 'on_hand' },
          { header: 'In Transit', accessor: 'in_transit' },
          {
            header: 'Recommended',
            accessor: 'recommended_qty',
            render: (val) => (
              <span className="font-bold text-green-400">{val}</span>
            ),
          },
          {
            header: 'Explanation',
            accessor: 'explain',
            render: (val) =>
              val ? (
                <span
                  className="text-xs text-gray-400 cursor-help"
                  title={val}
                >
                  {val.length > 50 ? val.substring(0, 50) + '...' : val}
                </span>
              ) : (
                '—'
              ),
          },
        ]}
        data={advice}
        emptyMessage="No recommendations available for this date/window"
      />
    </div>
  );
}
