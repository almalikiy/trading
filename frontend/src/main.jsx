import React, { Suspense, lazy, useState } from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import Layout from "./Layout";

const App = lazy(() => import("./legacy/App"));
const TradeHistory = lazy(() => import("./TradeHistory"));
const AccountMonitor = lazy(() => import("./AccountMonitor"));
const AdaptiveInsights = lazy(() => import("./AdaptiveInsights"));
const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage"));

function Root() {
  const [darkMode, setDarkMode] = useState(false);

  const theme = createTheme({
    palette: {
      mode: darkMode ? "dark" : "light",
      background: {
        default: darkMode ? "#121212" : "#fafafa",
        paper: darkMode ? "#1e1e1e" : "#fff",
      },
    },
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Layout darkMode={darkMode} setDarkMode={setDarkMode}>
          <Suspense fallback={<div style={{ padding: 24 }}>Loading dashboard…</div>}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/history" element={<TradeHistory />} />
              <Route path="/account" element={<AccountMonitor />} />
              <Route path="/adaptive" element={<AdaptiveInsights />} />
              <Route path="/legacy" element={<App />} />
            </Routes>
          </Suspense>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
