import csv
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Dict, List

DATABASE_PATH = os.getenv("DATABASE_PATH", "data.db")
DATA_DIR = Path(__file__).resolve().parent / "data"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _to_int(value, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(str(value).strip()))
    except ValueError:
        return default


def _read_tsv(filename: str) -> List[Dict[str, str]]:
    path = DATA_DIR / filename
    rows: List[Dict[str, str]] = []

    with path.open("r", encoding="latin1", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            cleaned = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k is not None}
            rows.append(cleaned)

    return rows


def _international_ratio(programme: str, year: int) -> float:
    """
    The Kaggle source files do not include domestic/international status.
    For the AUT assessment scenario, we add a realistic synthetic segmentation.

    Rationale:
    - Business/Economics/Computer Science/Data Science usually attract a higher international share.
    - 2020-2021 has a lower international ratio to simulate COVID border/travel impact.
    - 2022+ gradually recovers.
    """
    programme_lower = programme.lower()

    ratio = 0.22
    if any(word in programme_lower for word in ["economics", "business", "computer", "data", "engineering"]):
        ratio = 0.34
    elif any(word in programme_lower for word in ["english", "art", "history"]):
        ratio = 0.18
    elif any(word in programme_lower for word in ["biology", "nursing", "health"]):
        ratio = 0.16

    if year in [2020, 2021]:
        ratio -= 0.10
    elif year >= 2022:
        ratio += 0.04

    return max(0.08, min(0.45, ratio))


def _split_domestic_international(enrolled: int, programme: str, year: int, section_id: str, category: str) -> tuple[int, int]:
    """
    Deterministically split enrolled numbers into Domestic and International counts.
    A stable hash adds small variation while keeping the result repeatable.
    """
    ratio = _international_ratio(programme, year)

    seed_text = f"{section_id}-{category}-{programme}-{year}"
    seed = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest(), 16)
    variation = ((seed % 9) - 4) / 100  # -0.04 to +0.04

    international = round(enrolled * max(0.05, min(0.50, ratio + variation)))
    domestic = max(0, enrolled - international)
    return domestic, international


def init_db() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS enrolment_summary")

    cur.execute(
        """
        CREATE TABLE enrolment_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            semester TEXT,
            term_code TEXT,
            division TEXT,
            faculty TEXT,
            department TEXT,
            dept_code TEXT,
            programme TEXT,
            course_code TEXT,
            course_title TEXT,
            student_category TEXT,
            student_origin TEXT,
            section_status TEXT,
            delivery_code TEXT,
            section_capacity INTEGER,
            category_capacity INTEGER,
            enrolled INTEGER
        )
        """
    )

    departments = {row["dept_code"]: row for row in _read_tsv("department.tsv") if row.get("dept_code")}
    courses = {row["course_code"]: row for row in _read_tsv("course.tsv") if row.get("course_code")}
    terms = {row["term_code"]: row for row in _read_tsv("term.tsv") if row.get("term_code")}
    sections = {row["section_id"]: row for row in _read_tsv("section.tsv") if row.get("section_id")}
    student_caps = _read_tsv("student_cap.tsv")

    insert_rows = []

    for cap_row in student_caps:
        section_id = cap_row.get("section_id")
        section = sections.get(section_id)
        if not section:
            continue

        course = courses.get(section.get("course_code", ""))
        if not course:
            continue

        department = departments.get(course.get("dept_code", ""))
        if not department:
            continue

        term = terms.get(section.get("term_code", ""))
        if not term:
            continue

        year = _to_int(term.get("year"))
        enrolled = _to_int(cap_row.get("enrolled"))
        if not year:
            continue

        division = department.get("division", "Unknown")
        department_name = department.get("name", "Unknown")
        dept_code = department.get("dept_code", "")
        course_code = course.get("course_code", "")
        course_title = course.get("title", "")
        category = cap_row.get("category", "")

        domestic_count, international_count = _split_domestic_international(
            enrolled=enrolled,
            programme=department_name,
            year=year,
            section_id=section_id or "",
            category=category,
        )

        for origin, origin_count in [
            ("Domestic", domestic_count),
            ("International", international_count),
        ]:
            insert_rows.append(
                (
                    year,
                    term.get("semester", ""),
                    term.get("term_code", ""),
                    division,
                    division,  # faculty alias for natural-language questions
                    department_name,
                    dept_code,
                    department_name,  # programme alias for the AUT scenario
                    course_code,
                    course_title,
                    category,
                    origin,
                    section.get("status", ""),
                    section.get("delivery_code", ""),
                    _to_int(section.get("cap")),
                    _to_int(cap_row.get("cap")),
                    origin_count,
                )
            )

    cur.executemany(
        """
        INSERT INTO enrolment_summary (
            year, semester, term_code, division, faculty, department, dept_code,
            programme, course_code, course_title, student_category, student_origin,
            section_status, delivery_code, section_capacity, category_capacity, enrolled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        insert_rows,
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_year ON enrolment_summary(year)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_programme ON enrolment_summary(programme)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_faculty ON enrolment_summary(faculty)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_category ON enrolment_summary(student_category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_origin ON enrolment_summary(student_origin)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_enrolment_course ON enrolment_summary(course_code)")

    conn.commit()
    conn.close()
