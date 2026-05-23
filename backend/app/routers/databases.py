from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy import extract, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.excel_utils import export_excel, import_excel
from app.logging_config import get_logger
from app.models import DatabaseRecord, User
from app.schemas import (
    DatabaseRecordCreate,
    DatabaseRecordOut,
    DatabaseRecordUpdate,
    ClearAllResult,
    ImportResult,
    KPIs,
    KpiListResponse,
    TypeBreakdown,
)

KPI_CATEGORIES = frozenset({
    "expiring_this_month",
    "expiring_next_month",
    "prod_mirror",
    "can_be_released",
    "blocked",
    "total",
})

KPI_TITLES = {
    "expiring_this_month": "Expiring this month",
    "expiring_next_month": "Expiring next month",
    "prod_mirror": "Prod mirror",
    "can_be_released": "Can be released",
    "blocked": "Blocked status",
    "total": "All databases",
}

logger = get_logger("app.databases.router")
router = APIRouter(prefix="/api/databases", tags=["databases"])

SORTABLE_COLUMNS = {
    "serial_number": DatabaseRecord.serial_number,
    "database_type": DatabaseRecord.database_type,
    "database_name": DatabaseRecord.database_name,
    "cics_transactions": DatabaseRecord.cics_transactions,
    "prod_mirror": DatabaseRecord.prod_mirror,
    "release": DatabaseRecord.release,
    "lifecycle": DatabaseRecord.lifecycle,
    "status": DatabaseRecord.status,
    "assignee": DatabaseRecord.assignee,
    "team": DatabaseRecord.team,
    "project": DatabaseRecord.project,
    "start_date": DatabaseRecord.start_date,
    "end_date": DatabaseRecord.end_date,
    "can_be_released": DatabaseRecord.can_be_released,
    "jira_key": DatabaseRecord.jira_key,
    "comments": DatabaseRecord.comments,
}


def _apply_sort(query, sort_by: str | None, sort_order: str):
    order = (sort_order or "asc").lower()
    if sort_by and sort_by in SORTABLE_COLUMNS:
        column = SORTABLE_COLUMNS[sort_by]
        if order == "desc":
            return query.order_by(column.desc().nulls_last(), DatabaseRecord.id.desc())
        return query.order_by(column.asc().nulls_last(), DatabaseRecord.id.asc())
    return query.order_by(DatabaseRecord.serial_number.asc().nulls_last(), DatabaseRecord.id.asc())


