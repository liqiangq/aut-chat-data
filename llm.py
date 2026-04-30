import json
import os
import re
from typing import Any

from openai import OpenAI

SCHEMA_DESCRIPTION = """
You are generating SQLite SELECT queries for a university enrolment analytics app.

The application uses a Kaggle-style university course and enrolment dataset transformed into one analytics table.

Table: enrolment_summary

Columns:
- year INTEGER
- semester TEXT
- term_code TEXT
- division TEXT
- faculty TEXT -- alias of division for business-user language
- department TEXT
- dept_code TEXT
- programme TEXT -- alias of department for the AUT scenario
- course_code TEXT
- course_title TEXT
- student_category TEXT -- examples: Freshman, Sophomore, Junior, Senior
- student_origin TEXT -- values: Domestic, International
- section_status TEXT
- delivery_code TEXT
- section_capacity INTEGER
- category_capacity INTEGER
- enrolled INTEGER

Important rules:
- Return ONLY valid JSON.
- JSON shape:
  {
    "sql": "SELECT ...",
    "chart": {"type": "bar", "x": "year", "y": "total_students"}
  }
- SQL must be a single SELECT statement.
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, or multiple statements.
- Use SUM(enrolled) when aggregating student numbers.
- Use clear aliases such as total_students.
- If the user asks for "last 5 years", use year >= 2019 because this dataset covers multiple terms up to 2023.
- If the user asks about Business and there is no exact Business programme, use programme = 'Economics' as the closest business-related department in this dataset.
- If the user asks about international students, filter student_origin = 'International'.
- If the user asks about domestic students, filter student_origin = 'Domestic'.

Example:
Question: How many international students were in the Economics programme by year for the last 5 years?
Answer:
{
  "sql": "SELECT year, SUM(enrolled) AS total_students FROM enrolment_summary WHERE programme = 'Economics' AND student_origin = 'International' AND year >= 2019 GROUP BY year ORDER BY year",
  "chart": {"type": "bar", "x": "year", "y": "total_students"}
}

Question: Show domestic and international enrolments by year.
Answer:
{
  "sql": "SELECT year, student_origin, SUM(enrolled) AS total_students FROM enrolment_summary GROUP BY year, student_origin ORDER BY year, student_origin",
  "chart": {"type": "bar", "x": "year", "y": "total_students"}
}
"""


def fallback_generate(question: str) -> dict[str, Any]:
    """Simple deterministic fallback so the MVP still works without an API key."""
    q = question.lower()

    where = []

    if "business" in q or "economics" in q:
        where.append("programme = 'Economics'")
    if "computer" in q or "cosc" in q:
        where.append("programme = 'Computer Science'")
    if "biology" in q or "biol" in q:
        where.append("programme = 'Biology'")
    if "math" in q:
        where.append("programme = 'Mathematics'")
    if "english" in q:
        where.append("programme = 'English'")
    if "law" in q:
        where.append("programme = 'Political Science'")

    if "international" in q and "domestic" not in q:
        where.append("student_origin = 'International'")
    if "domestic" in q and "international" not in q:
        where.append("student_origin = 'Domestic'")

    if "freshman" in q:
        where.append("student_category = 'Freshman'")
    if "sophomore" in q:
        where.append("student_category = 'Sophomore'")
    if "junior" in q:
        where.append("student_category = 'Junior'")
    if "senior" in q:
        where.append("student_category = 'Senior'")

    if "last 5" in q or "five" in q:
        where.append("year >= 2019")

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    if ("domestic" in q and "international" in q) or "origin" in q:
        sql = f"""
        SELECT year, student_origin, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY year, student_origin
        ORDER BY year, student_origin
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "year", "y": "total_students"}}

    if "faculty" in q or "division" in q:
        sql = f"""
        SELECT faculty, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY faculty
        ORDER BY total_students DESC
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "faculty", "y": "total_students"}}

    if "programme" in q or "program" in q or "department" in q:
        sql = f"""
        SELECT programme, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY programme
        ORDER BY total_students DESC
        LIMIT 10
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "programme", "y": "total_students"}}

    if "category" in q or "freshman" in q or "sophomore" in q or "junior" in q or "senior" in q:
        sql = f"""
        SELECT student_category, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY student_category
        ORDER BY total_students DESC
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "student_category", "y": "total_students"}}

    sql = f"""
    SELECT year, SUM(enrolled) AS total_students
    FROM enrolment_summary
    {where_clause}
    GROUP BY year
    ORDER BY year
    """
    return {"sql": " ".join(sql.split()), "chart": {"type": "line", "x": "year", "y": "total_students"}}


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def generate_sql_from_question(question: str) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    if not api_key:
        return fallback_generate(question)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SCHEMA_DESCRIPTION},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )

    content = response.choices[0].message.content or ""
    return extract_json(content)
