/**
 * Zammad Plugin Settings Component
 * Configuration interface for Zammad plugin
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  FormGroup,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  LinearProgress
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Save as SaveIcon,
  TestTube as TestIcon,
  Security as SecurityIcon,
  Sync as SyncIcon,
  Smart as AIIcon
} from '@mui/icons-material';

interface ZammadConfig {
  name: string;
  zammad_url: string;
  api_token: string;
  chatbot_id: string;
  ai_summarization: {
    enabled: boolean;
    model: string;
    max_tokens: number;
    auto_summarize: boolean;
  };
  sync_settings: {
    enabled: boolean;
    interval_hours: number;
    sync_articles: boolean;
    max_tickets_per_sync: number;
  };
  webhook_settings: {
    secret: string;
    enabled_events: string[];
  };
  notification_settings: {
    email_notifications: boolean;
    slack_webhook_url: string;
    notification_events: string[];
  };
}

const defaultConfig: ZammadConfig = {
  name: '',
  zammad_url: '',
  api_token: '',
  chatbot_id: '',
  ai_summarization: {
    enabled: true,
    model: 'gpt-3.5-turbo',
    max_tokens: 150,
    auto_summarize: true
  },
  sync_settings: {
    enabled: true,
    interval_hours: 2,
    sync_articles: true,
    max_tickets_per_sync: 100
  },
  webhook_settings: {
    secret: '',
    enabled_events: ['ticket.create', 'ticket.update']
  },
  notification_settings: {
    email_notifications: false,
    slack_webhook_url: '',
    notification_events: ['sync_error', 'api_error']
  }
};

export const ZammadSettings: React.FC = () => {
  const [config, setConfig] = useState<ZammadConfig>(defaultConfig);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  
  useEffect(() => {
    loadConfiguration();
  }, []);
  
  const loadConfiguration = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/plugins/zammad/configurations');
      if (response.ok) {
        const data = await response.json();
        if (data.configurations.length > 0) {
          // Load the first (active) configuration
          const loadedConfig = data.configurations[0];
          setConfig({
            ...defaultConfig,
            ...loadedConfig
          });
        }
      }
    } catch (err) {
      setError('Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };
  
  const handleConfigChange = (path: string, value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current: any = newConfig;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      return newConfig;
    });
  };
  
  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    
    try {
      const response = await fetch('/api/v1/plugins/zammad/configurations/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          zammad_url: config.zammad_url,
          api_token: config.api_token
        })
      });
      
      const result = await response.json();
      setTestResult(result);
      
      if (!result.success) {
        setError(`Connection test failed: ${result.error}`);
      }
    } catch (err) {
      setError('Connection test failed');
    } finally {
      setTesting(false);
    }
  };
  
  const handleSaveConfiguration = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    
    try {
      const response = await fetch('/api/v1/plugins/zammad/configurations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        setSuccess('Configuration saved successfully');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save configuration');
      }
    } catch (err) {
      setError('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };
  
  const handleArrayToggle = (path: string, value: string) => {
    const currentArray = path.split('.').reduce((obj, key) => obj[key], config) as string[];
    const newArray = currentArray.includes(value)
      ? currentArray.filter(item => item !== value)
      : [...currentArray, value];
    handleConfigChange(path, newArray);
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>Zammad Settings</Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Zammad Settings
        </Typography>
        
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<TestIcon />}
            onClick={handleTestConnection}
            disabled={testing || !config.zammad_url || !config.api_token}
          >
            {testing ? 'Testing...' : 'Test Connection'}
          </Button>
          
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSaveConfiguration}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </Button>
        </Box>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert severity="success" sx={{ mb: 3 }}>
          {success}
        </Alert>
      )}
      
      {testResult && (
        <Alert 
          severity={testResult.success ? 'success' : 'error'} 
          sx={{ mb: 3 }}
        >
          {testResult.success 
            ? `Connection successful! User: ${testResult.user}, Version: ${testResult.zammad_version}`
            : `Connection failed: ${testResult.error}`
          }
        </Alert>
      )}
      
      {/* Basic Configuration */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Basic Configuration
          </Typography>
          
          <Box display="flex" flexDirection="column" gap={3}>
            <TextField
              label="Configuration Name"
              value={config.name}
              onChange={(e) => handleConfigChange('name', e.target.value)}
              fullWidth
              required
            />
            
            <TextField
              label="Zammad URL"
              value={config.zammad_url}
              onChange={(e) => handleConfigChange('zammad_url', e.target.value)}
              fullWidth
              required
              placeholder="https://company.zammad.com"
            />
            
            <TextField
              label="API Token"
              type="password"
              value={config.api_token}
              onChange={(e) => handleConfigChange('api_token', e.target.value)}
              fullWidth
              required
              helperText="Zammad API token with ticket read/write permissions"
            />
            
            <TextField
              label="Chatbot ID"
              value={config.chatbot_id}
              onChange={(e) => handleConfigChange('chatbot_id', e.target.value)}
              fullWidth
              required
              helperText="Platform chatbot ID for AI summarization"
            />
          </Box>
        </CardContent>
      </Card>
      
      {/* AI Summarization Settings */}
      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box display="flex" alignItems="center" gap={2}>
            <AIIcon />
            <Typography variant="h6">AI Summarization</Typography>
            <Chip 
              label={config.ai_summarization.enabled ? 'Enabled' : 'Disabled'} 
              color={config.ai_summarization.enabled ? 'success' : 'default'}
              size="small"
            />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Box display="flex" flexDirection="column" gap={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.ai_summarization.enabled}
                  onChange={(e) => handleConfigChange('ai_summarization.enabled', e.target.checked)}
                />
              }
              label="Enable AI Summarization"
            />
            
            <FormControl fullWidth>
              <InputLabel>AI Model</InputLabel>
              <Select
                value={config.ai_summarization.model}
                onChange={(e) => handleConfigChange('ai_summarization.model', e.target.value)}
                label="AI Model"
              >
                <MenuItem value="gpt-3.5-turbo">GPT-3.5 Turbo</MenuItem>
                <MenuItem value="gpt-4">GPT-4</MenuItem>
                <MenuItem value="claude-3-sonnet">Claude 3 Sonnet</MenuItem>
              </Select>
            </FormControl>
            
            <TextField
              label="Max Summary Tokens"
              type="number"
              value={config.ai_summarization.max_tokens}
              onChange={(e) => handleConfigChange('ai_summarization.max_tokens', parseInt(e.target.value))}
              inputProps={{ min: 50, max: 500 }}
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={config.ai_summarization.auto_summarize}
                  onChange={(e) => handleConfigChange('ai_summarization.auto_summarize', e.target.checked)}
                />
              }
              label="Auto-summarize New Tickets"
            />
          </Box>
        </AccordionDetails>
      </Accordion>
      
      {/* Sync Settings */}
      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box display="flex" alignItems="center" gap={2}>
            <SyncIcon />
            <Typography variant="h6">Sync Settings</Typography>
            <Chip 
              label={config.sync_settings.enabled ? 'Enabled' : 'Disabled'} 
              color={config.sync_settings.enabled ? 'success' : 'default'}
              size="small"
            />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Box display="flex" flexDirection="column" gap={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.sync_settings.enabled}
                  onChange={(e) => handleConfigChange('sync_settings.enabled', e.target.checked)}
                />
              }
              label="Enable Automatic Sync"
            />
            
            <TextField
              label="Sync Interval (Hours)"
              type="number"
              value={config.sync_settings.interval_hours}
              onChange={(e) => handleConfigChange('sync_settings.interval_hours', parseInt(e.target.value))}
              inputProps={{ min: 1, max: 24 }}
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={config.sync_settings.sync_articles}
                  onChange={(e) => handleConfigChange('sync_settings.sync_articles', e.target.checked)}
                />
              }
              label="Sync Ticket Articles"
            />
            
            <TextField
              label="Max Tickets Per Sync"
              type="number"
              value={config.sync_settings.max_tickets_per_sync}
              onChange={(e) => handleConfigChange('sync_settings.max_tickets_per_sync', parseInt(e.target.value))}
              inputProps={{ min: 10, max: 1000 }}
            />
          </Box>
        </AccordionDetails>
      </Accordion>
      
      {/* Webhook Settings */}
      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box display="flex" alignItems="center" gap={2}>
            <SecurityIcon />
            <Typography variant="h6">Webhook Settings</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Box display="flex" flexDirection="column" gap={3}>
            <TextField
              label="Webhook Secret"
              type="password"
              value={config.webhook_settings.secret}
              onChange={(e) => handleConfigChange('webhook_settings.secret', e.target.value)}
              fullWidth
              helperText="Secret for webhook signature validation"
            />
            
            <Typography variant="subtitle2">Enabled Webhook Events</Typography>
            <FormGroup>
              {['ticket.create', 'ticket.update', 'ticket.close', 'article.create'].map((event) => (
                <FormControlLabel
                  key={event}
                  control={
                    <Switch
                      checked={config.webhook_settings.enabled_events.includes(event)}
                      onChange={() => handleArrayToggle('webhook_settings.enabled_events', event)}
                    />
                  }
                  label={event}
                />
              ))}
            </FormGroup>
          </Box>
        </AccordionDetails>
      </Accordion>
      
      {/* Notification Settings */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Notification Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box display="flex" flexDirection="column" gap={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.notification_settings.email_notifications}
                  onChange={(e) => handleConfigChange('notification_settings.email_notifications', e.target.checked)}
                />
              }
              label="Email Notifications"
            />
            
            <TextField
              label="Slack Webhook URL"
              value={config.notification_settings.slack_webhook_url}
              onChange={(e) => handleConfigChange('notification_settings.slack_webhook_url', e.target.value)}
              fullWidth
              placeholder="https://hooks.slack.com/services/..."
            />
            
            <Typography variant="subtitle2">Notification Events</Typography>
            <FormGroup>
              {['sync_error', 'api_error', 'new_tickets', 'summarization_complete'].map((event) => (
                <FormControlLabel
                  key={event}
                  control={
                    <Switch
                      checked={config.notification_settings.notification_events.includes(event)}
                      onChange={() => handleArrayToggle('notification_settings.notification_events', event)}
                    />
                  }
                  label={event.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                />
              ))}
            </FormGroup>
          </Box>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};