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
      <AppBar
        position="fixed"
        elevation={3}
        sx={{
          zIndex: theme.zIndex.drawer + 1,
          background: darkMode
            ? 'linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(30,41,59,1) 100%)'
            : 'linear-gradient(90deg, rgba(25,118,210,1) 0%, rgba(67,233,123,1) 100%)',
          color: '#fff',
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setOpen(!open)}
            sx={{ mr: 2, display: { sm: 'block', md: 'block' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 700, letterSpacing: 1, flexGrow: 1, color: '#fff' }}>
            {getTitle()}
          </Typography>
          <FormControlLabel
            control={
              <Switch
                checked={darkMode}
                onChange={() => setDarkMode((v) => !v)}
                sx={{ color: darkMode ? theme.palette.success.main : theme.palette.warning.main }}
              />
            }
            label={darkMode ? "Dark Mode" : "Light Mode"}
            sx={{ color: '#fff', m: 0 }}
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
            boxShadow: darkMode ? '2px 0 12px rgba(0,0,0,0.42)' : '2px 0 10px rgba(15,23,42,0.08)',
            transition: 'width 0.3s',
            color: theme.palette.text.primary,
          },
        }}
      >
        <Toolbar />
        <Divider />
        <List sx={{ px: 1, py: 1 }}>
          <ListItem
            button
            selected={location.pathname === "/"}
            onClick={() => { navigate("/"); setOpen(false); }}
            sx={{ borderRadius: 2, mb: 1, color: theme.palette.text.primary }}
          >
            <DashboardIcon sx={{ mr: 1, color: location.pathname === "/" ? theme.palette.primary.main : theme.palette.text.secondary }} />
            <ListItemText primary="Dashboard" primaryTypographyProps={{ color: 'inherit' }} />
          </ListItem>
          <ListItem
            button
            selected={location.pathname === "/history"}
            onClick={() => { navigate("/history"); setOpen(false); }}
            sx={{ borderRadius: 2, mb: 1, color: theme.palette.text.primary }}
          >
            <HistoryIcon sx={{ mr: 1, color: location.pathname === "/history" ? theme.palette.primary.main : theme.palette.text.secondary }} />
            <ListItemText primary="Trade History" primaryTypographyProps={{ color: 'inherit' }} />
          </ListItem>
          <ListItem
            button
            selected={location.pathname === "/account"}
            onClick={() => { navigate("/account"); setOpen(false); }}
            sx={{ borderRadius: 2, mb: 1, color: theme.palette.text.primary }}
          >
            <AccountBalanceWalletIcon sx={{ mr: 1, color: location.pathname === "/account" ? theme.palette.primary.main : theme.palette.text.secondary }} />
            <ListItemText primary="Account Monitor" primaryTypographyProps={{ color: 'inherit' }} />
          </ListItem>
          <ListItem
            button
            selected={location.pathname === "/adaptive"}
            onClick={() => { navigate("/adaptive"); setOpen(false); }}
            sx={{ borderRadius: 2, mb: 1, color: theme.palette.text.primary }}
          >
            <InsightsIcon sx={{ mr: 1, color: location.pathname === "/adaptive" ? theme.palette.primary.main : theme.palette.text.secondary }} />
            <ListItemText primary="Adaptive Insights" primaryTypographyProps={{ color: 'inherit' }} />
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
