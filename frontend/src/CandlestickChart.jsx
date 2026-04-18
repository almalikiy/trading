// =============================================
// Penjelasan singkat keyword, API, dan library (CandlestickChart):
//
// - React: Library utama untuk membangun UI berbasis komponen.
// - Chart.js & chartjs-chart-financial: Library charting untuk candlestick/ohlc.
// - react-chartjs-2: Wrapper React untuk Chart.js.
// - chartjs-adapter-date-fns: Adapter agar Chart.js bisa menampilkan sumbu waktu dengan format modern.
//
// Keyword penting:
// - props: Data yang dikirim dari parent ke komponen ini (ohlcv).
// - useRef, useEffect, useState: React hooks untuk efek samping, referensi DOM, dan state lokal.
// - map: Fungsi array untuk transformasi data.
// =============================================

import React, { useRef, useEffect, useState } from "react";
import { Chart as ChartJS, registerables } from "chart.js";
import { Chart } from "react-chartjs-2";
import { CandlestickController, CandlestickElement, OhlcController, OhlcElement } from 'chartjs-chart-financial';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  ...registerables,
  CandlestickController,
  CandlestickElement,
  OhlcController,
  OhlcElement
);

export default function CandlestickChart({ ohlcv }) {
  const chartRef = useRef(null);
  const [canvasStatus, setCanvasStatus] = useState('');
  useEffect(() => {
    if (chartRef.current) {
      const canvas = chartRef.current.querySelector('canvas');
      if (canvas && canvas.offsetHeight > 0 && canvas.offsetWidth > 0) {
        setCanvasStatus('Chart rendered');
      } else {
        setCanvasStatus('Chart not rendered');
      }
    }
  });
  if (!ohlcv || ohlcv.length === 0) return <div>No data</div>;
  let yMin = undefined, yMax = undefined;
  if (ohlcv && ohlcv.length > 0) {
    yMin = Math.min(...ohlcv.map(d => d.low));
    yMax = Math.max(...ohlcv.map(d => d.high));
  }
  // Tampilkan waktu sesuai epoch detik yang dikirim backend (tanpa offset)
  const data = {
    datasets: [
      {
        type: 'candlestick',
        label: "OHLCV",
        data: ohlcv.map((d) => ({
          x: d.time * 1000, // epoch detik -> ms
          o: d.open,
          h: d.high,
          l: d.low,
          c: d.close
        }))
      }
    ]
  };
  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { enabled: true },
      title: {
        display: true,
        text: 'XAUUSD M1 Candlestick Chart',
      }
    },
    scales: {
      x: {
        type: "time",
        offset: false, // hilangkan padding kiri-kanan agar chart penuh
        time: {
          unit: "minute",
          displayFormats: {
            minute: "HH:mm",
            hour: "HH:mm",
            day: "HH:mm"
          },
          tooltipFormat: "HH:mm"
        },
        grid: { drawOnChartArea: true },
        ticks: {
          autoSkip: true,
          maxTicksLimit: 24,
          align: 'start', // rata kiri
          callback: function(value, index, ticks) {
            // Format label 24 jam (HH:mm), candle pertama tampilkan tanggal di bawah jam
            const date = new Date(value);
            const jam = date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
            if (index === 0) {
              const tgl = date.toLocaleDateString('en-CA'); // YYYY-MM-DD
              // Gunakan Unicode newline (\u000A) agar Chart.js render multi-line
              return jam + '\u000A' + tgl;
            }
            return jam;
          }
        }
      },
      y: {
        min: yMin,
        max: yMax,
        position: 'right',
        ticks: {
          callback: function(value) { return Number(value).toFixed(2); },
        },
      },
    },
  };
  return (
    <div style={{ height: 350, width: '100%' }} ref={chartRef}>
      <Chart type="candlestick" data={data} options={options} height={320} width={800} />
    </div>
  );
}
