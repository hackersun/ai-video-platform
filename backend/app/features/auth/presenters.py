"""Authentication response presenters."""

from app.features.auth.schemas import UserResponse
from app.models.user import User


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar=user.avatar,
        created_at=user.created_at,
        is_active=user.is_active,
    )
