"""
Token Management Service

Security mitigations:
- #5: Refresh tokens not rotated
- #45: No token revocation mechanism

Provides:
- Refresh token rotation on every use
- Token revocation for logout
- Token family tracking to detect token reuse attacks
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.cache import core_cache
from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenService:
    """
    Service for managing refresh tokens with rotation and revocation.

    Security features:
    - Token rotation: Each refresh generates a new token
    - Token revocation: Tokens can be explicitly revoked
    - Token family tracking: Detects reuse of old tokens
    - Automatic expiration via TTL
    """

    # Redis key prefixes
    REFRESH_TOKEN_PREFIX = "token:refresh:"
    TOKEN_FAMILY_PREFIX = "token:family:"
    REVOKED_PREFIX = "token:revoked:"

    # Token family is a unique ID that groups related refresh tokens
    # If an old token from a family is used, all tokens in that family are revoked

    def __init__(self):
        self.token_ttl = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60  # in seconds

    def _hash_token(self, token: str) -> str:
        """Create a hash of the token for storage (don't store raw tokens)"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_token_id(self) -> str:
        """Generate a unique token identifier"""
        return secrets.token_urlsafe(32)

    async def create_refresh_token_entry(
        self, user_id: int, token_jti: str, family_id: Optional[str] = None
    ) -> str:
        """
        Create a refresh token entry in the store.

        Args:
            user_id: The user this token belongs to
            token_jti: The JWT ID (jti) of the token
            family_id: Optional family ID for token rotation tracking

        Returns:
            The family_id (new or existing)
        """
        if family_id is None:
            family_id = self._generate_token_id()

        token_data = {
            "user_id": user_id,
            "family_id": family_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_latest": True,
        }

        # Store token data
        token_key = f"{self.REFRESH_TOKEN_PREFIX}{token_jti}"
        await core_cache.set(token_key, token_data, ttl=self.token_ttl, prefix="auth")

        # Update family with latest token
        family_key = f"{self.TOKEN_FAMILY_PREFIX}{family_id}"
        family_data = {
            "user_id": user_id,
            "latest_jti": token_jti,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await core_cache.set(family_key, family_data, ttl=self.token_ttl, prefix="auth")

        logger.debug(
            f"Created refresh token entry for user {user_id}, family {family_id}"
        )
        return family_id

    async def validate_refresh_token(
        self, token_jti: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Validate a refresh token and check for reuse attacks.

        Args:
            token_jti: The JWT ID of the token
            user_id: The user ID from the token

        Returns:
            Dict with 'valid' bool and optionally 'family_id' and 'error'
        """
        # Check if token is explicitly revoked
        revoked_key = f"{self.REVOKED_PREFIX}{token_jti}"
        if await core_cache.exists(revoked_key, prefix="auth"):
            logger.warning(f"Attempt to use revoked token {token_jti[:8]}...")
            return {"valid": False, "error": "Token has been revoked"}

        # Get token data
        token_key = f"{self.REFRESH_TOKEN_PREFIX}{token_jti}"
        token_data = await core_cache.get(token_key, prefix="auth")

        if not token_data:
            # Token not in store - could be expired or never existed
            # We allow this for backwards compatibility with tokens issued before
            # this service was implemented, but log it
            logger.debug(f"Token {token_jti[:8]}... not found in store (may be legacy)")
            return {"valid": True, "family_id": None, "is_legacy": True}

        # Verify user matches
        if token_data.get("user_id") != user_id:
            logger.warning(
                f"Token user mismatch: token for user {token_data.get('user_id')}, "
                f"claimed by user {user_id}"
            )
            return {"valid": False, "error": "Token user mismatch"}

        family_id = token_data.get("family_id")

        # Check if this is the latest token in its family
        if family_id and not token_data.get("is_latest", True):
            # This is an old token being reused - potential attack!
            logger.warning(
                f"Refresh token reuse detected! Token {token_jti[:8]}... "
                f"in family {family_id[:8]}..."
            )
            # Revoke entire token family
            await self.revoke_token_family(family_id)
            return {
                "valid": False,
                "error": "Token reuse detected. All sessions revoked.",
            }

        return {"valid": True, "family_id": family_id}

    async def rotate_refresh_token(
        self, old_token_jti: str, new_token_jti: str, user_id: int, family_id: str
    ) -> bool:
        """
        Rotate a refresh token - mark old as used, register new as latest.

        Args:
            old_token_jti: The JTI of the token being replaced
            new_token_jti: The JTI of the new token
            user_id: The user ID
            family_id: The token family ID

        Returns:
            True if rotation succeeded
        """
        try:
            # Mark old token as not latest (but don't delete - for reuse detection)
            old_token_key = f"{self.REFRESH_TOKEN_PREFIX}{old_token_jti}"
            old_token_data = await core_cache.get(old_token_key, prefix="auth")
            if old_token_data:
                old_token_data["is_latest"] = False
                old_token_data["rotated_at"] = datetime.now(timezone.utc).isoformat()
                old_token_data["replaced_by"] = new_token_jti
                # Keep for a shorter time (just for reuse detection)
                await core_cache.set(
                    old_token_key, old_token_data, ttl=3600, prefix="auth"
                )  # 1 hour

            # Register new token
            await self.create_refresh_token_entry(user_id, new_token_jti, family_id)

            logger.debug(
                f"Rotated refresh token for user {user_id}: "
                f"{old_token_jti[:8]}... -> {new_token_jti[:8]}..."
            )
            return True

        except Exception as e:
            logger.error(f"Error rotating refresh token: {e}")
            return False

    async def revoke_token(self, token_jti: str) -> bool:
        """
        Revoke a specific refresh token.

        Args:
            token_jti: The JWT ID of the token to revoke

        Returns:
            True if revocation succeeded
        """
        try:
            # Add to revoked list
            revoked_key = f"{self.REVOKED_PREFIX}{token_jti}"
            await core_cache.set(
                revoked_key,
                {"revoked_at": datetime.now(timezone.utc).isoformat()},
                ttl=self.token_ttl,
                prefix="auth",
            )

            # Delete token data
            token_key = f"{self.REFRESH_TOKEN_PREFIX}{token_jti}"
            await core_cache.delete(token_key, prefix="auth")

            logger.info(f"Revoked refresh token {token_jti[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    async def revoke_token_family(self, family_id: str) -> bool:
        """
        Revoke all tokens in a family (used when token reuse is detected).

        Args:
            family_id: The token family ID

        Returns:
            True if revocation succeeded
        """
        try:
            # Mark family as revoked
            family_key = f"{self.TOKEN_FAMILY_PREFIX}{family_id}"
            family_data = await core_cache.get(family_key, prefix="auth")

            if family_data:
                latest_jti = family_data.get("latest_jti")
                if latest_jti:
                    await self.revoke_token(latest_jti)

            # Delete family data
            await core_cache.delete(family_key, prefix="auth")

            logger.warning(f"Revoked entire token family {family_id[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Error revoking token family: {e}")
            return False

    async def revoke_all_user_tokens(self, user_id: int) -> int:
        """
        Revoke all refresh tokens for a user (e.g., on password change).

        Note: This is a best-effort operation that relies on pattern matching.
        For complete revocation, consider also invalidating by user_id in verify.

        Args:
            user_id: The user whose tokens should be revoked

        Returns:
            Number of tokens revoked (approximate)
        """
        # Store user revocation timestamp for additional check
        user_revoke_key = f"token:user_revoked:{user_id}"
        await core_cache.set(
            user_revoke_key,
            {"revoked_at": datetime.now(timezone.utc).isoformat()},
            ttl=self.token_ttl,
            prefix="auth",
        )

        logger.info(f"Marked all tokens for user {user_id} as revoked")
        return 1  # Can't count exact number without scanning

    async def is_user_revoked_after(
        self, user_id: int, token_issued_at: datetime
    ) -> bool:
        """
        Check if user's tokens were revoked after a specific time.

        Args:
            user_id: The user ID
            token_issued_at: When the token was issued

        Returns:
            True if tokens were revoked after the token was issued
        """
        user_revoke_key = f"token:user_revoked:{user_id}"
        revoke_data = await core_cache.get(user_revoke_key, prefix="auth")

        if not revoke_data:
            return False

        revoked_at_str = revoke_data.get("revoked_at")
        if revoked_at_str:
            revoked_at = datetime.fromisoformat(revoked_at_str)
            return revoked_at > token_issued_at

        return False


# Global instance
token_service = TokenService()
