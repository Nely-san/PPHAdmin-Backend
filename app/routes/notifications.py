from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.database import get_db
from app.routes.auth import get_current_user
from app.models.auth import UserProfile
from app.models.notification import NotificationResponse, NotificationPreferencesUpdate
from app.services.notification import get_or_create_default_preferences
from prisma import Prisma
from typing import Optional, List

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def get_my_notifications(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Cursor-based paginated notifications list."""
    query_args = {
        "where": {"userId": current_user.id},
        "take": limit,
        "order": {"createdAt": "desc"}
    }
    if cursor:
        query_args["cursor"] = {"id": cursor}
        query_args["skip"] = 1
        
    return await db.notification.find_many(**query_args)

@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Get the unread notification count for the current user."""
    count = await db.notification.count(
        where={
            "userId": current_user.id,
            "isRead": False
        }
    )
    return {"unreadCount": count}

@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: str,
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Mark a notification as read."""
    notification = await db.notification.find_unique(where={"id": notification_id})
    if not notification or notification.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return await db.notification.update(
        where={"id": notification_id},
        data={"isRead": True}
    )

@router.put("/read-all", response_model=dict)
async def mark_all_notifications_as_read(
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Mark all notifications for current user as read."""
    result = await db.notification.update_many(
        where={
            "userId": current_user.id,
            "isRead": False
        },
        data={"isRead": True}
    )
    return {"status": "success", "count": result}

@router.get("/preferences")
async def get_user_preferences(
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Fetch current user's notification preferences."""
    prefs = await get_or_create_default_preferences(current_user.id, db)
    return prefs

@router.put("/preferences")
async def update_user_preferences(
    payload: NotificationPreferencesUpdate,
    db: Prisma = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user)
):
    """Update current user's notification preferences."""
    prefs = await get_or_create_default_preferences(current_user.id, db)
    update_data = payload.model_dump(exclude_unset=True)
    
    return await db.notificationpreference.update(
        where={"id": prefs.id},
        data=update_data
    )
