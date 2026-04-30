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
- If the user asks for "by year", "per year", "yearly", "over time", or "last 5 years", year must be the primary grouping column.
- If the user asks for "last 5 years", use year >= 2019 because this dataset covers multiple terms up to 2023.
- A programme name such as Economics, Computer Science, Biology, Mathematics, English, or Business should be used as a WHERE filter. It must not override a requested year grouping.
- Only group by programme when the user asks for a programme/program/department comparison or says "by programme", "by program", or "by department".
- Only group by faculty when the user asks for a faculty/division comparison or says "by faculty" or "by division".
- Only group by student_category when the user asks for a category comparison or says "by category".
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
    selected_programme = None
    selected_category = None
    by_year = any(phrase in q for phrase in ["by year", "per year", "yearly", "over time", "trend", "last 5", "last five", "five years"])
    last_five_years = "last 5" in q or "last five" in q or "five years" in q
    wants_origin_breakdown = ("domestic" in q and "international" in q) or "origin" in q
    wants_faculty_breakdown = "by faculty" in q or "by division" in q or ("faculty" in q and not by_year)
    wants_programme_breakdown = (
        "by programme" in q
        or "by program" in q
        or "by department" in q
        or "programmes" in q
        or "programs" in q
        or ("programme" in q and not by_year)
        or ("program" in q and not by_year)
        or ("department" in q and not by_year)
    )
    wants_category_breakdown = "by category" in q or ("category" in q and not by_year)

    if "business" in q or "economics" in q:
        selected_programme = "Economics"
    if "computer" in q or "cosc" in q:
        selected_programme = "Computer Science"
    if "biology" in q or "biol" in q:
        selected_programme = "Biology"
    if "math" in q:
        selected_programme = "Mathematics"
    if "english" in q:
        selected_programme = "English"
    if "law" in q:
        selected_programme = "Political Science"

    if selected_programme:
        where.append(f"programme = '{selected_programme}'")

    if "international" in q and "domestic" not in q:
        where.append("student_origin = 'International'")
    if "domestic" in q and "international" not in q:
        where.append("student_origin = 'Domestic'")

    if "freshman" in q:
        selected_category = "Freshman"
    if "sophomore" in q:
        selected_category = "Sophomore"
    if "junior" in q:
        selected_category = "Junior"
    if "senior" in q:
        selected_category = "Senior"

    if selected_category:
        where.append(f"student_category = '{selected_category}'")

    if last_five_years:
        where.append("year >= 2019")

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    if by_year:
        dimensions = ["year"]
        if wants_origin_breakdown:
            dimensions.append("student_origin")
        if wants_faculty_breakdown:
            dimensions.append("faculty")
        if wants_programme_breakdown and not selected_programme:
            dimensions.append("programme")
        if wants_category_breakdown and not selected_category:
            dimensions.append("student_category")

        select_columns = ", ".join(dimensions)
        group_columns = ", ".join(dimensions)
        order_columns = ", ".join(dimensions)
        sql = f"""
        SELECT {select_columns}, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY {group_columns}
        ORDER BY {order_columns}
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "line", "x": "year", "y": "total_students"}}

    if wants_origin_breakdown:
        sql = f"""
        SELECT student_origin, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY student_origin
        ORDER BY student_origin
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "student_origin", "y": "total_students"}}

    if wants_faculty_breakdown:
        sql = f"""
        SELECT faculty, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY faculty
        ORDER BY total_students DESC
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "faculty", "y": "total_students"}}

    if wants_programme_breakdown and not selected_programme:
        sql = f"""
        SELECT programme, SUM(enrolled) AS total_students
        FROM enrolment_summary
        {where_clause}
        GROUP BY programme
        ORDER BY total_students DESC
        LIMIT 10
        """
        return {"sql": " ".join(sql.split()), "chart": {"type": "bar", "x": "programme", "y": "total_students"}}

    if wants_category_breakdown and not selected_category:
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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def generate_sql_from_question(question: str) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    if not api_key:
        return fallback_generate(question)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=20.0,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SCHEMA_DESCRIPTION},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content or ""
        parsed = extract_json(content)
        if not isinstance(parsed.get("sql"), str):
            return fallback_generate(question)
        if not isinstance(parsed.get("chart"), dict):
            parsed["chart"] = {}
        return parsed
    except Exception as exc:
        print(f"OpenRouter request failed, using local fallback: {exc}")
        return fallback_generate(question)
