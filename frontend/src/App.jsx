import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Send, Database, ShieldCheck, Info } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

function DataTable({ columns, rows }) {
  if (!rows || rows.length === 0) {
    return <div className="empty">No data returned.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{row[column]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultChart({ chart, rows }) {
  const chartConfig = chart || {};
  const xKey = chartConfig.x;
  const yKey = chartConfig.y;

  const canRender = rows && rows.length > 0 && xKey && yKey;
  if (!canRender) {
    return <div className="empty">Ask a question to render a chart.</div>;
  }

  const chartType = chartConfig.type || 'bar';

  return (
    <div className="chart-card">
      <ResponsiveContainer width="100%" height={280}>
        {chartType === 'line' ? (
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey={yKey} strokeWidth={3} />
          </LineChart>
        ) : (
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Bar dataKey={yKey} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState('How many international students were in the Economics programme by year for the last 5 years?');
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/api/sample-questions`)
      .then((res) => res.json())
      .then((data) => setSampleQuestions(data.questions || []))
      .catch(() => setSampleQuestions([]));

    fetch(`${API_BASE}/api/metadata`)
      .then((res) => res.json())
      .then((data) => setMetadata(data))
      .catch(() => setMetadata(null));
  }, []);

  const lastSql = useMemo(() => result?.sql || '', [result]);

  async function askQuestion(nextQuestion = question) {
    const q = nextQuestion.trim();
    if (!q) return;

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
      }

      setResult(data);
      setHistory((items) => [q, ...items.filter((item) => item !== q)].slice(0, 5));
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    askQuestion();
  }

  return (
    <main className="page">
      <section className="hero">
        <div>
          <div className="badge">AUT AI Acceleration Centre · Kaggle Data MVP</div>
          <h1>Chat with University Data</h1>
          <p>
            Ask natural-language questions about a real Kaggle university enrolment dataset.
            The backend translates the question into safe SQL, queries SQLite, and returns a table and chart.
          </p>
        </div>
      </section>

      {metadata && (
        <section className="meta">
          <div><strong>{metadata.rows}</strong><span>analytics rows</span></div>
          <div><strong>{metadata.year_range?.[0]}–{metadata.year_range?.[1]}</strong><span>year range</span></div>
          <div><strong>{metadata.faculties?.length}</strong><span>faculties/divisions</span></div>
          <div><strong>{metadata.student_origins?.join(' / ')}</strong><span>student origin</span></div>
        </section>
      )}

      <section className="grid">
        <div className="panel chat-panel">
          <div className="panel-header">
            <Database size={20} />
            <h2>Ask a data question</h2>
          </div>

          <form onSubmit={handleSubmit} className="ask-form">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Example: Show Economics students by year for the last 5 years"
            />
            <button type="submit" disabled={loading}>
              <Send size={18} />
              {loading ? 'Asking...' : 'Ask'}
            </button>
          </form>

          <div className="chips">
            {sampleQuestions.map((sample) => (
              <button
                key={sample}
                type="button"
                onClick={() => {
                  setQuestion(sample);
                  askQuestion(sample);
                }}
              >
                {sample}
              </button>
            ))}
          </div>

          {history.length > 0 && (
            <div className="history">
              <strong>Recent questions</strong>
              {history.map((item) => (
                <button key={item} onClick={() => askQuestion(item)}>
                  {item}
                </button>
              ))}
            </div>
          )}

          {error && <div className="error">{error}</div>}
          {result?.note && (
            <div className="note">
              <Info size={16} />
              {result.note}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <ShieldCheck size={20} />
            <h2>Result chart</h2>
          </div>
          <ResultChart chart={result?.chart} rows={result?.rows || []} />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Result table</h2>
        </div>
        <DataTable columns={result?.columns || []} rows={result?.rows || []} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Generated SQL</h2>
        </div>
        <pre>{lastSql || 'No SQL generated yet.'}</pre>
      </section>
    </main>
  );
}
