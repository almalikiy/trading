const BACKEND_URLS = {
    mt5: {
        http: import.meta.env.VITE_BACKEND_URL || "http://localhost:8001",
        ws: import.meta.env.VITE_BACKEND_WS_URL || "ws://localhost:8001/ws/signal",
    },
    sim: {
        http: "http://localhost:8001",
        ws: "ws://localhost:8001/ws/signal",
    },
};

export const API_BASE = BACKEND_URLS.mt5.http;

export function getBackendUrl(engine = "mt5", type = "http") {
    return BACKEND_URLS[engine]?.[type] || BACKEND_URLS.mt5[type];
}

export default BACKEND_URLS;
