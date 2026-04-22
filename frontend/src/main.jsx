
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import TradeHistory from "./TradeHistory";
import AccountMonitor from "./AccountMonitor";
import { CssBaseline } from "@mui/material";
import { BrowserRouter, Routes, Route } from "react-router-dom";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CssBaseline />
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/history" element={<TradeHistory />} />
        <Route path="/account" element={<AccountMonitor />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
