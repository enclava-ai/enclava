"""
User Management Service
Handles business logic for user and role management operations
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc
from fastapi import HTTPException, status
from datetime import datetime, timedelta
import bcrypt
from app.models.user import User
from app.models.role import Role, RoleLevel
from app.models.audit_log import AuditLog, AuditAction, AuditSeverity
from app.core.security import create_access_token, get_password_hash
from pydantic import EmailStr


class UserManagementService:
    """Service for managing users and roles"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # User Management Methods
    async def create_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
        role_id: Optional[int] = None,
        custom_permissions: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """Create a new user with validation"""

        # Check if email or username already exists
        existing_user = await self.get_user_by_email_or_username(email, username)
        if existing_user:
            if existing_user.email == email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        # Validate role if provided
        if role_id:
            role = await self.get_role_by_id(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role specified",
                )
            if not role.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected role is not active",
                )

        # Hash password
        hashed_password = get_password_hash(password)

        # Create user
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role_id=role_id,
            custom_permissions=custom_permissions or {},
            is_active=is_active,
            is_verified=is_verified,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Log user creation audit event
        await self._log_audit_event(
            user_id=None,  # System creation or could be passed from context
            action=AuditAction.CREATE,
            resource_type="user",
            resource_id=str(user.id),
            description=f"User created: {email}",
            details={
                "email": email,
                "username": username,
                "role_id": role_id,
                "is_active": is_active,
                "is_verified": is_verified,
            },
            severity=AuditSeverity.MEDIUM,
        )

        return user

    async def authenticate_user(
        self, email_or_username: str, password: str
    ) -> Optional[User]:
        """Authenticate user with email/username and password"""

        # Find user by email or username
        result = await self.db.execute(
            select(User).where(
                or_(User.email == email_or_username, User.username == email_or_username)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Check if account is locked
        if user.account_locked:
            if (
                user.account_locked_until
                and user.account_locked_until > datetime.utcnow()
            ):
                return None  # Account is still locked
            else:
                # Unlock account if lock period has expired
                user.unlock_account()
                await self.db.commit()

        # Check if user is active
        if not user.is_active:
            return None

        # Verify password
        if not bcrypt.checkpw(
            password.encode("utf-8"), user.hashed_password.encode("utf-8")
        ):
            user.record_failed_login()
            await self.db.commit()
            return None

        # Reset failed login attempts on successful login
        user.reset_failed_logins()
        user.update_last_login()
        await self.db.commit()

        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_user_by_email_or_username(
        self, email: str, username: str
    ) -> Optional[User]:
        """Get user by email or username"""
        result = await self.db.execute(
            select(User).where(or_(User.email == email, User.username == username))
        )
        return result.scalar_one_or_none()

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        role_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[User]:
        """Get users with filtering and pagination"""

        query = select(User).options(selectinload(User.role))

        # Apply filters
        if role_id:
            query = query.where(User.role_id == role_id)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if search:
            query = query.where(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.username.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%"),
                )
            )

        # Order and pagination
        query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        role_id: Optional[int] = None,
        custom_permissions: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
    ) -> User:
        """Update user information"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check for email/username conflicts
        if email and email != user.email:
            existing_user = await self.get_user_by_email(email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            user.email = email

        if username and username != user.username:
            existing_user = await self.get_user_by_username(username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
            user.username = username

        # Update fields
        if full_name is not None:
            user.full_name = full_name

        if role_id is not None:
            # Validate role
            if role_id != 0:  # 0 means remove role
                role = await self.get_role_by_id(role_id)
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid role specified",
                    )
            user.role_id = role_id if role_id != 0 else None

        if custom_permissions is not None:
            user.custom_permissions = custom_permissions

        if is_active is not None:
            user.is_active = is_active

        if is_verified is not None:
            user.is_verified = is_verified

        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user, ["role"])

        return user

    async def change_user_password(
        self,
        user_id: int,
        current_password: Optional[str] = None,
        new_password: str = None,
        is_admin_reset: bool = False,
    ) -> User:
        """Change user password"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # For user-initiated password changes, verify current password
        if not is_admin_reset and current_password:
            if not bcrypt.checkpw(
                current_password.encode("utf-8"), user.hashed_password.encode("utf-8")
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect",
                )

        # Hash and set new password
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()

        # If user is changing their own password and was forced to change it, clear the flag
        if not is_admin_reset and user.force_password_change:
            user.force_password_change = False

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def admin_reset_user_password(
        self,
        user_id: int,
        new_password: str,
        force_change_on_login: bool = True,
        admin_user_id: Optional[int] = None,
    ) -> User:
        """Admin reset user password with forced change option"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Hash and set new password
        old_password_hash = user.hashed_password
        user.hashed_password = get_password_hash(new_password)
        user.force_password_change = force_change_on_login
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        # Log password reset audit event
        await self._log_audit_event(
            user_id=admin_user_id,
            action="password_reset",
            resource_type="user",
            resource_id=str(user_id),
            description=f"Admin password reset for user {user.email}",
            details={
                "target_user": user.email,
                "force_change_on_login": force_change_on_login,
                "reset_by_admin": True,
            },
            severity=AuditSeverity.HIGH,
        )

        return user

    async def delete_user(self, user_id: int, hard_delete: bool = False) -> bool:
        """Delete or deactivate user"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if hard_delete:
            # Hard delete - remove from database
            await self.db.delete(user)
        else:
            # Soft delete - deactivate account
            user.is_active = False
            user.email = f"deleted_{user_id}_{user.email}"
            user.username = f"deleted_{user_id}_{user.username}"
            user.updated_at = datetime.utcnow()

        await self.db.commit()
        return True

    async def lock_user_account(self, user_id: int, duration_hours: int = 24) -> User:
        """Lock user account for specified duration"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.lock_account(duration_hours)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def unlock_user_account(self, user_id: int) -> User:
        """Unlock user account"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.unlock_account()
        await self.db.commit()
        await self.db.refresh(user)

        return user

    # Role Management Methods
    async def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        level: str = RoleLevel.USER,
        permissions: Optional[Dict[str, Any]] = None,
        can_manage_users: bool = False,
        can_manage_budgets: bool = False,
        can_view_reports: bool = False,
        can_manage_tools: bool = False,
        inherits_from: Optional[List[str]] = None,
        is_active: bool = True,
        is_system_role: bool = False,
    ) -> Role:
        """Create a new role"""

        # Check if role name already exists
        existing_role = await self.get_role_by_name(name)
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name already exists",
            )

        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            level=level,
            permissions=permissions or {},
            can_manage_users=can_manage_users,
            can_manage_budgets=can_manage_budgets,
            can_view_reports=can_view_reports,
            can_manage_tools=can_manage_tools,
            inherits_from=inherits_from or [],
            is_active=is_active,
            is_system_role=is_system_role,
        )

        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)

        return role

    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID"""
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name"""
        result = await self.db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def get_roles(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        level: Optional[str] = None,
    ) -> List[Role]:
        """Get roles with filtering and pagination"""

        query = select(Role)

        if is_active is not None:
            query = query.where(Role.is_active == is_active)

        if level:
            query = query.where(Role.level == level)

        query = query.order_by(Role.level, Role.name).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_role(
        self,
        role_id: int,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[Dict[str, Any]] = None,
        can_manage_users: Optional[bool] = None,
        can_manage_budgets: Optional[bool] = None,
        can_view_reports: Optional[bool] = None,
        can_manage_tools: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Role:
        """Update role information"""

        role = await self.get_role_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )

        # Don't allow modification of system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify system roles",
            )

        # Update fields
        if display_name is not None:
            role.display_name = display_name

        if description is not None:
            role.description = description

        if permissions is not None:
            role.permissions = permissions

        if can_manage_users is not None:
            role.can_manage_users = can_manage_users

        if can_manage_budgets is not None:
            role.can_manage_budgets = can_manage_budgets

        if can_view_reports is not None:
            role.can_view_reports = can_view_reports

        if can_manage_tools is not None:
            role.can_manage_tools = can_manage_tools

        if is_active is not None:
            role.is_active = is_active

        role.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(role)

        return role

    async def delete_role(self, role_id: int) -> bool:
        """Delete role (if not system role and no users assigned)"""

        role = await self.get_role_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )

        # Don't allow deletion of system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete system roles",
            )

        # Check if any users are assigned to this role
        users_count = await self.db.execute(
            select(func.count(User.id)).where(User.role_id == role_id)
        )
        if users_count.scalar() > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete role with assigned users",
            )

        await self.db.delete(role)
        await self.db.commit()

        return True

    async def assign_role_to_user(self, user_id: int, role_id: int) -> User:
        """Assign a role to a user"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        role = await self.get_role_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )

        if not role.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign inactive role",
            )

        user.role_id = role_id
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def remove_role_from_user(self, user_id: int) -> User:
        """Remove role from user"""

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.role_id = None
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        return user

    # Statistics and Analytics
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user management statistics"""

        total_users = await self.db.execute(select(func.count(User.id)))
        active_users = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        verified_users = await self.db.execute(
            select(func.count(User.id)).where(User.is_verified == True)
        )
        locked_users = await self.db.execute(
            select(func.count(User.id)).where(User.account_locked == True)
        )

        # Users by role
        users_by_role = await self.db.execute(
            select(Role.name, func.count(User.id))
            .join(User, Role.id == User.role_id)
            .where(User.is_active == True)
            .group_by(Role.name)
        )

        # Recent registrations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_registrations = await self.db.execute(
            select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
        )

        return {
            "total_users": total_users.scalar(),
            "active_users": active_users.scalar(),
            "verified_users": verified_users.scalar(),
            "locked_users": locked_users.scalar(),
            "users_by_role": dict(users_by_role.all()),
            "recent_registrations": recent_registrations.scalar(),
        }

    async def get_role_statistics(self) -> Dict[str, Any]:
        """Get role management statistics"""

        total_roles = await self.db.execute(select(func.count(Role.id)))
        active_roles = await self.db.execute(
            select(func.count(Role.id)).where(Role.is_active == True)
        )
        system_roles = await self.db.execute(
            select(func.count(Role.id)).where(Role.is_system_role == True)
        )

        # Roles by level
        roles_by_level = await self.db.execute(
            select(Role.level, func.count(Role.id)).group_by(Role.level)
        )

        return {
            "total_roles": total_roles.scalar(),
            "active_roles": active_roles.scalar(),
            "system_roles": system_roles.scalar(),
            "roles_by_level": dict(roles_by_level.all()),
        }

    # Audit Logging Methods
    async def _log_audit_event(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        severity: str = AuditSeverity.LOW,
        category: str = "user_management",
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log audit event for user management operations"""

        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            details=details or {},
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
            category=category,
            success=success,
            tags=["user_management", action],
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_user_login(
        self,
        user_id: int,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Log user login attempt"""

        audit_log = AuditLog.create_login_event(
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_user_logout(
        self,
        user_id: int,
        session_id: Optional[str] = None,
    ):
        """Log user logout"""

        audit_log = AuditLog.create_logout_event(
            user_id=user_id,
            session_id=session_id,
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_user_action(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
    ):
        """Log general user action"""

        await self._log_audit_event(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            details=details,
            severity=AuditSeverity.LOW,
            category="user_action",
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_user_audit_logs(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        action_filter: Optional[str] = None,
    ) -> List[AuditLog]:
        """Get audit logs for a specific user"""

        query = select(AuditLog).where(
            or_(
                AuditLog.user_id == user_id,
                and_(
                    AuditLog.resource_type == "user",
                    AuditLog.resource_id == str(user_id),
                ),
            )
        )

        if action_filter:
            query = query.where(AuditLog.action == action_filter)

        query = query.order_by(desc(AuditLog.created_at))
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()


# Import for selectinload and func
from sqlalchemy.orm import selectinload
from sqlalchemy import func
