from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatabaseRecord(Base):
    __tablename__ = "database_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    serial_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cics_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prod_mirror: Mapped[str | None] = mapped_column(String(32), nullable=True)
    release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    can_be_released: Mapped[str | None] = mapped_column(String(8), nullable=True)
    jira_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
