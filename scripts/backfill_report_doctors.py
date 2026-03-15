import argparse
from datetime import datetime, timezone

from app import create_app
from app.extensions import get_db


def backfill_report_doctors(dry_run=False):
    app = create_app()

    with app.app_context():
        db = get_db()
        query = {
            "$or": [
                {"doctor_user_id": {"$exists": False}},
                {"doctor_user_id": None},
            ]
        }

        scanned = 0
        updated = 0
        skipped_missing_patient = 0
        skipped_missing_assignment = 0

        for report in db.patient_reports.find(query):
            scanned += 1
            patient_id = report.get("patient_user_id")
            if not patient_id:
                skipped_missing_patient += 1
                continue

            profile = db.patient_profiles.find_one(
                {"patient_user_id": patient_id},
                {"assigned_doctor_id": 1},
            ) or {}
            assigned_doctor_id = profile.get("assigned_doctor_id")
            if not assigned_doctor_id:
                skipped_missing_assignment += 1
                continue

            if not dry_run:
                db.patient_reports.update_one(
                    {"_id": report["_id"]},
                    {
                        "$set": {
                            "doctor_user_id": assigned_doctor_id,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
            updated += 1

    print(f"Scanned reports: {scanned}")
    print(f"Reports updated: {updated}")
    print(f"Skipped without patient_user_id: {skipped_missing_patient}")
    print(f"Skipped without assigned doctor: {skipped_missing_assignment}")
    print(f"Mode: {'dry-run' if dry_run else 'write'}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill doctor_user_id for existing patient reports."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many reports would be updated without writing changes.",
    )
    args = parser.parse_args()
    backfill_report_doctors(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
