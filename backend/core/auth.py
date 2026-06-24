"""Authentication and Role-Based Access Control (RBAC) for API.

Phase 337: Basic token-based auth with role checks.
Future: Integrate with OAuth2, JWT, or external auth service.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    ANALYST = "analyst"
    TRADER = "trader"
    VIEWER = "viewer"


class User:
    """Authenticated user with roles and permissions."""

    def __init__(
        self,
        user_id: str,
        username: str,
        roles: List[UserRole],
    ) -> None:
        """Initialize user.

        Args:
            user_id: Unique user identifier
            username: Human-readable username
            roles: List of assigned roles
        """
        self.user_id = user_id
        self.username = username
        self.roles = set(roles)

    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role.

        Args:
            role: Role to check

        Returns:
            True if user has role, False otherwise
        """
        return role in self.roles

    def has_any_role(self, roles: Set[UserRole]) -> bool:
        """Check if user has any of the specified roles.

        Args:
            roles: Set of roles to check

        Returns:
            True if user has any role, False otherwise
        """
        return bool(self.roles & roles)


class AuthManager:
    """Manage authentication and authorization.

    In Phase 337: Basic token lookup.
    Future: Integrate with JWT/OAuth2.
    """

    def __init__(self) -> None:
        """Initialize auth manager with demo users."""
        # Demo users (replace with real auth in production)
        self.users: Dict[str, User] = {
            "admin-token-123": User(
                user_id="admin-1",
                username="admin_user",
                roles=[UserRole.ADMIN, UserRole.ANALYST, UserRole.TRADER],
            ),
            "analyst-token-456": User(
                user_id="analyst-1",
                username="analyst_user",
                roles=[UserRole.ANALYST],
            ),
            "trader-token-789": User(
                user_id="trader-1",
                username="trader_user",
                roles=[UserRole.TRADER, UserRole.ANALYST],
            ),
            "viewer-token-000": User(
                user_id="viewer-1",
                username="viewer_user",
                roles=[UserRole.VIEWER],
            ),
        }

    def authenticate(self, token: Optional[str]) -> User:
        """Authenticate user by token.

        Args:
            token: Bearer token from Authorization header

        Returns:
            Authenticated User

        Raises:
            HTTPException: If token invalid or missing
        """
        if not token:
            logger.warning("Authentication failed: no token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        user = self.users.get(token)
        if not user:
            logger.warning(f"Authentication failed: invalid token {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"Authenticated user: {user.username} ({user.user_id})")
        return user

    def require_role(self, user: User, required_role: UserRole) -> None:
        """Check if user has required role.

        Args:
            user: User to check
            required_role: Role that is required

        Raises:
            HTTPException: If user doesn't have role
        """
        if not user.has_role(required_role):
            logger.warning(
                f"Authorization failed: user {user.user_id} lacks {required_role.value} role"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User requires {required_role.value} role",
            )

    def require_any_role(self, user: User, required_roles: Set[UserRole]) -> None:
        """Check if user has any of the required roles.

        Args:
            user: User to check
            required_roles: Set of roles (at least one required)

        Raises:
            HTTPException: If user doesn't have any role
        """
        if not user.has_any_role(required_roles):
            role_names = ", ".join(r.value for r in required_roles)
            logger.warning(
                f"Authorization failed: user {user.user_id} lacks any of [{role_names}]"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User requires one of: {role_names}",
            )


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get global auth manager.

    Returns:
        AuthManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def verify_token(token: Optional[str]) -> User:
    """Dependency for FastAPI route protection.

    Usage:
        @app.get("/protected")
        def protected_route(user: User = Depends(verify_token)):
            return {"message": f"Hello {user.username}"}

    Args:
        token: Bearer token from Authorization header

    Returns:
        Authenticated User

    Raises:
        HTTPException: If token invalid
    """
    auth = get_auth_manager()
    return auth.authenticate(token)
