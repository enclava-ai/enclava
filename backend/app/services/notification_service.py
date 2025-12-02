"""
Notification Service
Multi-channel notification system with email, webhooks, and other providers
"""
import asyncio
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from jinja2 import Template, Environment, DictLoader
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from fastapi import HTTPException, status

from app.models.notification import (
    Notification,
    NotificationTemplate,
    NotificationChannel,
    NotificationType,
    NotificationStatus,
    NotificationPriority,
)
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing and sending notifications"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.jinja_env = Environment(loader=DictLoader({}))

    async def send_notification(
        self,
        recipients: List[str],
        subject: Optional[str] = None,
        body: str = "",
        html_body: Optional[str] = None,
        notification_type: NotificationType = NotificationType.EMAIL,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        template_name: Optional[str] = None,
        template_variables: Optional[Dict[str, Any]] = None,
        channel_name: Optional[str] = None,
        user_id: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Notification:
        """Send a notification through specified channel"""

        # Get or create channel
        channel = await self._get_or_default_channel(notification_type, channel_name)
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active channel found for type: {notification_type}",
            )

        # Process template if specified
        if template_name:
            template = await self._get_template(template_name)
            if template:
                rendered = await self._render_template(
                    template, template_variables or {}
                )
                subject = subject or rendered.get("subject")
                body = body or rendered.get("body")
                html_body = html_body or rendered.get("html_body")

        # Create notification record
        notification = Notification(
            subject=subject,
            body=body,
            html_body=html_body,
            recipients=recipients,
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            channel_id=channel.id,
            user_id=user_id,
            metadata=metadata or {},
            tags=tags or [],
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # Send immediately if not scheduled
        if scheduled_at is None or scheduled_at <= datetime.utcnow():
            await self._deliver_notification(notification)

        return notification

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        **kwargs,
    ) -> Notification:
        """Send email notification"""

        notification = await self.send_notification(
            recipients=recipients,
            subject=subject,
            body=body,
            html_body=html_body,
            notification_type=NotificationType.EMAIL,
            **kwargs,
        )

        if cc_recipients:
            notification.cc_recipients = cc_recipients
        if bcc_recipients:
            notification.bcc_recipients = bcc_recipients

        await self.db.commit()
        return notification

    async def send_webhook(
        self,
        webhook_url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Notification:
        """Send webhook notification"""

        # Use webhook URL as recipient
        notification = await self.send_notification(
            recipients=[webhook_url],
            body=json.dumps(payload),
            notification_type=NotificationType.WEBHOOK,
            metadata={"headers": headers or {}},
            **kwargs,
        )

        return notification

    async def send_slack_message(
        self, channel: str, message: str, **kwargs
    ) -> Notification:
        """Send Slack message"""

        notification = await self.send_notification(
            recipients=[channel],
            body=message,
            notification_type=NotificationType.SLACK,
            **kwargs,
        )

        return notification

    async def process_scheduled_notifications(self):
        """Process notifications that are scheduled for delivery"""

        now = datetime.utcnow()

        # Get pending scheduled notifications that are due
        stmt = select(Notification).where(
            and_(
                Notification.status == NotificationStatus.PENDING,
                Notification.scheduled_at <= now,
                or_(Notification.expires_at.is_(None), Notification.expires_at > now),
            )
        )

        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        processed_count = 0
        for notification in notifications:
            try:
                await self._deliver_notification(notification)
                processed_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to process scheduled notification {notification.id}: {e}"
                )

        logger.info(f"Processed {processed_count} scheduled notifications")
        return processed_count

    async def retry_failed_notifications(self):
        """Retry failed notifications that can be retried"""

        # Get failed notifications that can be retried
        stmt = select(Notification).where(
            and_(
                Notification.status.in_(
                    [NotificationStatus.FAILED, NotificationStatus.RETRY]
                ),
                Notification.attempts < Notification.max_attempts,
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.utcnow(),
                ),
            )
        )

        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        retried_count = 0
        for notification in notifications:
            # Check retry delay
            if notification.failed_at:
                retry_delay = timedelta(
                    minutes=notification.channel.retry_delay_minutes
                )
                if datetime.utcnow() - notification.failed_at < retry_delay:
                    continue

            try:
                await self._deliver_notification(notification)
                retried_count += 1
            except Exception as e:
                logger.error(f"Failed to retry notification {notification.id}: {e}")

        logger.info(f"Retried {retried_count} failed notifications")
        return retried_count

    async def _deliver_notification(self, notification: Notification):
        """Deliver a notification through its channel"""

        channel = await self._get_channel_by_id(notification.channel_id)
        if not channel or not channel.is_active:
            notification.mark_failed("Channel not available")
            await self.db.commit()
            return

        try:
            if channel.notification_type == NotificationType.EMAIL:
                await self._send_email(notification, channel)
            elif channel.notification_type == NotificationType.WEBHOOK:
                await self._send_webhook(notification, channel)
            elif channel.notification_type == NotificationType.SLACK:
                await self._send_slack(notification, channel)
            else:
                raise ValueError(
                    f"Unsupported notification type: {channel.notification_type}"
                )

            # Update channel stats
            channel.update_stats(success=True)

        except Exception as e:
            logger.error(f"Failed to deliver notification {notification.id}: {e}")
            notification.mark_failed(str(e))
            channel.update_stats(success=False, error_message=str(e))

        await self.db.commit()

    async def _send_email(
        self, notification: Notification, channel: NotificationChannel
    ):
        """Send email through SMTP"""

        config = channel.config
        credentials = channel.credentials or {}

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = notification.subject or "No Subject"
        msg["From"] = config.get("from_email", "noreply@example.com")
        msg["To"] = ", ".join(notification.recipients)

        if notification.cc_recipients:
            msg["Cc"] = ", ".join(notification.cc_recipients)

        # Add text part
        text_part = MIMEText(notification.body, "plain", "utf-8")
        msg.attach(text_part)

        # Add HTML part if available
        if notification.html_body:
            html_part = MIMEText(notification.html_body, "html", "utf-8")
            msg.attach(html_part)

        # Send email
        smtp_host = config.get("smtp_host", "localhost")
        smtp_port = config.get("smtp_port", 587)
        username = credentials.get("username")
        password = credentials.get("password")
        use_tls = config.get("use_tls", True)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)

            all_recipients = notification.recipients[:]
            if notification.cc_recipients:
                all_recipients.extend(notification.cc_recipients)
            if notification.bcc_recipients:
                all_recipients.extend(notification.bcc_recipients)

            server.sendmail(msg["From"], all_recipients, msg.as_string())

        notification.mark_sent()

    async def _send_webhook(
        self, notification: Notification, channel: NotificationChannel
    ):
        """Send webhook HTTP request"""

        webhook_url = notification.recipients[0]  # URL is stored as recipient
        headers = notification.metadata.get("headers", {})
        headers.setdefault("Content-Type", "application/json")

        # Parse body as JSON payload
        try:
            payload = json.loads(notification.body)
        except json.JSONDecodeError:
            payload = {"message": notification.body}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status >= 400:
                    raise Exception(
                        f"Webhook failed with status {response.status}: {await response.text()}"
                    )

                external_id = response.headers.get("X-Message-ID")
                notification.mark_sent(external_id)

    async def _send_slack(
        self, notification: Notification, channel: NotificationChannel
    ):
        """Send Slack message"""

        credentials = channel.credentials or {}
        webhook_url = credentials.get("webhook_url")

        if not webhook_url:
            raise ValueError("Slack webhook URL not configured")

        payload = {
            "channel": notification.recipients[0],
            "text": notification.body,
            "username": channel.config.get("username", "Enclava Bot"),
        }

        if notification.subject:
            payload["attachments"] = [
                {"title": notification.subject, "text": notification.body}
            ]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status >= 400:
                    raise Exception(
                        f"Slack webhook failed with status {response.status}: {await response.text()}"
                    )

                notification.mark_sent()

    async def _get_or_default_channel(
        self, notification_type: NotificationType, channel_name: Optional[str] = None
    ) -> Optional[NotificationChannel]:
        """Get specific channel or default for notification type"""

        if channel_name:
            stmt = select(NotificationChannel).where(
                and_(
                    NotificationChannel.name == channel_name,
                    NotificationChannel.is_active == True,
                )
            )
        else:
            stmt = select(NotificationChannel).where(
                and_(
                    NotificationChannel.notification_type == notification_type,
                    NotificationChannel.is_active == True,
                    NotificationChannel.is_default == True,
                )
            )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_channel_by_id(
        self, channel_id: int
    ) -> Optional[NotificationChannel]:
        """Get channel by ID"""

        stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_template(self, template_name: str) -> Optional[NotificationTemplate]:
        """Get notification template by name"""

        stmt = select(NotificationTemplate).where(
            and_(
                NotificationTemplate.name == template_name,
                NotificationTemplate.is_active == True,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _render_template(
        self, template: NotificationTemplate, variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render template with variables"""

        rendered = {}

        # Render subject
        if template.subject_template:
            subject_tmpl = Template(template.subject_template)
            rendered["subject"] = subject_tmpl.render(**variables)

        # Render body
        body_tmpl = Template(template.body_template)
        rendered["body"] = body_tmpl.render(**variables)

        # Render HTML body
        if template.html_template:
            html_tmpl = Template(template.html_template)
            rendered["html_body"] = html_tmpl.render(**variables)

        return rendered

    # Management methods

    async def create_template(
        self,
        name: str,
        display_name: str,
        notification_type: NotificationType,
        body_template: str,
        subject_template: Optional[str] = None,
        html_template: Optional[str] = None,
        description: Optional[str] = None,
        default_priority: NotificationPriority = NotificationPriority.NORMAL,
        variables: Optional[Dict[str, Any]] = None,
    ) -> NotificationTemplate:
        """Create notification template"""

        template = NotificationTemplate(
            name=name,
            display_name=display_name,
            description=description,
            notification_type=notification_type,
            subject_template=subject_template,
            body_template=body_template,
            html_template=html_template,
            default_priority=default_priority,
            variables=variables or {},
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    async def create_channel(
        self,
        name: str,
        display_name: str,
        notification_type: NotificationType,
        config: Dict[str, Any],
        credentials: Optional[Dict[str, Any]] = None,
        is_default: bool = False,
    ) -> NotificationChannel:
        """Create notification channel"""

        channel = NotificationChannel(
            name=name,
            display_name=display_name,
            notification_type=notification_type,
            config=config,
            credentials=credentials,
            is_default=is_default,
        )

        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)

        return channel

    async def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""

        # Total notifications
        total_notifications = await self.db.execute(select(func.count(Notification.id)))
        total_count = total_notifications.scalar()

        # Notifications by status
        status_counts = await self.db.execute(
            select(Notification.status, func.count(Notification.id)).group_by(
                Notification.status
            )
        )
        status_stats = dict(status_counts.all())

        # Recent notifications (last 24h)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_notifications = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.created_at >= twenty_four_hours_ago
            )
        )
        recent_count = recent_notifications.scalar()

        # Channel performance
        channel_stats = await self.db.execute(
            select(
                NotificationChannel.name,
                NotificationChannel.success_count,
                NotificationChannel.failure_count,
            )
        )
        channel_performance = [
            {
                "name": name,
                "success_count": success,
                "failure_count": failure,
                "success_rate": success / (success + failure)
                if (success + failure) > 0
                else 0,
            }
            for name, success, failure in channel_stats.all()
        ]

        return {
            "total_notifications": total_count,
            "status_breakdown": status_stats,
            "recent_notifications": recent_count,
            "channel_performance": channel_performance,
        }