def _is_prod_mirror(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("yes", "y", "true", "1")


def _next_calendar_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _apply_kpi_category_filter(query, category: str, today: date, next_year: int, next_month: int):
    if category == "expiring_this_month":
        return query.filter(
            DatabaseRecord.end_date.isnot(None),
            extract("year", DatabaseRecord.end_date) == today.year,
            extract("month", DatabaseRecord.end_date) == today.month,
        )
    if category == "expiring_next_month":
        return query.filter(
            DatabaseRecord.end_date.isnot(None),
            extract("year", DatabaseRecord.end_date) == next_year,
            extract("month", DatabaseRecord.end_date) == next_month,
        )
    if category == "prod_mirror":
        return query.filter(
            func.lower(func.trim(DatabaseRecord.prod_mirror)).in_(("yes", "y", "true", "1"))
        )
    if category == "can_be_released":
        return query.filter(func.upper(func.trim(DatabaseRecord.can_be_released)).in_(("Y", "YES")))
    if category == "blocked":
        return query.filter(func.lower(func.trim(DatabaseRecord.status)) == "blocked")
    return query


@router.get("/kpis", response_model=KPIs)
def get_kpis(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    logger.debug("Fetching KPIs user_id=%s", user.id)
    try:
        today = date.today()
        next_year, next_month = _next_calendar_month(today.year, today.month)
        total = db.query(func.count(DatabaseRecord.id)).scalar() or 0
        expiring = (
            db.query(func.count(DatabaseRecord.id))
            .filter(
                DatabaseRecord.end_date.isnot(None),
                extract("year", DatabaseRecord.end_date) == today.year,
                extract("month", DatabaseRecord.end_date) == today.month,
            )
            .scalar()
            or 0
        )
        expiring_next = (
            db.query(func.count(DatabaseRecord.id))
            .filter(
                DatabaseRecord.end_date.isnot(None),
                extract("year", DatabaseRecord.end_date) == next_year,
                extract("month", DatabaseRecord.end_date) == next_month,
            )
            .scalar()
            or 0
        )
        all_records = db.query(
            DatabaseRecord.database_type,
            DatabaseRecord.prod_mirror,
            DatabaseRecord.can_be_released,
            DatabaseRecord.status,
            DatabaseRecord.end_date,
        ).all()
        prod_mirror_count = sum(1 for r in all_records if _is_prod_mirror(r.prod_mirror))
        can_be_released_count = sum(
            1 for r in all_records if r.can_be_released and r.can_be_released.strip().upper() in ("Y", "YES")
        )
        blocked_count = sum(1 for r in all_records if r.status and r.status.strip().lower() == "blocked")

        type_stats: dict[str, dict[str, int]] = {}
        for r in all_records:
            t = r.database_type or "Unassigned"
            if t not in type_stats:
                type_stats[t] = {
                    "count": 0,
                    "prod_mirror_count": 0,
                    "expiring_this_month": 0,
                    "expiring_next_month": 0,
                    "blocked_count": 0,
                    "can_be_released_count": 0,
                }
            s = type_stats[t]
            s["count"] += 1
            if _is_prod_mirror(r.prod_mirror):
                s["prod_mirror_count"] += 1
            if r.end_date and r.end_date.year == today.year and r.end_date.month == today.month:
                s["expiring_this_month"] += 1
            if r.end_date and r.end_date.year == next_year and r.end_date.month == next_month:
                s["expiring_next_month"] += 1
            if r.status and r.status.strip().lower() == "blocked":
                s["blocked_count"] += 1
            if r.can_be_released and r.can_be_released.strip().upper() in ("Y", "YES"):
                s["can_be_released_count"] += 1

        by_type = [
            TypeBreakdown(database_type=t, **stats)
            for t, stats in sorted(type_stats.items(), key=lambda x: (-x[1]["count"], x[0]))
        ]

        kpis = KPIs(
            total_databases=total,
            expiring_this_month=expiring,
            expiring_next_month=expiring_next,
            prod_mirror_count=prod_mirror_count,
            can_be_released_count=can_be_released_count,
            blocked_count=blocked_count,
            by_type=by_type,
        )
        logger.info(
            "KPIs computed total=%s expiring_this_month=%s expiring_next_month=%s prod_mirror=%s",
            total,
            expiring,
            expiring_next,
            prod_mirror_count,
        )
        return kpis
    except SQLAlchemyError:
        logger.exception("Database error while fetching KPIs")
        raise HTTPException(status_code=500, detail="Failed to fetch KPIs") from None


@router.get("/kpi-list", response_model=KpiListResponse)
def get_kpi_list(
    category: str = Query(..., description="KPI category to list databases for"),
    database_type: str | None = Query(None, description="Optional filter by database type"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if category not in KPI_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Allowed: {', '.join(sorted(KPI_CATEGORIES))}",
        )
    today = date.today()
    next_year, next_month = _next_calendar_month(today.year, today.month)
    try:
        q = db.query(DatabaseRecord)
        if database_type:
            q = q.filter(DatabaseRecord.database_type == database_type)
        q = _apply_kpi_category_filter(q, category, today, next_year, next_month)
        if category in ("expiring_this_month", "expiring_next_month"):
            q = q.order_by(DatabaseRecord.end_date.asc().nulls_last(), DatabaseRecord.database_name)
        else:
            q = q.order_by(DatabaseRecord.database_type, DatabaseRecord.database_name)
        records = q.limit(2000).all()
        title = KPI_TITLES[category]
        if database_type:
            title = f"{title} — {database_type}"
        logger.info(
            "KPI list user_id=%s category=%s type_filter=%s count=%s",
            user.id,
            category,
            database_type,
            len(records),
        )
        return KpiListResponse(category=category, title=title, count=len(records), records=records)
    except SQLAlchemyError:
        logger.exception("Database error fetching KPI list category=%s", category)
        raise HTTPException(status_code=500, detail="Failed to fetch KPI list") from None


@router.get("", response_model=list[DatabaseRecordOut])
def list_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    search: str | None = None,
    database_type: str | None = Query(None, description="Filter by database type (sheet name)"),
    expiry_filter: str | None = Query(
        None,
        description="Filter by end date: expiring_this_month, expiring_next_month",
    ),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if sort_by and sort_by not in SORTABLE_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by. Allowed: {', '.join(sorted(SORTABLE_COLUMNS))}",
        )
    if expiry_filter and expiry_filter not in ("expiring_this_month", "expiring_next_month"):
        raise HTTPException(
            status_code=400,
            detail="Invalid expiry_filter. Allowed: expiring_this_month, expiring_next_month",
        )
    today = date.today()
    next_year, next_month = _next_calendar_month(today.year, today.month)
    logger.debug(
        "List records user_id=%s skip=%s limit=%s search=%s expiry=%s sort_by=%s sort_order=%s",
        user.id,
        skip,
        limit,
        search,
        expiry_filter,
        sort_by,
        sort_order,
    )
    try:
        q = db.query(DatabaseRecord)
        if database_type:
            q = q.filter(DatabaseRecord.database_type == database_type)
        if expiry_filter:
            q = _apply_kpi_category_filter(q, expiry_filter, today, next_year, next_month)
        if search:
            term = f"%{search}%"
            q = q.filter(
                (DatabaseRecord.database_name.ilike(term))
                | (DatabaseRecord.assignee.ilike(term))
                | (DatabaseRecord.team.ilike(term))
                | (DatabaseRecord.project.ilike(term))
                | (DatabaseRecord.database_type.ilike(term))
            )
        q = _apply_sort(q, sort_by, sort_order)
        records = q.offset(skip).limit(limit).all()
        logger.info(
            "Listed %s database records (search=%s sort=%s %s)",
            len(records),
            search or "none",
            sort_by or "serial_number",
            sort_order,
        )
        return records
    except SQLAlchemyError:
        logger.exception("Database error while listing records")
        raise HTTPException(status_code=500, detail="Failed to list records") from None


@router.post("", response_model=DatabaseRecordOut, status_code=201)
def create_record(
    payload: DatabaseRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logger.info("Create record user_id=%s database_name=%s", user.id, payload.database_name)
    try:
        record = DatabaseRecord(**payload.model_dump())
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info("Created record id=%s database_name=%s", record.id, record.database_name)
        return record
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while creating record database_name=%s", payload.database_name)
        raise HTTPException(status_code=500, detail="Failed to create record") from None


@router.post("/import", response_model=ImportResult)
async def import_file(
    file: UploadFile = File(...),
    replace: bool = Query(False, description="Replace all existing records"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logger.info(
        "Excel import user_id=%s filename=%s replace=%s content_type=%s",
        user.id,
        file.filename,
        replace,
        file.content_type,
    )
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        logger.warning("Import rejected: invalid file type filename=%s", file.filename)
        raise HTTPException(status_code=400, detail="Upload a valid .xlsx file")
    try:
        content = await file.read()
        logger.debug("Read upload file size=%s bytes", len(content))
        imported, skipped, sheets = import_excel(db, content, replace=replace)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Excel import failed filename=%s", file.filename)
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {exc}") from exc
    sheet_msg = f" from {len(sheets)} sheet(s): {', '.join(sheets)}" if sheets else ""
    result = ImportResult(
        imported=imported,
        skipped=skipped,
        sheets=sheets,
        message=f"Imported {imported} records, skipped {skipped} empty rows{sheet_msg}.",
    )
    logger.info("Excel import complete imported=%s skipped=%s replace=%s", imported, skipped, replace)
    return result


@router.get("/export/excel")
def export_file(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    logger.info("Excel export user_id=%s", user.id)
    try:
        content = export_excel(db)
        filename = f"DB_Excel_Utility_list_{date.today().isoformat()}.xlsx"
        logger.info("Excel export complete size=%s bytes filename=%s", len(content), filename)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception:
        logger.exception("Excel export failed user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="Failed to export Excel") from None


@router.delete("/clear/all", response_model=ClearAllResult)
def clear_all_records(
    confirm: bool = Query(False, description="Must be true to delete all records"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not confirm:
        logger.warning("Clear all rejected: confirm=false user_id=%s", user.id)
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set confirm=true to clear all database records.",
        )
    try:
        count = db.query(func.count(DatabaseRecord.id)).scalar() or 0
        if count == 0:
            logger.info("Clear all: no records to delete user_id=%s", user.id)
            return ClearAllResult(deleted=0, message="No records to delete.")
        logger.warning("Clear all requested user_id=%s record_count=%s", user.id, count)
        db.query(DatabaseRecord).delete()
        db.commit()
        logger.warning("Cleared all database records user_id=%s deleted=%s", user.id, count)
        return ClearAllResult(
            deleted=count,
            message=f"Permanently deleted {count} database record(s).",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while clearing all records user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="Failed to clear all records") from None


@router.get("/{record_id}", response_model=DatabaseRecordOut)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logger.debug("Get record user_id=%s record_id=%s", user.id, record_id)
    record = db.query(DatabaseRecord).filter(DatabaseRecord.id == record_id).first()
    if not record:
        logger.warning("Record not found id=%s", record_id)
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.patch("/{record_id}", response_model=DatabaseRecordOut)
def update_record(
    record_id: int,
    payload: DatabaseRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = list(payload.model_dump(exclude_unset=True).keys())
    logger.info("Update record user_id=%s record_id=%s fields=%s", user.id, record_id, fields)
    record = db.query(DatabaseRecord).filter(DatabaseRecord.id == record_id).first()
    if not record:
        logger.warning("Update failed: record not found id=%s", record_id)
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
        logger.info("Updated record id=%s database_name=%s", record.id, record.database_name)
        return record
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while updating record id=%s", record_id)
        raise HTTPException(status_code=500, detail="Failed to update record") from None


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logger.info("Delete record user_id=%s record_id=%s", user.id, record_id)
    record = db.query(DatabaseRecord).filter(DatabaseRecord.id == record_id).first()
    if not record:
        logger.warning("Delete failed: record not found id=%s", record_id)
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        db_name = record.database_name
        db.delete(record)
        db.commit()
        logger.info("Deleted record id=%s database_name=%s", record_id, db_name)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while deleting record id=%s", record_id)
        raise HTTPException(status_code=500, detail="Failed to delete record") from None
