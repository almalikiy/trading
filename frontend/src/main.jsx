
import React from "react";
import ReactDOM from "react-dom/client";
import Layout from "./layout";
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import App from "./App";
import TradeHistory from "./TradeHistory";
import AccountMonitor from "./AccountMonitor";
import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";

function Root() {
  // Override Root component to include dark mode state
  // Normally, can be start using ReacthDOM.createRoot(document.getElementById("root")).render(<App />);
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
        <Layout>
          <Routes>
            <Route path="/" element={<App darkMode={darkMode} setDarkMode={setDarkMode} />} />
            <Route path="/history" element={<TradeHistory />} />
            <Route path="/account" element={<AccountMonitor />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
