# AUT Chat with University Data MVP

This is a one-hour MVP for the AUT AI Acceleration Centre Senior Developer technical assessment.

The app uses a real Kaggle-style university course/enrolment dataset uploaded as TSV files. It transforms the source tables into a simple analytics table called `enrolment_summary`, then lets a user ask natural-language questions and receive a table plus chart.

## Why this dataset

The original assessment asks for dummy university enrolment data. I found and used a richer Kaggle university student/course dataset instead. This makes the MVP more realistic while keeping the implementation pragmatic for a one-hour timebox.

Note: this dataset has student categories such as Freshman, Sophomore, Junior, and Senior. The original source does not contain domestic/international status, so I add a deterministic synthetic `student_origin` field for the AUT scenario. For the AUT scenario, I use:

- `faculty` as an alias for dataset `division`
- `programme` as an alias for dataset `department`
- `enrolled` as the enrolment count
- `student_origin` as a synthetic Domestic/International segmentation

## Tech stack

- Frontend: React + Vite
- Charting: Recharts
- Backend: FastAPI
- Database: SQLite
- LLM: OpenRouter using the OpenAI SDK format
- Deployment: Render

## Data model

The backend loads these core files:

```text
backend/data/course.tsv
backend/data/section.tsv
backend/data/term.tsv
backend/data/department.tsv
backend/data/student_cap.tsv
```

It joins them into:

```text
enrolment_summary
```

Main columns:

```text
year
semester
faculty
department
programme
course_code
course_title
student_category
student_origin
section_status
section_capacity
category_capacity
enrolled
```

Join logic:

```text
student_cap.section_id -> section.section_id
section.course_code -> course.course_code
course.dept_code -> department.dept_code
section.term_code -> term.term_code
```

## Features

- Natural-language chat input
- Real Kaggle university enrolment dataset
- LLM-generated SQL
- SQL validation to allow only safe `SELECT` statements
- Result table
- Bar/line chart
- Sample question buttons
- Metadata summary
- Local fallback SQL generation if no API key is provided

## Run locally

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env`:

```bash
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
DATABASE_PATH=data.db
```

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

Health check:

```text
http://localhost:8000/api/health
```

Metadata check:

```text
http://localhost:8000/api/metadata
```

### 2. Frontend

Open a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```bash
VITE_API_BASE=http://localhost:8000
```

Start frontend:

```bash
npm run dev
```

Then open:

```text
http://localhost:5173
```

## Example questions

```text
How many international students were in the Economics programme by year for the last 5 years?
Show domestic and international enrolments by year.
Show enrolments by faculty.
Which programmes had the most students?
Show Computer Science enrolments by year.
Show enrolments by student category.
How many Business students were there by year?
```

For "Business", the prompt maps it to Economics because this dataset does not contain a direct Business programme.

Domestic/International values are synthetic and deterministic. I added them because this segmentation is important in real university analytics and in the AUT assessment scenario. The logic gives business/computing-related programmes a higher international ratio, reduces international share around 2020–2021 to simulate COVID impact, and recovers from 2022 onwards.

## API

### POST `/api/chat`

Request:

```json
{
  "question": "How many international students were in the Economics programme by year for the last 5 years?"
}
```

Response:

```json
{
  "question": "How many international students were in the Economics programme by year for the last 5 years?",
  "sql": "SELECT year, SUM(enrolled) AS total_students FROM enrolment_summary WHERE programme = 'Economics' AND year >= 2019 GROUP BY year ORDER BY year",
  "columns": ["year", "total_students"],
  "rows": [
    {"year": 2019, "total_students": 123},
    {"year": 2020, "total_students": 130}
  ],
  "chart": {
    "type": "bar",
    "x": "year",
    "y": "total_students"
  },
  "note": null
}
```

## SQL safety controls

The backend:

- Only allows SQL beginning with `SELECT`
- Blocks dangerous keywords such as `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, and `CREATE`
- Blocks multiple SQL statements
- Requires the query to read from `enrolment_summary`
- Adds a limit for non-aggregated queries

## Production improvements

For a production enterprise version, I would add:

- Authentication and role-based access control
- Read-only database credentials
- SQL parser-based validation
- A semantic layer with approved metrics and dimensions
- Query timeout and row limits
- Audit logging of user questions and generated SQL
- Rate limiting
- Monitoring and tracing
- Secure secret management
- CI/CD and automated tests
- Separate dev/test/prod environments

## Deploy to Render

### Option A: Deploy using GitHub

1. Push this project to GitHub.
2. Go to Render.
3. Create a new **Web Service**.
4. Connect your GitHub repository.
5. Use these settings:

```text
Environment: Python

Build Command:
pip install -r backend/requirements.txt && cd frontend && npm install && npm run build

Start Command:
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

6. Add environment variables:

```text
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
DATABASE_PATH=data.db
```

7. Deploy.

### Option B: Deploy using render.yaml

This repository includes a `render.yaml` file. In Render, choose **New Blueprint**, connect the repository, and Render will read the deployment configuration.

You still need to add the secret variable manually:

```text
OPENROUTER_API_KEY
```

## What to submit

Submit:

```text
1. Live public URL from Render
2. GitHub repository URL
```
