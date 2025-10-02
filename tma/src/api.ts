/**
 * API client for SoVAni backend
 * Automatically includes Telegram initData in headers
 */

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

function getInitData(): string {
  return window.Telegram?.WebApp?.initData || '';
}

export async function apiGet<T = any>(
  path: string,
  params: Record<string, string | number> = {}
): Promise<T> {
  const url = new URL(path, window.location.origin + API_BASE);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));

  const initData = getInitData();
  const res = await fetch(url.toString(), {
    headers: {
      'X-Telegram-Init-Data': initData,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error: ${res.status} ${text}`);
  }

  return res.json();
}

export async function apiPost<T = any>(
  path: string,
  body: unknown
): Promise<T> {
  const initData = getInitData();
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error: ${res.status} ${text}`);
  }

  return res.json().catch(() => ({}));
}

// Initialize Telegram WebApp
if (window.Telegram?.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}
