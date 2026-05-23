from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DatabaseRecordBase(BaseModel):
    serial_number: int | None = None
    database_type: str | None = None
    database_name: str
    cics_transactions: int | None = None
    prod_mirror: str | None = None
    release: str | None = None
    lifecycle: str | None = None
    status: str | None = None
    assignee: str | None = None
    team: str | None = None
    project: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    can_be_released: str | None = None
    comments: str | None = None


class DatabaseRecordCreate(DatabaseRecordBase):
    pass


class DatabaseRecordUpdate(BaseModel):
    serial_number: int | None = None
    database_type: str | None = None
    database_name: str | None = None
    cics_transactions: int | None = None
    prod_mirror: str | None = None
    release: str | None = None
    lifecycle: str | None = None
    status: str | None = None
    assignee: str | None = None
    team: str | None = None
    project: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    can_be_released: str | None = None
    comments: str | None = None


class DatabaseRecordOut(DatabaseRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None


class TypeBreakdown(BaseModel):
    database_type: str
    count: int
    prod_mirror_count: int
    expiring_this_month: int
    expiring_next_month: int
    blocked_count: int
    can_be_released_count: int


class KPIs(BaseModel):
    total_databases: int
    expiring_this_month: int
    expiring_next_month: int
    prod_mirror_count: int
    can_be_released_count: int
    blocked_count: int
    by_type: list[TypeBreakdown]


class ImportResult(BaseModel):
    imported: int
    skipped: int
    sheets: list[str] = []
    message: str


class ClearAllResult(BaseModel):
    deleted: int
    message: str


class KpiListResponse(BaseModel):
    category: str
    title: str
    count: int
    records: list[DatabaseRecordOut]


class EmailStatusOut(BaseModel):
    enabled: bool
    configured: bool
    provider: str
    smtp_host: str | None = None
    mail_from: str | None = None
    graph_send_as: str | None = None
    hint: str | None = None


class SendEmailRequest(BaseModel):
    to: list[EmailStr] = Field(min_length=1)
    cc: list[EmailStr] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    html: bool = False


class NotifyRecordEmailRequest(BaseModel):
    to: EmailStr | None = None
    message: str | None = Field(default=None, max_length=4000)


class ExpiryDigestEmailRequest(BaseModel):
    category: str
    to: list[EmailStr] = Field(min_length=1)
    cc: list[EmailStr] = Field(default_factory=list)
    database_type: str | None = None
    message: str | None = Field(default=None, max_length=4000)


class EmailSendResult(BaseModel):
    message: str
