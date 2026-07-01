"""
Alert Service for Token Stats System

Provides alerting functionality for critical events:
- Budget exceeded notifications
- Pricing sync failures
- High error rates

Supports multiple notification channels:
- Email (SMTP)
- Slack webhooks
- PagerDuty
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    """Alert types"""

    BUDGET_EXCEEDED = "budget_exceeded"
    BUDGET_WARNING = "budget_warning"
    PRICING_SYNC_FAILURE = "pricing_sync_failure"
    HIGH_ERROR_RATE = "high_error_rate"
    SYSTEM_ERROR = "system_error"


class AlertService:
    """
    Service for sending alerts through multiple channels.

    Alerts can be sent via:
    - Email (if SMTP is configured)
    - Slack (if webhook URL is configured)
    - PagerDuty (if integration key is configured)
    """

    def __init__(self):
        """Initialize alert service with configuration"""
        self.email_enabled = getattr(settings, "ALERT_EMAIL_ENABLED", False)
        self.slack_webhook_url = getattr(settings, "ALERT_SLACK_WEBHOOK_URL", None)
        self.pagerduty_key = getattr(settings, "ALERT_PAGERDUTY_KEY", None)
        self.smtp_host = getattr(settings, "ALERT_SMTP_HOST", None)
        self.smtp_port = getattr(settings, "ALERT_SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "ALERT_SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "ALERT_SMTP_PASSWORD", None)
        self.alert_from_email = getattr(
            settings, "ALERT_FROM_EMAIL", "alerts@enclava.com"
        )
        self.alert_to_emails = getattr(settings, "ALERT_TO_EMAILS", [])

        # Parse comma-separated email list if provided as string
        if isinstance(self.alert_to_emails, str):
            self.alert_to_emails = [
                e.strip() for e in self.alert_to_emails.split(",") if e.strip()
            ]

    async def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Send alert through all configured channels.

        Args:
            alert_type: Type of alert
            severity: Alert severity level
            message: Human-readable alert message
            context: Additional context data
        """
        if context is None:
            context = {}

        # Add timestamp to context
        context["timestamp"] = datetime.now(timezone.utc).isoformat()
        context["alert_type"] = alert_type.value
        context["severity"] = severity.value

        logger.info(
            f"Sending alert: type={alert_type.value}, severity={severity.value}, message={message}"
        )

        # Send through all configured channels (non-blocking)
        tasks = []

        if self.email_enabled and self.alert_to_emails:
            tasks.append(self._send_email_alert(message, context))

        if self.slack_webhook_url:
            tasks.append(self._send_slack_alert(message, severity, context))

        if self.pagerduty_key and severity == AlertSeverity.CRITICAL:
            tasks.append(self._send_pagerduty_alert(message, alert_type, context))

        if tasks:
            # Execute all alert tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Alert delivery failed for channel {i}: {result}")
        else:
            logger.warning("No alert channels configured, alert not sent")

    async def send_budget_exceeded_alert(
        self,
        budget_id: int,
        budget_name: str,
        user_id: int,
        limit_cents: int,
        usage_cents: int,
        requested_cents: int,
    ):
        """
        Send alert when a budget is exceeded.

        Args:
            budget_id: Budget identifier
            budget_name: Budget name
            user_id: User who owns the budget
            limit_cents: Budget limit in cents
            usage_cents: Current usage in cents
            requested_cents: Requested amount that would exceed
        """
        message = (
            f"Budget Exceeded: '{budget_name}'\n"
            f"Budget ID: {budget_id}\n"
            f"User ID: {user_id}\n"
            f"Limit: ${limit_cents/100:.2f}\n"
            f"Current Usage: ${usage_cents/100:.2f}\n"
            f"Requested: ${requested_cents/100:.4f}\n"
            f"Over by: ${(usage_cents + requested_cents - limit_cents)/100:.2f}"
        )

        context = {
            "budget_id": budget_id,
            "budget_name": budget_name,
            "user_id": user_id,
            "limit_cents": limit_cents,
            "usage_cents": usage_cents,
            "requested_cents": requested_cents,
            "over_by_cents": usage_cents + requested_cents - limit_cents,
        }

        await self.send_alert(
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=AlertSeverity.CRITICAL,
            message=message,
            context=context,
        )

    async def send_budget_warning_alert(
        self,
        budget_id: int,
        budget_name: str,
        user_id: int,
        limit_cents: int,
        usage_cents: int,
        warning_threshold_percent: float,
    ):
        """
        Send warning when budget approaches limit.

        Args:
            budget_id: Budget identifier
            budget_name: Budget name
            user_id: User who owns the budget
            limit_cents: Budget limit in cents
            usage_cents: Current usage in cents
            warning_threshold_percent: Warning threshold percentage
        """
        usage_percent = (usage_cents / limit_cents * 100) if limit_cents > 0 else 0

        message = (
            f"Budget Warning: '{budget_name}'\n"
            f"Budget ID: {budget_id}\n"
            f"User ID: {user_id}\n"
            f"Usage: ${usage_cents/100:.2f} / ${limit_cents/100:.2f} ({usage_percent:.1f}%)\n"
            f"Threshold: {warning_threshold_percent:.0f}%\n"
            f"Remaining: ${(limit_cents - usage_cents)/100:.2f}"
        )

        context = {
            "budget_id": budget_id,
            "budget_name": budget_name,
            "user_id": user_id,
            "limit_cents": limit_cents,
            "usage_cents": usage_cents,
            "usage_percent": usage_percent,
            "warning_threshold_percent": warning_threshold_percent,
            "remaining_cents": limit_cents - usage_cents,
        }

        await self.send_alert(
            alert_type=AlertType.BUDGET_WARNING,
            severity=AlertSeverity.WARNING,
            message=message,
            context=context,
        )

    async def send_pricing_sync_failure_alert(
        self,
        provider: str,
        error: str,
        duration_seconds: Optional[float] = None,
    ):
        """
        Send alert when pricing sync fails.

        Args:
            provider: Provider identifier
            error: Error message
            duration_seconds: Sync duration before failure
        """
        message = f"Pricing Sync Failed: {provider}\n" f"Error: {error}\n"

        if duration_seconds is not None:
            message += f"Duration: {duration_seconds:.2f}s\n"

        context = {
            "provider": provider,
            "error": error,
            "duration_seconds": duration_seconds,
        }

        await self.send_alert(
            alert_type=AlertType.PRICING_SYNC_FAILURE,
            severity=AlertSeverity.CRITICAL,
            message=message,
            context=context,
        )

    async def send_high_error_rate_alert(
        self,
        provider: str,
        model: str,
        error_rate_percent: float,
        error_count: int,
        total_count: int,
        time_window_minutes: int = 5,
    ):
        """
        Send alert when error rate is high.

        Args:
            provider: Provider identifier
            model: Model name
            error_rate_percent: Error rate percentage
            error_count: Number of errors
            total_count: Total requests
            time_window_minutes: Time window for measurement
        """
        message = (
            f"High Error Rate Detected\n"
            f"Provider: {provider}\n"
            f"Model: {model}\n"
            f"Error Rate: {error_rate_percent:.1f}%\n"
            f"Errors: {error_count} / {total_count} requests\n"
            f"Time Window: {time_window_minutes} minutes"
        )

        context = {
            "provider": provider,
            "model": model,
            "error_rate_percent": error_rate_percent,
            "error_count": error_count,
            "total_count": total_count,
            "time_window_minutes": time_window_minutes,
        }

        await self.send_alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.WARNING,
            message=message,
            context=context,
        )

    async def _send_email_alert(
        self,
        message: str,
        context: Dict[str, Any],
    ):
        """
        Send alert via email.

        Args:
            message: Alert message
            context: Alert context
        """
        try:
            if not self.smtp_host or not self.alert_to_emails:
                logger.debug("Email alerts not configured")
                return

            # Import email libraries only when needed
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            # Create email message
            msg = MIMEMultipart()
            msg["From"] = self.alert_from_email
            msg["To"] = ", ".join(self.alert_to_emails)
            msg["Subject"] = (
                f"[{context.get('severity', 'ALERT').upper()}] {context.get('alert_type', 'Alert')}"
            )

            # Build email body
            body = f"{message}\n\n"
            body += "Additional Details:\n"
            for key, value in context.items():
                body += f"  {key}: {value}\n"

            msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent to {len(self.alert_to_emails)} recipients")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            raise

    async def _send_slack_alert(
        self,
        message: str,
        severity: AlertSeverity,
        context: Dict[str, Any],
    ):
        """
        Send alert via Slack webhook.

        Args:
            message: Alert message
            severity: Alert severity
            context: Alert context
        """
        try:
            if not self.slack_webhook_url:
                logger.debug("Slack alerts not configured")
                return

            # Color code by severity
            color_map = {
                AlertSeverity.CRITICAL: "#FF0000",  # Red
                AlertSeverity.WARNING: "#FFA500",  # Orange
                AlertSeverity.INFO: "#0000FF",  # Blue
            }
            color = color_map.get(severity, "#808080")

            # Build Slack message
            slack_message = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{severity.value.upper()}] {context.get('alert_type', 'Alert')}",
                        "text": message,
                        "fields": [
                            {"title": key, "value": str(value), "short": True}
                            for key, value in context.items()
                            if key not in ["timestamp", "alert_type", "severity"]
                        ],
                        "footer": "Enclava Token Stats",
                        "ts": int(datetime.now(timezone.utc).timestamp()),
                    }
                ]
            }

            # Send to Slack
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json=slack_message,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info("Slack alert sent successfully")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            raise

    async def _send_pagerduty_alert(
        self,
        message: str,
        alert_type: AlertType,
        context: Dict[str, Any],
    ):
        """
        Send alert via PagerDuty Events API v2.

        Args:
            message: Alert message
            alert_type: Alert type
            context: Alert context
        """
        try:
            if not self.pagerduty_key:
                logger.debug("PagerDuty alerts not configured")
                return

            # Build PagerDuty event
            event = {
                "routing_key": self.pagerduty_key,
                "event_action": "trigger",
                "payload": {
                    "summary": message[:1024],  # PagerDuty has 1024 char limit
                    "source": "enclava-token-stats",
                    "severity": "critical",
                    "custom_details": context,
                },
            }

            # Send to PagerDuty
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=event,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info("PagerDuty alert sent successfully")

        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")
            raise


# Singleton instance
_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """
    Get or create the alert service singleton.

    Returns:
        AlertService instance
    """
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
