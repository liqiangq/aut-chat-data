import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import get_connection, init_db
from llm import generate_sql_from_question

load_dotenv()

app = FastAPI(title="AUT Chat with Real University Data MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For the one-hour MVP. Restrict this in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    chart: dict[str, Any]
    note: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


def validate_sql(sql: str) -> str:
    cleaned = " ".join(sql.strip().split())
    upper = cleaned.upper()

    if not upper.startswith("SELECT "):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")

    blocked = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "TRUNCATE",
        "PRAGMA",
        "ATTACH",
        "DETACH",
    ]
    for keyword in blocked:
        if re.search(rf"\b{keyword}\b", upper):
            raise HTTPException(status_code=400, detail=f"Blocked SQL keyword: {keyword}")

    if ";" in cleaned:
        raise HTTPException(status_code=400, detail="Multiple SQL statements are not allowed.")

    if "FROM ENROLMENT_SUMMARY" not in upper and " ENROLMENT_SUMMARY " not in upper:
        raise HTTPException(status_code=400, detail="Query must read from the enrolment_summary table.")

    if " LIMIT " not in upper and " GROUP BY " not in upper:
        cleaned = f"{cleaned} LIMIT 100"

    return cleaned


def run_query(sql: str) -> tuple[list[str], list[dict[str, Any]]]:
    conn = get_connection()
    try:
        cur = conn.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        columns = list(rows[0].keys()) if rows else [description[0] for description in cur.description or []]
        return columns, rows
    finally:
        conn.close()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metadata")
def metadata() -> dict[str, Any]:
    conn = get_connection()
    try:
        total_rows = conn.execute("SELECT COUNT(*) AS count FROM enrolment_summary").fetchone()["count"]
        years = conn.execute("SELECT MIN(year) AS min_year, MAX(year) AS max_year FROM enrolment_summary").fetchone()
        programmes = [
            row["programme"]
            for row in conn.execute(
                "SELECT programme FROM enrolment_summary GROUP BY programme ORDER BY programme LIMIT 30"
            ).fetchall()
        ]
        faculties = [
            row["faculty"]
            for row in conn.execute(
                "SELECT faculty FROM enrolment_summary GROUP BY faculty ORDER BY faculty"
            ).fetchall()
        ]
        origins = [
            row["student_origin"]
            for row in conn.execute(
                "SELECT student_origin FROM enrolment_summary GROUP BY student_origin ORDER BY student_origin"
            ).fetchall()
        ]
        return {
            "rows": total_rows,
            "year_range": [years["min_year"], years["max_year"]],
            "faculties": faculties,
            "student_origins": origins,
            "sample_programmes": programmes,
        }
    finally:
        conn.close()


@app.get("/api/sample-questions")
def sample_questions() -> dict[str, list[str]]:
    return {
        "questions": [
            "How many international students were in the Economics programme by year for the last 5 years?",
            "Show domestic and international enrolments by year.",
            "Show enrolments by faculty.",
            "Which programmes had the most students?",
            "Show Computer Science enrolments by year.",
            "Show enrolments by student category.",
            "How many Business students were there by year?",
        ]
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required.")

    note = None
    lowered = request.question.lower()
    if "international" in lowered or "domestic" in lowered:
        note = (
            "Domestic/International is a synthetic but deterministic segmentation added for the AUT scenario, "
            "because the original Kaggle source files do not include student origin."
        )

    try:
        generated = generate_sql_from_question(request.question)
        sql = validate_sql(generated["sql"])
        columns, rows = run_query(sql)

        return ChatResponse(
            question=request.question,
            sql=sql,
            columns=columns,
            rows=rows,
            chart=generated.get("chart", {}),
            note=note,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not process question: {exc}") from exc


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
