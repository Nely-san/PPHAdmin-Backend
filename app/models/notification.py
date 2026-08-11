from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from prisma.enums import NotificationPriority

class NotificationBase(BaseModel):
    title: str
    message: str
    category: str = "INFO"
    priority: NotificationPriority = NotificationPriority.MEDIUM
    actionUrl: Optional[str] = None

class NotificationCreate(NotificationBase):
    userId: str

class NotificationResponse(NotificationBase):
    id: str
    userId: str
    isRead: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class NotificationPreferencesUpdate(BaseModel):
    enableInApp: Optional[bool] = None
    notifyAttendance: Optional[bool] = None
    notifyPayroll: Optional[bool] = None
    notifyLeave: Optional[bool] = None
