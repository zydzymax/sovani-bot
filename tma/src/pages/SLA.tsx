// Stage 18: Reviews SLA Page - TTFR monitoring and backlog management

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Calendar, Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface SLASummary {
  count_total: number;
  replied: number;
  within_sla: number;
  share_within_sla: number;
  median_ttfr_min: number;
  by_marketplace: Array<{
    marketplace: string;
    total: number;
    replied: number;
    within_sla: number;
    share_within_sla: number;
  }>;
  by_reply_kind: Array<{
    reply_kind: string;
    count: number;
  }>;
}

interface OverdueReview {
  review_id: number;
  marketplace: string;
  rating: number;
  has_media: boolean;
  ai_needed: boolean;
  created_at_utc: string;
  age_hours: number;
  sku_id: number;
  article: string;
  external_id: string | null;
  link: string | null;
}

export default function SLAPage() {
  const [summary, setSummary] = useState<SLASummary | null>(null);
  const [backlog, setBacklog] = useState<OverdueReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [escalating, setEscalating] = useState(false);

  // Filters
  const [dateFrom, setDateFrom] = useState<string>(
    new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  );
  const [dateTo, setDateTo] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [marketplace, setMarketplace] = useState<string>('');
  const [showOverdueOnly, setShowOverdueOnly] = useState(false);

  useEffect(() => {
    loadData();
  }, [dateFrom, dateTo, marketplace]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load SLA summary
      const summaryParams = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo,
      });
      if (marketplace) {
        summaryParams.append('marketplace', marketplace);
      }

      const summaryRes = await fetch(`/api/v1/reviews/sla/summary?${summaryParams}`);
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Load backlog if showing overdue only
      if (showOverdueOnly) {
        const backlogParams = new URLSearchParams({ limit: '100' });
        if (marketplace) {
          backlogParams.append('marketplace', marketplace);
        }

        const backlogRes = await fetch(`/api/v1/reviews/sla/backlog?${backlogParams}`);
        const backlogData = await backlogRes.json();
        setBacklog(backlogData.reviews || []);
      }
    } catch (error) {
      console.error('Failed to load SLA data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEscalate = async () => {
    setEscalating(true);
    try {
      const res = await fetch('/api/v1/reviews/sla/escalate', { method: 'POST' });
      const data = await res.json();
      alert(`Эскалация отправлена: ${data.overdue_count} отзывов, ${data.messages_sent} сообщений`);
      loadData(); // Reload
    } catch (error) {
      console.error('Escalation failed:', error);
      alert('Ошибка эскалации');
    } finally {
      setEscalating(false);
    }
  };

  if (loading) {
    return <div className="p-4">Загрузка...</div>;
  }

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold mb-6">SLA: Время первого ответа</h1>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Фильтры</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">От</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full border rounded p-2"
              />
            </div>
            <div>
              <label className="text-sm font-medium">До</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full border rounded p-2"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">Маркетплейс</label>
            <select
              value={marketplace}
              onChange={(e) => setMarketplace(e.target.value)}
              className="w-full border rounded p-2"
            >
              <option value="">Все</option>
              <option value="WB">Wildberries</option>
              <option value="OZON">Ozon</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={showOverdueOnly}
              onChange={(e) => setShowOverdueOnly(e.target.checked)}
              className="rounded"
            />
            <label className="text-sm font-medium">Только просроченные</label>
          </div>
        </CardContent>
      </Card>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Ответы отправлены</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {summary.replied} / {summary.count_total}
              </div>
              <p className="text-xs text-muted-foreground">
                {((summary.replied / summary.count_total) * 100).toFixed(1)}% охват
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Ответы в SLA</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.share_within_sla}%</div>
              <p className="text-xs text-muted-foreground">
                {summary.within_sla} из {summary.replied} ответов
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Медиана TTFR</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary.median_ttfr_min / 60).toFixed(1)}ч
              </div>
              <p className="text-xs text-muted-foreground">
                {summary.median_ttfr_min.toFixed(0)} минут
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Backlog Table */}
      {showOverdueOnly && backlog.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Просроченные отзывы ({backlog.length})</CardTitle>
            <Button onClick={handleEscalate} disabled={escalating} size="sm">
              {escalating ? 'Отправка...' : 'Эскалировать сейчас'}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">ID</th>
                    <th className="text-left p-2">★</th>
                    <th className="text-left p-2">Возраст</th>
                    <th className="text-left p-2">AI?</th>
                    <th className="text-left p-2">MP</th>
                    <th className="text-left p-2">Артикул</th>
                    <th className="text-left p-2">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {backlog.map((review) => (
                    <tr key={review.review_id} className="border-b hover:bg-muted/50">
                      <td className="p-2">{review.review_id}</td>
                      <td className="p-2">{'★'.repeat(review.rating)}</td>
                      <td className="p-2">{review.age_hours.toFixed(1)}ч</td>
                      <td className="p-2">
                        {review.ai_needed ? (
                          <Badge variant="secondary">🤖 AI</Badge>
                        ) : (
                          <Badge variant="outline">📝</Badge>
                        )}
                      </td>
                      <td className="p-2">{review.marketplace}</td>
                      <td className="p-2">{review.article}</td>
                      <td className="p-2">
                        {review.link && (
                          <a
                            href={review.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline text-xs"
                          >
                            Открыть
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* By Marketplace */}
      {summary && summary.by_marketplace.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>По маркетплейсам</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {summary.by_marketplace.map((mp) => (
                <div key={mp.marketplace} className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{mp.marketplace}</p>
                    <p className="text-sm text-muted-foreground">
                      {mp.replied} / {mp.total} отзывов
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold">{mp.share_within_sla.toFixed(1)}%</p>
                    <p className="text-xs text-muted-foreground">в SLA</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* By Reply Kind */}
      {summary && summary.by_reply_kind.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>По типу ответа</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {summary.by_reply_kind.map((kind) => (
                <div key={kind.reply_kind} className="flex items-center justify-between p-2 border rounded">
                  <span className="font-medium">
                    {kind.reply_kind === 'template' ? '📝 Шаблон' : '🤖 AI'}
                  </span>
                  <span className="text-lg font-bold">{kind.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
