// =============================================
// Penjelasan singkat keyword, API, dan library (LineChart):
//
// - React: Library utama untuk membangun UI berbasis komponen.
// - Chart.js: Library charting populer untuk visualisasi data (line, candlestick, dsb).
// - react-chartjs-2: Wrapper React untuk Chart.js.
// - chartjs-adapter-date-fns: Adapter agar Chart.js bisa menampilkan sumbu waktu dengan format modern.
//
// Keyword penting:
// - props: Data yang dikirim dari parent ke komponen ini (ohlcv).
// - useRef, useEffect: React hooks untuk efek samping dan referensi DOM.
// - map: Fungsi array untuk transformasi data.
// =============================================
import React, { useRef, useEffect } from "react";
import { Chart as ChartJS, LineElement, PointElement, LinearScale, TimeScale, Tooltip, Legend } from "chart.js";
import { Chart } from "react-chartjs-2";
import 'chartjs-adapter-date-fns';

ChartJS.register(LineElement, PointElement, LinearScale, TimeScale, Tooltip, Legend);

export default function LineChart({ ohlcv }) {
  if (!ohlcv || ohlcv.length === 0) return <div>No data</div>;
  // Tidak perlu konversi waktu, urutkan berdasarkan string saja (asumsi backend sudah urut)
  const sortedOhlcv = [...ohlcv];
  const prevRangeRef = useRef(ohlcv.length);
  // DEBUG: log sample data
  console.log('[LineChart] sample:', sortedOhlcv[0]);

  // Validasi data: cek gap waktu, duplikasi, interval tidak konsisten
  let debugInfo = "";
  let hasGap = false, hasDup = false, hasUnsorted = false;
  let intervals = [];
  for (let i = 1; i < sortedOhlcv.length; i++) {
    const t0 = new Date(sortedOhlcv[i-1].time).getTime();
    const t1 = new Date(sortedOhlcv[i].time).getTime();
    const diff = t1 - t0;
    intervals.push(diff);
    if (diff < 0) hasUnsorted = true;
    if (diff === 0) hasDup = true;
    // Untuk M1, idealnya diff = 60000 ms
    if (diff > 70000) hasGap = true;
  }
  if (hasGap) debugInfo += "⚠️ Gap waktu terdeteksi pada data OHLCV. ";
  if (hasDup) debugInfo += "⚠️ Duplikasi waktu terdeteksi. ";
  if (hasUnsorted) debugInfo += "⚠️ Data tidak urut waktu. ";
  if (intervals.length > 0) {
    const avg = Math.round(intervals.reduce((a,b)=>a+b,0)/intervals.length);
    debugInfo += `Interval rata-rata: ${avg/1000}s. `;
  }
  // debugInfo += `Jumlah data: ${sortedOhlcv.length}. Range: ${sortedOhlcv[0]?.time} - ${sortedOhlcv[sortedOhlcv.length-1]?.time}`;
  const data = {
    datasets: [
      {
        label: "Close Price",
        data: sortedOhlcv.map((d) => ({ 
          x: d.time * 1000, // epoch detik -> ms
          y: d.close })),
        borderColor: '#1976d2',
        backgroundColor: 'rgba(25, 118, 210, 0.1)',
        pointRadius: 0,
        tension: 0.2,
        fill: true,
      },
    ],
  };
  let yMin = null, yMax = null;
  if (sortedOhlcv && sortedOhlcv.length > 0) {
    yMin = Math.min(...sortedOhlcv.map(d => d.low));
    yMax = Math.max(...sortedOhlcv.map(d => d.high));
    // Tambahkan padding 1% agar chart tidak mepet
    const padding = (yMax - yMin) * 0.01;
    yMin = yMin - padding;
    yMax = yMax + padding;
  }
  // Nonaktifkan animasi jika range berubah drastis (misal, dari 60 ke 120 bar)
  const prevRange = prevRangeRef.current;
  const rangeChanged = Math.abs(prevRange - sortedOhlcv.length) > 2;
  useEffect(() => { prevRangeRef.current = sortedOhlcv.length; }, [sortedOhlcv.length]);
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { enabled: true },
    },
    animation: rangeChanged ? false : {
      duration: 400,
      easing: 'easeOutCubic',
    },
    scales: {
      x: {
        type: "time",
        time: { 
          unit: 'minute',
          displayFormats: {
            minute: 'HH:mm'
          } 
        },
        grid: {
          drawOnChartArea: true,
        },
        ticks: {
          autoSkip: true,
          maxTicksLimit: 24,
          // Hapus callback custom agar Chart.js pakai default time formatter
        }
      },
      y: {
        min: yMin,
        max: yMax,
        position: 'right',
        ticks: {
          callback: function(value) { return Number(value).toFixed(2); },
        },
        grace: '2%',
      },
    },
  };
  return (
    <div style={{ height: 350, width: '100%' }}>
      <Chart type="line" data={data} options={options} height={320} width={800} />
    </div>
  );
}
