import React, { useEffect, useState } from "react";
import { Box, Typography, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from "@mui/material";

export default function TradeHistory() {
  const [history, setHistory] = useState([]);
  useEffect(() => {
    fetch("http://localhost:8000/trade/history")
      .then(res => res.json())
      .then(data => setHistory(Array.isArray(data) ? data : []));
  }, []);

  return (
    <Box sx={{ p: 2, maxWidth: 1000, mx: 'auto' }}>
      <Typography variant="h5" sx={{ mb: 2 }}>Trade History</Typography>
      <Paper>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>No</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Entry</TableCell>
                <TableCell>Exit</TableCell>
                <TableCell>Profit</TableCell>
                <TableCell>Entry Time</TableCell>
                <TableCell>Exit Time</TableCell>
                <TableCell>Reason</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((row, idx) => (
                <TableRow key={idx}>
                  <TableCell>{idx + 1}</TableCell>
                  <TableCell>{row.type}</TableCell>
                  <TableCell>{row.entry}</TableCell>
                  <TableCell>{row.exit}</TableCell>
                  <TableCell style={{color: row.profit < 0 ? 'red' : 'green'}}>{row.profit?.toFixed(2)}</TableCell>
                  <TableCell>{row.entryTime ? new Date(row.entryTime * 1000).toLocaleString() : '-'}</TableCell>
                  <TableCell>{row.exitTime ? new Date(row.exitTime * 1000).toLocaleString() : '-'}</TableCell>
                  <TableCell>{row.reason || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
}
