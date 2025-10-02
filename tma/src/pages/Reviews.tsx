import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../api';
import Header from '../components/Header';

interface Review {
  review_id: string;
  marketplace: string | null;
  sku_key: string | null;
  rating: number | null;
  text: string | null;
  created_at_utc: string | null;
  reply_status: string | null;
  reply_text: string | null;
}

export default function Reviews() {
  const [items, setItems] = useState<Review[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadReviews();
  }, []);

  const loadReviews = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await apiGet<Review[]>('/api/v1/reviews', {
        status: 'pending',
        limit: 50,
      });
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reviews');
    } finally {
      setLoading(false);
    }
  };

  const onReply = async (id: string) => {
    const text = prompt('Enter your reply:');
    if (!text) return;

    try {
      await apiPost(`/api/v1/reviews/${id}/reply`, { text });
      setItems((prev) => prev.filter((x) => x.review_id !== id));
      alert('✅ Reply sent successfully');
    } catch (err) {
      alert('❌ Failed to send reply: ' + (err instanceof Error ? err.message : ''));
    }
  };

  if (loading && items.length === 0) {
    return <div className="text-center py-8">Loading reviews...</div>;
  }

  if (error) {
    return <div className="text-red-400 text-center py-8">{error}</div>;
  }

  return (
    <div>
      <Header
        title="Reviews"
        subtitle="Manage and reply to customer reviews"
      />

      {items.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400 border border-gray-700">
          No pending reviews ✅
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((review) => (
            <div
              key={review.review_id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className="text-yellow-400 text-lg">
                    {'★'.repeat(review.rating || 0)}
                    {'☆'.repeat(5 - (review.rating || 0))}
                  </span>
                  <span className="text-gray-400 text-sm ml-3">
                    {review.marketplace || 'Unknown'} • {review.sku_key || 'N/A'}
                  </span>
                </div>
                <span className="text-gray-500 text-xs">
                  {review.created_at_utc
                    ? new Date(review.created_at_utc).toLocaleDateString()
                    : 'Unknown date'}
                </span>
              </div>

              <p className="text-white mb-4">
                {review.text || '(No text provided)'}
              </p>

              <button
                onClick={() => onReply(review.review_id)}
                className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm font-medium"
              >
                Reply
              </button>
            </div>
          ))}
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-6">
          <button
            onClick={loadReviews}
            className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded text-sm"
          >
            Refresh
          </button>
        </div>
      )}
    </div>
  );
}
