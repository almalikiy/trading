
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

export default function CandlestickChart({ ohlcv, xTimeMode }) {
  const chartRef = useRef(null);
  const [canvasStatus, setCanvasStatus] = useState('');
  // Hooks harus selalu di atas, pengecekan data setelahnya
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
  const timeField = xTimeMode === 'local' ? 'time_local' : (xTimeMode === 'server' ? 'time_utc' : 'time');
  // Tidak perlu konversi waktu, gunakan string dari backend
  const labels = ohlcv.map((d) => d[timeField] || d.time);
  let yMin = undefined, yMax = undefined;
  if (ohlcv && ohlcv.length > 0) {
    yMin = Math.min(...ohlcv.map(d => d.low));
    yMax = Math.max(...ohlcv.map(d => d.high));
  }
  const data = {
    labels,
    datasets: [
      {
        type: 'candlestick',
        label: "OHLCV",
        data: ohlcv.map((d) => ({
          x: d[timeField] || d.time,
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
    },
    scales: {
      x: {
        type: "time",
        time: { unit: "minute" },
        grid: {
          drawOnChartArea: true,
        },
        ticks: {
          autoSkip: true,
          maxTicksLimit: 24, // lebih banyak grid vertikal
          callback: function(value, index, ticks) {
            let date = new Date(value);
            if (typeof window !== 'undefined' && window.xTimeMode === 'local') {
              // value diasumsikan UTC, new Date(value) sudah otomatis local, cukup gunakan date
            }
            const prevTick = ticks[index-1];
            let showDate = false;
            if (index === 0) showDate = true;
            else if (prevTick) {
              const prevDate = new Date(prevTick.value);
              if (
                date.getFullYear() !== prevDate.getFullYear() ||
                date.getMonth() !== prevDate.getMonth() ||
                date.getDate() !== prevDate.getDate()
              ) showDate = true;
            }
            const pad = n => n.toString().padStart(2, '0');
            if (showDate) {
              return [pad(date.getDate()) + '/' + pad(date.getMonth()+1), pad(date.getHours()) + ':' + pad(date.getMinutes())];
            } else {
              return pad(date.getHours()) + ':' + pad(date.getMinutes());
            }
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
