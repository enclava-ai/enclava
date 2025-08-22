/**
 * Zammad Plugin Dashboard Component
 * Main dashboard for Zammad plugin showing tickets, statistics, and quick actions
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Tooltip
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Sync as SyncIcon,
  Analytics as AnalyticsIcon,
  Assignment as TicketIcon,
  AutoAwesome as AIIcon,
  Settings as SettingsIcon,
  OpenInNew as OpenIcon
} from '@mui/icons-material';

interface ZammadTicket {
  id: string;
  title: string;
  status: string;
  priority: string;
  customer_id: string;
  created_at: string;
  ai_summary?: string;
}

interface ZammadStats {
  configurations: number;
  total_tickets: number;
  tickets_with_summaries: number;
  recent_tickets: number;
  summary_rate: number;
  last_sync: string;
}

export const ZammadDashboard: React.FC = () => {
  const [tickets, setTickets] = useState<ZammadTicket[]>([]);
  const [stats, setStats] = useState<ZammadStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTicket, setSelectedTicket] = useState<ZammadTicket | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  
  useEffect(() => {
    loadDashboardData();
  }, []);
  
  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Load statistics
      const statsResponse = await fetch('/api/v1/plugins/zammad/statistics');
      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }
      
      // Load recent tickets
      const ticketsResponse = await fetch('/api/v1/plugins/zammad/tickets?limit=10');
      if (ticketsResponse.ok) {
        const ticketsData = await ticketsResponse.json();
        setTickets(ticketsData.tickets || []);
      }
      
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleSyncTickets = async () => {
    setSyncing(true);
    try {
      const response = await fetch('/api/v1/plugins/zammad/tickets/sync', {
        method: 'GET'
      });
      
      if (response.ok) {
        const result = await response.json();
        // Reload dashboard data after sync
        await loadDashboardData();
        // Show success message with sync count
        console.log(`Synced ${result.synced_count} tickets`);
      } else {
        throw new Error('Sync failed');
      }
    } catch (err) {
      setError('Failed to sync tickets');
    } finally {
      setSyncing(false);
    }
  };
  
  const handleTicketClick = (ticket: ZammadTicket) => {
    setSelectedTicket(ticket);
    setDialogOpen(true);
  };
  
  const handleSummarizeTicket = async (ticketId: string) => {
    try {
      const response = await fetch(`/api/v1/plugins/zammad/tickets/${ticketId}/summarize`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // Show success message
        console.log('Summarization started');
      }
    } catch (err) {
      console.error('Summarization failed:', err);
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open': return 'error';
      case 'pending': return 'warning';
      case 'closed': return 'success';
      default: return 'default';
    }
  };
  
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case '3 high': return 'error';
      case '2 normal': return 'warning';
      case '1 low': return 'success';
      default: return 'default';
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Zammad Dashboard
        </Typography>
        
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<SyncIcon />}
            onClick={handleSyncTickets}
            disabled={syncing}
          >
            {syncing ? 'Syncing...' : 'Sync Tickets'}
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadDashboardData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {loading && <LinearProgress sx={{ mb: 3 }} />}
      
      {/* Statistics Cards */}
      {stats && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2}>
                  <TicketIcon color="primary" />
                  <Box>
                    <Typography variant="h6">{stats.total_tickets}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Tickets
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2}>
                  <AIIcon color="secondary" />
                  <Box>
                    <Typography variant="h6">{stats.tickets_with_summaries}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      AI Summaries
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2}>
                  <AnalyticsIcon color="success" />
                  <Box>
                    <Typography variant="h6">{stats.summary_rate}%</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Summary Rate
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2}>
                  <RefreshIcon color="info" />
                  <Box>
                    <Typography variant="h6">{stats.recent_tickets}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Recent (7 days)
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
      
      {/* Recent Tickets Table */}
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Recent Tickets</Typography>
            <Button
              size="small"
              endIcon={<OpenIcon />}
              onClick={() => window.location.hash = '#/plugins/zammad/tickets'}
            >
              View All
            </Button>
          </Box>
          
          {tickets.length === 0 ? (
            <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
              No tickets found. Try syncing with Zammad.
            </Typography>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Title</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Priority</TableCell>
                  <TableCell>AI Summary</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tickets.map((ticket) => (
                  <TableRow key={ticket.id} hover onClick={() => handleTicketClick(ticket)}>
                    <TableCell>
                      <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                        {ticket.title}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={ticket.status} 
                        color={getStatusColor(ticket.status) as any}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={ticket.priority} 
                        color={getPriorityColor(ticket.priority) as any}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      {ticket.ai_summary ? (
                        <Chip label="Available" color="success" size="small" />
                      ) : (
                        <Chip label="None" color="default" size="small" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Generate AI Summary">
                        <IconButton 
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSummarizeTicket(ticket.id);
                          }}
                          disabled={!!ticket.ai_summary}
                        >
                          <AIIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      
      {/* Ticket Detail Dialog */}
      <Dialog 
        open={dialogOpen} 
        onClose={() => setDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Ticket Details
        </DialogTitle>
        
        <DialogContent>
          {selectedTicket && (
            <Box>
              <Typography variant="h6" gutterBottom>
                {selectedTicket.title}
              </Typography>
              
              <Box display="flex" gap={2} mb={2}>
                <Chip label={selectedTicket.status} color={getStatusColor(selectedTicket.status) as any} />
                <Chip label={selectedTicket.priority} color={getPriorityColor(selectedTicket.priority) as any} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Customer: {selectedTicket.customer_id}
              </Typography>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Created: {new Date(selectedTicket.created_at).toLocaleString()}
              </Typography>
              
              {selectedTicket.ai_summary && (
                <Box mt={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    AI Summary
                  </Typography>
                  <Typography variant="body2" sx={{ 
                    backgroundColor: 'grey.100', 
                    p: 2, 
                    borderRadius: 1 
                  }}>
                    {selectedTicket.ai_summary}
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            Close
          </Button>
          {selectedTicket && !selectedTicket.ai_summary && (
            <Button
              variant="contained"
              startIcon={<AIIcon />}
              onClick={() => {
                handleSummarizeTicket(selectedTicket.id);
                setDialogOpen(false);
              }}
            >
              Generate Summary
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};