from typing import List, Optional, Union, Dict
from pydantic import BaseModel, HttpUrl, validator

class CaptchaConfig(BaseModel):
    method: str = "HYBRID"
    ocr_retries: int = 5
    gemini_retries: int = 0

class NotificationConfig(BaseModel):
    webhook_url: Optional[str] = None

class TicketAmount(BaseModel):
    adult: int = 0
    child: int = 0
    disabled: int = 0
    elder: int = 0
    college: int = 0

class ScheduleConfig(BaseModel):
    type: str # specific, recurring
    value: str # YYYY-MM-DD or Weekday

class TicketConfig(BaseModel):
    name: str
    start_station: str
    dest_station: str
    schedule: ScheduleConfig
    time_preference: str
    train_no: Optional[str] = None
    ticket_amount: TicketAmount
    car_class: str = "standard"
    trip_type: str = "one-way"
    seat_preference: str = "none"

class AppConfig(BaseModel):
    captcha: CaptchaConfig = CaptchaConfig()
    notification: NotificationConfig = NotificationConfig()
    tickets: List[TicketConfig] = []

    @validator('tickets', pre=True)
    def check_tickets(cls, v):
        if v is None:
            return []
        return v
