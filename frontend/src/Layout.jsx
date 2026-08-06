import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import {
  Drawer,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Box,
  Toolbar,
  AppBar,
  Typography,
  useTheme,
  Divider,
  useMediaQuery,
  Switch,
  FormControlLabel,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import DashboardIcon from "@mui/icons-material/Dashboard";
import HistoryIcon from "@mui/icons-material/History";
import AccountBalanceWalletIcon from "@mui/icons-material/AccountBalanceWallet";
import InsightsIcon from "@mui/icons-material/Insights";

export function Layout({ children, darkMode, setDarkMode }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const getTitle = () => {
    if (location.pathname === "/") return "Trading Signal Dashboard";
    if (location.pathname === "/history") return "Trade History";
    if (location.pathname === "/account") return "Account Monitor";
    if (location.pathname === "/adaptive") return "Adaptive & ML Insights";
    return "Trading Dashboard";
  };
  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: theme.palette.background.default }}>
      {/* AppBar di atas */}
      <AppBar position="fixed" color="primary" elevation={3} sx={{ zIndex: theme.zIndex.drawer + 1, background: 'linear-gradient(90deg,#1976d2 0%,#43e97b 100%)' }}>
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setOpen(!open)}
            sx={{ mr: 2, display: { sm: 'block', md: 'block' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 700, letterSpacing: 1, flexGrow: 1 }}>
            <span style={{ color: '#fff', letterSpacing: 2 }}>{getTitle()}</span>
          </Typography>
            <FormControlLabel
              control={<Switch checked={darkMode} onChange={() => setDarkMode((v) => !v)} 
                  sx={{ color: darkMode ? theme.palette.success.main : theme.palette.warning.main }} 
                />}
              label={darkMode ? "Dark Mode" : "Light Mode"}
            />
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Drawer
        variant={isMobile ? "temporary" : "persistent"}
        open={open}
        onClose={() => setOpen(false)}
        sx={{
          width: 220,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 220,
            boxSizing: 'border-box',
            background: theme.palette.background.paper,
            borderRight: `1px solid ${theme.palette.divider}`,
            boxShadow: '2px 0 8px #0001',
            transition: 'width 0.3s',
          },
        }}
      >
        <Toolbar />
        <Divider />
        <List>
          <ListItem button selected={location.pathname === "/"} onClick={() => { navigate("/"); setOpen(false); }} sx={{ borderRadius: 2, mb: 1 }}>
            <DashboardIcon sx={{ mr: 1, color: location.pathname === "/" ? theme.palette.primary.main : '#888' }} />
            <ListItemText primary="Dashboard" />
          </ListItem>
          <ListItem button selected={location.pathname === "/history"} onClick={() => { navigate("/history"); setOpen(false); }} sx={{ borderRadius: 2, mb: 1 }}>
            <HistoryIcon sx={{ mr: 1, color: location.pathname === "/history" ? theme.palette.primary.main : '#888' }} />
            <ListItemText primary="Trade History" />
          </ListItem>
          <ListItem button selected={location.pathname === "/account"} onClick={() => { navigate("/account"); setOpen(false); }} sx={{ borderRadius: 2, mb: 1 }}>
            <AccountBalanceWalletIcon sx={{ mr: 1, color: location.pathname === "/account" ? theme.palette.primary.main : '#888' }} />
            <ListItemText primary="Account Monitor" />
          </ListItem>
          <ListItem button selected={location.pathname === "/adaptive"} onClick={() => { navigate("/adaptive"); setOpen(false); }} sx={{ borderRadius: 2, mb: 1 }}>
            <InsightsIcon sx={{ mr: 1, color: location.pathname === "/adaptive" ? theme.palette.primary.main : '#888' }} />
            <ListItemText primary="Adaptive Insights" />
          </ListItem>
        </List>
      </Drawer>

      {/* Konten utama */}
      <Box
        component="main"
        sx={{ flexGrow: 1, p: { xs: 1, sm: 3 }, marginLeft: !isMobile && open ? "220px" : 0, background: theme.palette.background.default, minHeight: '100vh', transition: 'margin-left 0.3s' }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
export default Layout;