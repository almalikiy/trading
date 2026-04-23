import { useState } from "react";
import { useNavigate } from "react-router-dom";

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
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import DashboardIcon from "@mui/icons-material/Dashboard";
import HistoryIcon from "@mui/icons-material/History";
import AccountBalanceWalletIcon from "@mui/icons-material/AccountBalanceWallet";

export function Layout({ children }) {
  const [open, setOpen] = useState(true);
  const navigate = useNavigate();
  const theme = useTheme();

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: theme.palette.background.default }}>
      {/* AppBar di atas */}
      <AppBar position="fixed" color="primary" elevation={2} sx={{ zIndex: theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setOpen(!open)}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 600, letterSpacing: 1 }}>
            Trading Dashboard
          </Typography>
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Drawer
        variant="persistent"
        open={open}
        sx={{
          width: 240,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box',
            background: theme.palette.background.paper,
            borderRight: `1px solid ${theme.palette.divider}`,
          },
        }}
      >
        <Toolbar />
        <Divider />
        <List>
          <ListItem button onClick={() => navigate("/")}> 
            <DashboardIcon sx={{ mr: 1, color: theme.palette.primary.main }} />
            <ListItemText primary="Dashboard" />
          </ListItem>
          <ListItem button onClick={() => navigate("/history")}> 
            <HistoryIcon sx={{ mr: 1, color: theme.palette.primary.main }} />
            <ListItemText primary="Trade History" />
          </ListItem>
          <ListItem button onClick={() => navigate("/account")}> 
            <AccountBalanceWalletIcon sx={{ mr: 1, color: theme.palette.primary.main }} />
            <ListItemText primary="Account Monitor" />
          </ListItem>
        </List>
      </Drawer>

      {/* Konten utama */}
      <Box
        component="main"
        sx={{ flexGrow: 1, p: { xs: 1, sm: 3 }, marginLeft: open ? "240px" : 0, background: theme.palette.background.default, minHeight: '100vh' }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
export default Layout;