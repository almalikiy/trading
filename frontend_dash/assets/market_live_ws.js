function buildOhlcTrace(payload) {
    const candles = Array.isArray(payload && payload.ohlcv) ? payload.ohlcv : [];
    if (!candles.length) {
        return [];
    }

    const times = candles.map((row) => new Date((Number(row.time) || Date.now()) * 1000));
    const opens = candles.map((row) => Number(row.open) || 0);
    const highs = candles.map((row) => Number(row.high) || 0);
    const lows = candles.map((row) => Number(row.low) || 0);
    const closes = candles.map((row) => Number(row.close) || 0);

    return [{
        type: 'candlestick',
        x: times,
        open: opens,
        high: highs,
        low: lows,
        close: closes,
        increasing: { line: { color: '#2ecc71' } },
        decreasing: { line: { color: '#ff5c7a' } },
        hoverlabel: { bgcolor: '#0f172a' },
        name: payload.symbol || 'OHLC',
    }];
}

function renderOhlcChart(payload) {
    const root = document.getElementById('market-chart-live');
    if (!root || typeof Plotly === 'undefined') {
        return;
    }

    const traces = buildOhlcTrace(payload);
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 36, r: 16, t: 8, b: 30 },
        font: { color: '#cddbf2' },
        dragmode: 'pan',
        xaxis: {
            showgrid: false,
            rangeselector: { visible: false },
            rangeslider: { visible: false },
            tickfont: { color: '#9eb2cb' },
        },
        yaxis: {
            showgrid: true,
            gridcolor: '#243248',
            tickfont: { color: '#9eb2cb' },
        },
        height: 520,
    };

    if (!traces.length) {
        root.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#9eb2cb;font-weight:600;">No OHLCV data</div>';
        return;
    }

    if (root.dataset.chartReady === 'true') {
        Plotly.react(root, traces, layout, { displayModeBar: false, responsive: true });
        return;
    }

    Plotly.newPlot(root, traces, layout, { displayModeBar: false, responsive: true });
    root.dataset.chartReady = 'true';
}

function openOhlcSocket() {
    const root = document.getElementById('market-chart-live');
    if (!root) {
        return;
    }

    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname || '127.0.0.1';
    const port = '8001';
    const symbol = document.getElementById('symbol-input') ? document.getElementById('symbol-input').value || 'XAUUSD' : 'XAUUSD';
    const timeframe = document.getElementById('timeframe-input') ? document.getElementById('timeframe-input').value || 'M1' : 'M1';
    const bars = document.getElementById('bars-input') ? document.getElementById('bars-input').value || '60' : '60';
    const url = `${scheme}://${host}:${port}/ws/ohlcv?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&bars=${encodeURIComponent(bars)}`;

    if (window.__marketSocket && window.__marketSocket.readyState === WebSocket.OPEN) {
        return;
    }

    if (window.__marketSocket && window.__marketSocket.readyState === WebSocket.CONNECTING) {
        return;
    }

    window.__marketSocket = new WebSocket(url);
    window.__marketSocket.onmessage = function (event) {
        try {
            const payload = JSON.parse(event.data);
            renderOhlcChart(payload);
        } catch (error) {
            console.warn('OHLC websocket payload parse failed', error);
        }
    };

    window.__marketSocket.onclose = function () {
        setTimeout(openOhlcSocket, 2000);
    };
}

window.addEventListener('load', function () {
    openOhlcSocket();
    window.addEventListener('resize', function () {
        const root = document.getElementById('market-chart-live');
        if (root && typeof Plotly !== 'undefined' && root.dataset.chartReady === 'true') {
            Plotly.Plots.resize(root);
        }
    });
});
