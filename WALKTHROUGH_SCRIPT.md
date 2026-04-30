# Walkthrough Script

## 1. Opening

Hi, thanks for the opportunity. I approached this as a one-hour MVP, so I focused on building a working end-to-end product rather than over-engineering the architecture.

The original brief suggested generating dummy university enrolment data. I found a real Kaggle-style university course and student enrolment dataset, so I used that to make the prototype more realistic.

The final flow is: natural-language question, LLM-generated SQL, backend validation, SQLite query execution, and a frontend table plus chart.

## 2. Tech stack

I used FastAPI for the backend because it is quick to build, easy to expose APIs, and works well for Python-based AI integration.

I used SQLite for the local data layer. For a one-hour MVP, it is lightweight and easy to deploy. The source dataset is loaded from TSV files and transformed into one analytics table.

The frontend is React with Vite, and the charting library is Recharts.

The LLM integration uses OpenRouter through the standard OpenAI SDK format.

## 3. Data explanation

The dataset includes course, section, term, department, and student capacity/enrolment files.

I join the data like this:

student_cap to section by section_id,
section to course by course_code,
course to department by dept_code,
and section to term by term_code.

For the frontend and LLM, I expose a simplified analytics table called enrolment_summary.

The main columns are year, faculty, department, programme, course code, course title, student category, and enrolled count.

The original Kaggle data does not include domestic/international status. However, that is very important for a university analytics scenario, so I added a deterministic synthetic student_origin field with Domestic and International values. I also kept the original student categories, such as Freshman, Sophomore, Junior, and Senior.

## 4. Demo

First, I can ask:

"How many students were in the Economics programme by year for the last 5 years?"

The frontend sends that to POST /api/chat.

The backend sends the question and schema instructions to the LLM. The LLM returns JSON containing a SQL query and chart metadata.

The backend then validates the SQL, executes it against SQLite, and returns the rows, columns, SQL, and chart configuration.

The frontend renders the results as both a data table and a chart.

I also included sample questions so the assessors can quickly test different types of analysis, such as international Economics students over time, domestic versus international enrolments, enrolments by faculty, top programmes, Computer Science over time, and student category breakdown.

## 5. SQL safety

The LLM does not directly access the database. It only proposes a SQL query.

The backend validates the generated SQL before execution. It only allows SELECT statements, blocks write or schema-changing keywords, blocks multiple statements, and requires queries to read from the enrolment_summary table.

This is suitable for an MVP. In production, I would use a stronger SQL parser, a read-only database user, row limits, timeouts, and audit logging.

## 6. Architecture decisions

The key pragmatic decision was to transform the raw dataset into one analytics table.

That reduces LLM complexity, improves reliability, and makes the SQL generation easier to control.

In a production system, I would probably introduce a semantic layer with approved metrics, such as total enrolments, enrolments by faculty, and enrolments by programme. That would reduce ambiguity and make answers more consistent for business users.

## 7. Deployment

The app can be deployed as a single Render web service.

The build command installs backend dependencies, installs frontend dependencies, and builds the React app.

The FastAPI backend serves both the API and the built frontend. This keeps deployment simple and suitable for a one-hour assessment.

The OpenRouter API key is not stored in GitHub. It is configured as an environment variable in Render.

## 8. Production discussion

For an enterprise version, I would add:

- Authentication and role-based access control
- Secure secret management
- Read-only database access
- Strong SQL validation
- A semantic data layer
- Query limits and timeouts
- Audit logging
- Monitoring and tracing
- CI/CD with automated tests
- Clear separation of dev, test, and production environments

For production, I would replace the synthetic domestic/international field with the real university source-of-truth field from the student information system.

## 9. Closing

Overall, this MVP demonstrates the full path from natural language to data insight using a real dataset. It is intentionally pragmatic, but the structure leaves clear extension points for security, reliability, and enterprise readiness.
