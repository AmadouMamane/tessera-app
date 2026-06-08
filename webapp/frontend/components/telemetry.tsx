"use client";

import { useReportWebVitals } from 'next/web-vitals';

export function Telemetry() {
  useReportWebVitals((metric) => {
    // Determine the level. LCP > 2500ms or FID > 100ms or CLS > 0.1 is usually poor.
    let level = 'info';
    if (metric.name === 'LCP' && metric.value > 2500) level = 'warning';
    if (metric.name === 'CLS' && metric.value > 0.1) level = 'warning';
    if (metric.name === 'FID' && metric.value > 100) level = 'warning';
    
    // In a real setup, we would batch these.
    fetch('/api/observability/log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: 'web_vital',
        level: level,
        metric: metric.name,
        value: metric.value,
        id: metric.id,
        url: window.location.href,
      }),
    }).catch(err => console.error("Telemetry failed", err));
  });

  return null;
}
