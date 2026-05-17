// React hook: subscribes to SSE live quote streams for an array of tickers.
// © 2024 Sauhabah

import { useEffect, useRef, useState } from 'react';
import { api } from '../utils/api';
import type { LiveQuote } from '../types';

export function useLiveQuotes(tickers: string[]) {
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({});
  const sources = useRef<Record<string, EventSource>>({});

  useEffect(() => {
    // Open SSE for each ticker not already open
    tickers.forEach((t) => {
      if (sources.current[t]) return;
      sources.current[t] = api.streamQuote(t, (q) => {
        setQuotes((prev) => ({ ...prev, [t]: q }));
      });
    });

    // Close streams for removed tickers
    Object.keys(sources.current).forEach((t) => {
      if (!tickers.includes(t)) {
        sources.current[t].close();
        delete sources.current[t];
      }
    });

    return () => {
      Object.values(sources.current).forEach((es) => es.close());
      sources.current = {};
    };
  }, [tickers.join(',')]);

  return quotes;
}
