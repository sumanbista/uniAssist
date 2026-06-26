"""Seed deterministic Caldwell smoke data into Supabase Postgres."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import async_sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.domains.calendar.models import AcademicCalendarEntry  # noqa: E402
from app.domains.contacts.models import Contact  # noqa: E402
from app.domains.deadlines.models import Deadline  # noqa: E402
from app.domains.forms.models import Form  # noqa: E402
from app.domains.relationships.models import EntityRelationship  # noqa: E402
from app.shared.database.session import get_engine  # noqa: E402

SEED_NAMESPACE = UUID("99999999-9999-4999-8999-999999999999")
UNIVERSITY_ID = settings.CALDWELL_UNIVERSITY_ID
SOURCE_URL = "https://www.caldwell.edu/registrar/"


def seed_uuid(name: str) -> UUID:
    """Return a stable UUID for one smoke fixture."""

    return uuid5(SEED_NAMESPACE, f"caldwell-smoke:{name}")


async def main() -> int:
    """Upsert Caldwell smoke records."""

    session_factory = async_sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        verified_at = datetime.now(UTC)
        forms = [
            Form(
                id=seed_uuid("form-withdrawal"),
                university_id=UNIVERSITY_ID,
                title="Course Withdrawal Form",
                description="Request to withdraw from a course after add/drop.",
                category="registrar",
                source_url=SOURCE_URL,
                storage_path=None,
                verification_status="verified",
                verification_score=1.0,
                last_verified_at=verified_at,
                status="verified",
                metadata_={"seed_key": "caldwell_smoke_form_withdrawal"},
            ),
            Form(
                id=seed_uuid("form-add-drop"),
                university_id=UNIVERSITY_ID,
                title="Add Drop Form",
                description="Request a schedule change during the add/drop window.",
                category="registrar",
                source_url=SOURCE_URL,
                storage_path=None,
                verification_status="verified",
                verification_score=1.0,
                last_verified_at=verified_at,
                status="verified",
                metadata_={"seed_key": "caldwell_smoke_form_add_drop"},
            ),
        ]
        deadlines = [
            Deadline(
                id=seed_uuid("deadline-withdrawal"),
                university_id=UNIVERSITY_ID,
                title="Course Withdrawal Deadline",
                description="Last day to submit the course withdrawal form.",
                term="Fall",
                academic_year="2026-2027",
                deadline_type="withdrawal",
                due_date=date(2026, 11, 6),
                source_url=SOURCE_URL,
                related_form_id=forms[0].id,
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_deadline_withdrawal"},
            ),
            Deadline(
                id=seed_uuid("deadline-add-drop"),
                university_id=UNIVERSITY_ID,
                title="Add Drop Deadline",
                description="Last day to submit schedule add/drop changes.",
                term="Fall",
                academic_year="2026-2027",
                deadline_type="add_drop",
                due_date=date(2026, 9, 4),
                source_url=SOURCE_URL,
                related_form_id=forms[1].id,
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_deadline_add_drop"},
            ),
        ]
        calendar_entries = [
            AcademicCalendarEntry(
                id=seed_uuid("calendar-classes-begin"),
                university_id=UNIVERSITY_ID,
                title="Fall Classes Begin",
                description="First day of Fall 2026 classes.",
                term="Fall",
                academic_year="2026-2027",
                entry_type="semester_start",
                start_date=date(2026, 8, 31),
                end_date=date(2026, 8, 31),
                source_url=settings.CALDWELL_CALENDAR_SOURCE_URL,
                source_hash="caldwell-smoke-calendar-classes-begin",
                status="verified",
                verification_status="verified",
                last_verified_at=verified_at,
                extracted_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_calendar_classes_begin"},
            ),
            AcademicCalendarEntry(
                id=seed_uuid("calendar-fall-break"),
                university_id=UNIVERSITY_ID,
                title="Fall Break",
                description="No classes during Fall Break.",
                term="Fall",
                academic_year="2026-2027",
                entry_type="break",
                start_date=date(2026, 10, 12),
                end_date=date(2026, 10, 13),
                source_url=settings.CALDWELL_CALENDAR_SOURCE_URL,
                source_hash="caldwell-smoke-calendar-fall-break",
                status="verified",
                verification_status="verified",
                last_verified_at=verified_at,
                extracted_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_calendar_fall_break"},
            ),
            AcademicCalendarEntry(
                id=seed_uuid("calendar-finals"),
                university_id=UNIVERSITY_ID,
                title="Final Exams Week",
                description="Final examinations for Fall 2026.",
                term="Fall",
                academic_year="2026-2027",
                entry_type="finals_week",
                start_date=date(2026, 12, 14),
                end_date=date(2026, 12, 18),
                source_url=settings.CALDWELL_CALENDAR_SOURCE_URL,
                source_hash="caldwell-smoke-calendar-finals",
                status="verified",
                verification_status="verified",
                last_verified_at=verified_at,
                extracted_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_calendar_finals"},
            ),
        ]
        contacts = [
            Contact(
                id=seed_uuid("contact-registrar"),
                university_id=UNIVERSITY_ID,
                name="Registrar Office",
                title="Registrar",
                department="Registrar",
                email="registrar@caldwell.edu",
                phone="973-618-3000",
                office_location="Alumni Theatre Building",
                office_hours="Monday-Friday 9:00 AM-4:30 PM",
                contact_type="office",
                source_url=SOURCE_URL,
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_contact_registrar"},
            ),
            Contact(
                id=seed_uuid("contact-financial-aid"),
                university_id=UNIVERSITY_ID,
                name="Financial Aid Office",
                title="Financial Aid",
                department="Financial Aid",
                email="financialaid@caldwell.edu",
                phone="973-618-3221",
                office_location="Aquinas Hall",
                office_hours="Monday-Friday 9:00 AM-4:30 PM",
                contact_type="office",
                source_url="https://www.caldwell.edu/admissions/financial-aid/",
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_contact_financial_aid"},
            ),
            Contact(
                id=seed_uuid("contact-student-success"),
                university_id=UNIVERSITY_ID,
                name="Student Success",
                title="Student Success Center",
                department="Student Success",
                email="studentsuccess@caldwell.edu",
                phone="973-618-3000",
                office_location="Academic Success Center",
                office_hours="Monday-Friday 9:00 AM-4:30 PM",
                contact_type="office",
                source_url="https://www.caldwell.edu/",
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_contact_student_success"},
            ),
            Contact(
                id=seed_uuid("contact-admissions"),
                university_id=UNIVERSITY_ID,
                name="Admissions Office",
                title="Admissions",
                department="Admissions",
                email="admissions@caldwell.edu",
                phone="973-618-3500",
                office_location="Newman Center",
                office_hours="Monday-Friday 9:00 AM-4:30 PM",
                contact_type="office",
                source_url="https://www.caldwell.edu/admissions/",
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_contact_admissions"},
            ),
            Contact(
                id=seed_uuid("contact-it-helpdesk"),
                university_id=UNIVERSITY_ID,
                name="IT Help Desk",
                title="Technology Support",
                department="Information Technology",
                email="helpdesk@caldwell.edu",
                phone="973-618-3904",
                office_location="Jennings Library",
                office_hours="Monday-Friday 9:00 AM-5:00 PM",
                contact_type="office",
                source_url="https://www.caldwell.edu/",
                verification_status="verified",
                status="verified",
                last_verified_at=verified_at,
                metadata_={"seed_key": "caldwell_smoke_contact_it_helpdesk"},
            ),
        ]
        relationships = [
            EntityRelationship(
                id=seed_uuid("relationship-withdrawal"),
                source_entity_type="form",
                source_entity_id=forms[0].id,
                target_entity_type="deadline",
                target_entity_id=deadlines[0].id,
                relationship_type="deadline_for",
                confidence_score=1.0,
                provenance_type="admin_verified",
                metadata_={"seed_key": "caldwell_smoke_relationship_withdrawal"},
            ),
            EntityRelationship(
                id=seed_uuid("relationship-add-drop"),
                source_entity_type="form",
                source_entity_id=forms[1].id,
                target_entity_type="deadline",
                target_entity_id=deadlines[1].id,
                relationship_type="deadline_for",
                confidence_score=1.0,
                provenance_type="admin_verified",
                metadata_={"seed_key": "caldwell_smoke_relationship_add_drop"},
            ),
        ]

        for record in [*forms, *deadlines, *calendar_entries, *contacts, *relationships]:
            await session.merge(record)
        await session.commit()

    print("Seeded Caldwell smoke data: 2 forms, 2 deadlines, 3 calendar entries, 5 contacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
