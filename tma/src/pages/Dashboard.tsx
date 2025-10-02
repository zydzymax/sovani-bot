import { useEffect, useState } from 'react';
import { apiGet } from '../api';
import Header from '../components/Header';
import KPICard from '../components/KPICard';
import Table from '../components/Table';

interface DashboardSummary {
  revenue_net: number;
  profit: number;
  margin: number;
  units: number;
  refunds_qty: number;
}

interface SkuMetric {
  sku_id: number;
  sku_key: string | null;
  article: string | null;
  marketplace: string | null;
  metric_value: number;
  units: number | null;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [topSku, setTopSku] = useState<SkuMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Date range (last 30 days by default)
  const today = new Date().toISOString().split('T')[0];
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0];

  const [dateFrom, setDateFrom] = useState(thirtyDaysAgo);
  const [dateTo, setDateTo] = useState(today);

  useEffect(() => {
    loadDashboard();
  }, [dateFrom, dateTo]);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryData, topSkuData] = await Promise.all([
        apiGet<DashboardSummary>('/api/v1/dashboard/summary', {
          date_from: dateFrom,
          date_to: dateTo,
        }),
        apiGet<SkuMetric[]>('/api/v1/dashboard/top-sku', {
          date_from: dateFrom,
          date_to: dateTo,
          metric: 'revenue',
          limit: 10,
        }),
      ]);

      setSummary(summaryData);
      setTopSku(topSkuData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !summary) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (error) {
    return <div className="text-red-400 text-center py-8">{error}</div>;
  }

  return (
    <div>
      <Header title="Dashboard" subtitle="Overview of your business metrics" />

      {/* Date Range Picker & Export */}
      <div className="mb-6 flex gap-4 items-end flex-wrap">
        <div>
          <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-2 text-gray-900 dark:text-white"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-2 text-gray-900 dark:text-white"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadDashboard}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white font-medium"
          >
            Refresh
          </button>
          <a
            href={`/api/v1/export/dashboard.csv?date_from=${dateFrom}&date_to=${dateTo}`}
            download
            className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded text-white font-medium inline-block"
            title="Export as CSV"
          >
            📥 CSV
          </a>
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          <KPICard
            title="Revenue Net"
            value={Math.round(summary.revenue_net).toLocaleString()}
            suffix="₽"
            icon="💰"
          />
          <KPICard
            title="Profit"
            value={Math.round(summary.profit).toLocaleString()}
            suffix="₽"
            icon="📈"
          />
          <KPICard
            title="Margin"
            value={summary.margin.toFixed(1)}
            suffix="%"
            icon="📊"
          />
          <KPICard
            title="Units Sold"
            value={summary.units.toLocaleString()}
            icon="📦"
          />
          <KPICard
            title="Refunds"
            value={summary.refunds_qty.toLocaleString()}
            icon="🔄"
          />
        </div>
      )}

      {/* Top SKU Table */}
      <div>
        <h2 className="text-xl font-bold mb-4">Top SKU by Revenue</h2>
        <Table
          columns={[
            { header: 'Marketplace', accessor: 'marketplace' },
            { header: 'SKU Key', accessor: 'sku_key' },
            { header: 'Article', accessor: 'article' },
            {
              header: 'Revenue',
              accessor: 'metric_value',
              render: (val) => `${Math.round(val).toLocaleString()} ₽`,
            },
            { header: 'Units', accessor: 'units' },
          ]}
          data={topSku}
          emptyMessage="No sales data for this period"
        />
      </div>
    </div>
  );
}
