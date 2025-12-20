"""
Response Archival Task

Background task for archiving expired responses and cleaning up old archived responses.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.response import Response

logger = logging.getLogger(__name__)


class ResponseArchivalTask:
    """Task for managing response lifecycle (TTL, archival, deletion)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def archive_expired_responses(self) -> int:
        """Archive responses that have passed their TTL.

        Moves expired responses to archived state (sets archived_at timestamp).

        Returns:
            Number of responses archived
        """
        try:
            # Find expired responses that aren't archived yet
            now = datetime.utcnow()

            # Update expired responses to archived
            stmt = (
                update(Response)
                .where(
                    Response.expires_at < now,
                    Response.archived_at.is_(None),
                    Response.store == True  # Only archive stored responses
                )
                .values(archived_at=now)
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            archived_count = result.rowcount

            if archived_count > 0:
                logger.info(f"Archived {archived_count} expired responses")

            return archived_count

        except Exception as e:
            logger.error(f"Error archiving expired responses: {e}")
            await self.db.rollback()
            return 0

    async def delete_old_archived_responses(self) -> int:
        """Delete responses that have been archived for too long.

        Hard deletes responses that have been in archived state beyond retention period.

        Returns:
            Number of responses deleted
        """
        try:
            # Calculate cutoff date (responses archived more than 90 days ago)
            cutoff_date = datetime.utcnow() - Response.get_archived_retention()

            # Delete old archived responses
            stmt = delete(Response).where(
                Response.archived_at < cutoff_date,
                Response.archived_at.isnot(None)
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            deleted_count = result.rowcount

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old archived responses")

            return deleted_count

        except Exception as e:
            logger.error(f"Error deleting old archived responses: {e}")
            await self.db.rollback()
            return 0

    async def cleanup_non_stored_responses(self, retention_days: int = 7) -> int:
        """Clean up old non-stored responses (store=false).

        These are audit-only records that don't contain actual content.
        Keep them for a shorter period for billing/audit purposes.

        Args:
            retention_days: Days to retain non-stored responses (default: 7)

        Returns:
            Number of responses deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Delete old non-stored responses
            stmt = delete(Response).where(
                Response.store == False,
                Response.created_at < cutoff_date
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            deleted_count = result.rowcount

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old non-stored responses")

            return deleted_count

        except Exception as e:
            logger.error(f"Error deleting non-stored responses: {e}")
            await self.db.rollback()
            return 0

    async def cleanup_orphaned_chain_responses(self) -> int:
        """Clean up orphaned responses in chains.

        Finds responses in chains where the root has been deleted,
        and deletes the orphaned responses.

        Returns:
            Number of orphaned responses deleted
        """
        try:
            # Find responses with previous_response_id that don't exist
            stmt = select(Response).where(
                Response.previous_response_id.isnot(None)
            )

            result = await self.db.execute(stmt)
            responses = result.scalars().all()

            orphaned_ids = []

            for response in responses:
                # Check if previous response exists
                prev_stmt = select(Response).where(
                    Response.id == response.previous_response_id
                )
                prev_result = await self.db.execute(prev_stmt)
                prev_response = prev_result.scalar_one_or_none()

                if not prev_response:
                    orphaned_ids.append(response.id)

            # Delete orphaned responses
            if orphaned_ids:
                delete_stmt = delete(Response).where(Response.id.in_(orphaned_ids))
                result = await self.db.execute(delete_stmt)
                await self.db.commit()

                deleted_count = result.rowcount
                logger.info(f"Deleted {deleted_count} orphaned chain responses")
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Error cleaning up orphaned chains: {e}")
            await self.db.rollback()
            return 0

    async def run_full_cleanup(self) -> Dict[str, int]:
        """Run full cleanup process.

        Returns:
            Dictionary with counts of archived/deleted responses
        """
        results = {
            "archived": 0,
            "deleted_old_archived": 0,
            "deleted_non_stored": 0,
            "deleted_orphaned": 0
        }

        try:
            # 1. Archive expired responses
            results["archived"] = await self.archive_expired_responses()

            # 2. Delete old archived responses
            results["deleted_old_archived"] = await self.delete_old_archived_responses()

            # 3. Clean up non-stored responses
            results["deleted_non_stored"] = await self.cleanup_non_stored_responses()

            # 4. Clean up orphaned chain responses
            results["deleted_orphaned"] = await self.cleanup_orphaned_chain_responses()

            logger.info(f"Full cleanup completed: {results}")

            return results

        except Exception as e:
            logger.error(f"Error in full cleanup: {e}")
            return results


# Background task runner (can be called by scheduler)
async def run_response_archival_task(db: AsyncSession):
    """Run response archival task.

    This should be called by a scheduler (e.g., APScheduler, Celery, cron).

    Args:
        db: Database session
    """
    task = ResponseArchivalTask(db)
    return await task.run_full_cleanup()
