from prisma import Prisma
from app.models.notification import NotificationCreate

async def get_or_create_default_preferences(user_id: str, db: Prisma):
    prefs = await db.notificationpreference.find_unique(where={"userId": user_id})
    if not prefs:
        prefs = await db.notificationpreference.create(
            data={"userId": user_id}
        )
    return prefs

async def dispatch_notification(data: NotificationCreate, db: Prisma):
    """
    Central dispatcher.
    Checks recipient preferences before saving.
    """
    prefs = await get_or_create_default_preferences(data.userId, db)
    
    # Check general preference
    if not prefs.enableInApp:
        return None
        
    # Check category rule preferences
    if data.category == "ATTENDANCE" and not prefs.notifyAttendance:
        return None
    if data.category == "PAYROLL" and not prefs.notifyPayroll:
        return None
    if data.category == "LEAVE" and not prefs.notifyLeave:
        return None
        
    notification = await db.notification.create(
        data={
            "userId": data.userId,
            "title": data.title,
            "message": data.message,
            "category": data.category,
            "priority": data.priority,
            "actionUrl": data.actionUrl
        }
    )
    
    return notification
