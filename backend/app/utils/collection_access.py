"""
Collection ACL utilities.

Single source of truth for deciding whether a user (or an unauthenticated
API caller) may read documents from a given RagCollection.

Visibility semantics
--------------------
public        – anyone, including unauthenticated callers (API keys without a user)
team          – any authenticated user (default; matches legacy behaviour)
role_required – authenticated users whose role.level >= collection.allowed_role_level
private       – only the owning user and admin / super_admin roles
"""

from typing import Optional

from app.models.rag_collection import CollectionVisibility, RagCollection
from app.models.user import User

# Role hierarchy used for 'role_required' comparisons
_ROLE_LEVEL_ORDER = {
    "read_only": 1,
    "user": 2,
    "admin": 3,
    "super_admin": 4,
}


def can_user_access_collection(
    collection: RagCollection,
    user: Optional[User],
) -> bool:
    """
    Return True if *user* is allowed to read documents from *collection*.

    Parameters
    ----------
    collection:
        The RagCollection to check.
    user:
        The authenticated User, or None for unauthenticated / API-key-only callers.
    """
    visibility = collection.visibility or CollectionVisibility.TEAM

    # ------------------------------------------------------------------ public
    if visibility == CollectionVisibility.PUBLIC:
        return True

    # All remaining tiers require authentication
    if user is None:
        return False

    # Superusers bypass everything
    if user.is_superuser:
        return True

    # Admins (role level >= admin) can always read any collection
    if user.role and user.role.level in ("admin", "super_admin"):
        return True

    # ------------------------------------------------------------------- team
    if visibility == CollectionVisibility.TEAM:
        return user.is_active

    # ----------------------------------------------------------------- private
    if visibility == CollectionVisibility.PRIVATE:
        return collection.owner_user_id is not None and collection.owner_user_id == user.id

    # --------------------------------------------------------- role_required
    if visibility == CollectionVisibility.ROLE_REQUIRED:
        required = collection.allowed_role_level
        if not required:
            # misconfigured — fall back to team behaviour
            return user.is_active
        if not user.role:
            return False
        user_level = _ROLE_LEVEL_ORDER.get(user.role.level, 0)
        required_level = _ROLE_LEVEL_ORDER.get(required, 0)
        return user_level >= required_level

    # Unknown visibility value — deny by default
    return False


def filter_accessible_collections(
    collections: list[RagCollection],
    user: Optional[User],
) -> list[RagCollection]:
    """Filter a list of collections down to those the user may access."""
    return [c for c in collections if can_user_access_collection(c, user)]
