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

// jumlahBar: jumlah bar yang ingin ditampilkan (misal 30, 60, 120, 240)
export default function CandlestickChart({ ohlcv, jumlahBar = 60 }) {
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
  // Ambil jumlahBar terakhir dari data (pastikan cukup data)
  const ohlcvSlice = ohlcv.length > jumlahBar ? ohlcv.slice(-jumlahBar) : ohlcv.slice();
  let yMin = undefined, yMax = undefined;
  const yPadding = 5; // padding tetap (misal 5 pip)
  if (ohlcvSlice && ohlcvSlice.length > 0) {
    yMin = Math.min(...ohlcvSlice.map(d => d.low));
    yMax = Math.max(...ohlcvSlice.map(d => d.high));
    yMin = Math.floor(yMin - yPadding);
    yMax = Math.ceil(yMax + yPadding);
  }
  // Manipulasi data: hilangkan candle pertama, tambahkan bar null setelah terakhir
  let chartData = [];
  let bbUpper = [], bbMiddle = [], bbLower = [];
  const bbPeriod = 20, bbStd = 2;
  if (ohlcvSlice.length > 2) {
    // Buang candle pertama
    const ohlcvTrim = ohlcvSlice.slice(1);
    chartData = ohlcvTrim.map((d) => ({
      x: d.time * 1000,
      o: d.open,
      h: d.high,
      l: d.low,
      c: d.close
    }));
    // Bollinger Band (20, 2)
    for (let i = 0; i < ohlcvTrim.length; i++) {
      if (i < bbPeriod - 1) {
        bbUpper.push(null);
        bbMiddle.push(null);
        bbLower.push(null);
        continue;
      }
      const slice = ohlcvTrim.slice(i - bbPeriod + 1, i + 1);
      const closes = slice.map(d => d.close);
      const mean = closes.reduce((a, b) => a + b, 0) / bbPeriod;
      const std = Math.sqrt(closes.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / bbPeriod);
      bbMiddle.push(mean);
      bbUpper.push(mean + bbStd * std);
      bbLower.push(mean - bbStd * std);
    }
    // Tambahkan bar null setelah candle terakhir
    const last = ohlcvTrim[ohlcvTrim.length - 1];
    const nextTime = last.time * 1000 + (ohlcvTrim[1].time - ohlcvTrim[0].time) * 1000; // asumsikan interval sama
    chartData.push({ x: nextTime, o: null, h: null, l: null, c: null });
    bbUpper.push(null);
    bbMiddle.push(null);
    bbLower.push(null);
  }
  const data = {
    datasets: [
      {
        type: 'candlestick',
        label: "OHLCV",
        data: chartData
      },
      // Bollinger Band Upper
      {
        type: 'line',
        label: 'BB Upper',
        data: chartData.map((d, i) => ({ x: d.x, y: bbUpper[i] })),
        borderColor: 'rgba(0,123,255,0.5)',
        borderWidth: 1,
        pointRadius: 0,
        fill: false,
        order: 1,
        yAxisID: 'y',
      },
      // Bollinger Band Middle
      {
        type: 'line',
        label: 'BB Middle',
        data: chartData.map((d, i) => ({ x: d.x, y: bbMiddle[i] })),
        borderColor: 'rgba(0,123,255,0.3)',
        borderWidth: 1,
        pointRadius: 0,
        borderDash: [4,2],
        fill: false,
        order: 1,
        yAxisID: 'y',
      },
      // Bollinger Band Lower
      {
        type: 'line',
        label: 'BB Lower',
        data: chartData.map((d, i) => ({ x: d.x, y: bbLower[i] })),
        borderColor: 'rgba(0,123,255,0.5)',
        borderWidth: 1,
        pointRadius: 0,
        fill: false,
        order: 1,
        yAxisID: 'y',
      },
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
    <div style={{ height: '100%', width: '100%' }} ref={chartRef}>
      <Chart type="candlestick" data={data} options={options} />
    </div>
  );
}
