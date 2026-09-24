import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Database, 
  Search, 
  Terminal, 
  BarChart3, 
  Table as TableIcon, 
  Copy, 
  Check, 
  Key, 
  Settings, 
  X, 
  Zap, 
  AlertCircle,
  HelpCircle,
  TrendingUp,
  SlidersHorizontal
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  Cell,
  CartesianGrid
} from 'recharts';

const SAMPLE_QUESTIONS = [
  "What are the top 5 product categories by revenue?",
  "Which state do most customers come from?",
  "What payment method do most customers use?",
  "Which product category has the lowest average review score?"
];

const MODELS = [
  { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash (Fastest)" },
  { id: "gemini-1.5-flash", name: "Gemini 1.5 Flash" },
  { id: "gemini-1.5-pro", name: "Gemini 1.5 Pro (Advanced)" }
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("gemini-2.0-flash");
  const [showSettings, setShowSettings] = useState(false);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copiedSql, setCopiedSql] = useState(false);
  const [showSql, setShowSql] = useState(true);

  // Run health check on mount
  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .catch(err => console.log('Backend starting...', err));
  }, []);

  const handleSearch = async (queryToRun) => {
    const q = queryToRun || question;
    if (!q.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q.trim(),
          api_key: apiKey.trim() || undefined,
          model: selectedModel
        })
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || data.detail || 'Failed to process business question.');
      } else {
        setResult(data);
      }
    } catch (err) {
      setError(`Network error: ${err.message}. Please check API endpoint.`);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  // Determine chartable columns if any
  const getChartConfig = () => {
    if (!result || !result.result || result.result.length === 0) return null;
    const records = result.result;
    const keys = Object.keys(records[0]);
    if (keys.length < 2) return null;

    let xKey = keys[0];
    let yKey = keys[1];

    // Find first numeric column for Y
    for (let k of keys) {
      if (typeof records[0][k] === 'number') {
        yKey = k;
        break;
      }
    }

    // Find first non-numeric or string column for X
    for (let k of keys) {
      if (k !== yKey && typeof records[0][k] !== 'number') {
        xKey = k;
        break;
      }
    }

    return { xKey, yKey, records: records.slice(0, 15) };
  };

  const chartConfig = getChartConfig();

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header Bar */}
      <header style={{
        borderBottom: '1px solid var(--border-color)',
        background: 'rgba(11, 15, 25, 0.8)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        padding: '16px 24px'
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'var(--gradient-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-glow)'
            }}>
              <BarChart3 size={24} color="#FFF" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(135deg, #FFF 0%, #A5B4FC 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                AI Business Analyst Assistant
              </h1>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Natural Language to SQL Analytics Engine
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button 
              className="btn-secondary" 
              onClick={() => setShowSettings(!showSettings)}
              style={{ position: 'relative' }}
            >
              <SlidersHorizontal size={16} />
              <span>Config</span>
              {apiKey && (
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-emerald)', position: 'absolute', top: '4px', right: '4px' }}></span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main style={{ flex: 1, maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '32px 24px' }}>

        {/* Settings Drawer / Modal */}
        {showSettings && (
          <div className="glass-panel animate-fade-in" style={{ padding: '24px', marginBottom: '32px', background: 'rgba(20, 27, 44, 0.95)', borderColor: 'var(--accent-indigo)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Key size={18} color="var(--accent-indigo)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>API & Model Settings</h3>
              </div>
              <button onClick={() => setShowSettings(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  🔑 Gemini API Key (Optional)
                </label>
                <input 
                  type="password" 
                  className="glass-input" 
                  style={{ width: '100%' }}
                  placeholder="Enter API key or leave blank for local SQL engine"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
                  Leave blank to use the built-in SQLite Business Engine.
                </span>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  🤖 Select Model
                </label>
                <select 
                  className="glass-input" 
                  style={{ width: '100%', cursor: 'pointer' }}
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {MODELS.map(m => (
                    <option key={m.id} value={m.id} style={{ background: '#121826', color: '#FFF' }}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Hero Search Section */}
        <section className="glass-panel" style={{ padding: '32px', marginBottom: '32px' }}>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '8px' }}>
            Ask a business question in plain English
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '24px' }}>
            Queries the SQLite e-commerce dataset instantly using Gemini AI or the built-in analytical engine.
          </p>

          <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }} style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={20} color="var(--text-muted)" style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }} />
              <input 
                type="text" 
                className="glass-input"
                style={{ width: '100%', paddingLeft: '48px', fontSize: '1rem' }}
                placeholder="e.g. What were the top 5 categories by revenue?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading || !question.trim()}>
              {loading ? (
                <>
                  <div style={{ width: '16px', height: '16px', border: '2px solid #FFF', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  Analyze
                </>
              )}
            </button>
          </form>

          {/* Question Chips */}
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '12px' }}>
              Suggested Queries:
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
              {SAMPLE_QUESTIONS.map((q, idx) => (
                <button 
                  key={idx} 
                  className="chip"
                  onClick={() => {
                    setQuestion(q);
                    handleSearch(q);
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Loading State */}
        {loading && (
          <div className="glass-panel animate-fade-in" style={{ padding: '48px', textAlign: 'center' }}>
            <div className="pulse-glow" style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'var(--gradient-glow)', border: '1px solid var(--accent-indigo)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
              <Sparkles size={32} color="var(--accent-indigo)" />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '8px' }}>Translating question into SQL...</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>Querying SQLite database & generating executive business summary</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="glass-panel animate-fade-in" style={{ padding: '24px', borderColor: 'var(--accent-rose)', background: 'rgba(244, 63, 94, 0.08)', marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <AlertCircle size={24} color="var(--accent-rose)" />
              <div>
                <h4 style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>Query Error</h4>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginTop: '2px' }}>{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Results Section */}
        {result && !loading && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* Answer Summary Card */}
            <div className="glass-panel" style={{ padding: '28px', background: 'var(--gradient-glow)', borderLeft: '4px solid var(--accent-indigo)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <TrendingUp size={22} color="var(--accent-indigo)" />
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Executive Answer Summary</h3>
                </div>
                
                <span className={`badge ${result.engine?.includes('Gemini') ? 'badge-gemini' : 'badge-sqlite'}`}>
                  <Zap size={12} />
                  {result.engine || 'SQL Engine'}
                </span>
              </div>

              <p style={{ fontSize: '1.05rem', lineHeight: '1.7', color: '#E2E8F0', fontWeight: 500 }}>
                {result.summary}
              </p>
            </div>

            {/* SQL Query Section */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Terminal size={18} color="var(--accent-violet)" />
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Generated SQL Query</h4>
                </div>
                
                <button className="btn-secondary" onClick={() => copyToClipboard(result.sql)}>
                  {copiedSql ? <Check size={14} color="var(--accent-emerald)" /> : <Copy size={14} />}
                  <span>{copiedSql ? 'Copied' : 'Copy SQL'}</span>
                </button>
              </div>

              <pre style={{
                background: '#070A12',
                padding: '16px',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                overflowX: 'auto',
                color: '#A5B4FC'
              }}>
                <code>{result.sql}</code>
              </pre>
            </div>

            {/* Interactive Chart (ifApplicable) */}
            {chartConfig && (
              <div className="glass-panel" style={{ padding: '28px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
                  <BarChart3 size={20} color="var(--accent-emerald)" />
                  <h4 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Data Visualization</h4>
                </div>

                <div style={{ width: '100%', height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartConfig.records} margin={{ top: 10, right: 30, left: 0, bottom: 40 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis 
                        dataKey={chartConfig.xKey} 
                        stroke="var(--text-muted)" 
                        fontSize={12} 
                        tick={{ fill: 'var(--text-secondary)' }}
                        angle={-25}
                        textAnchor="end"
                      />
                      <YAxis stroke="var(--text-muted)" fontSize={12} tick={{ fill: 'var(--text-secondary)' }} />
                      <Tooltip 
                        contentStyle={{ background: '#121826', border: '1px solid var(--border-color)', borderRadius: '8px', color: '#FFF' }}
                      />
                      <Bar dataKey={chartConfig.yKey} radius={[6, 6, 0, 0]}>
                        {chartConfig.records.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={`hsl(${240 + (index * 15)}, 80%, 65%)`} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Raw Result Data Table */}
            <div className="glass-panel" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <TableIcon size={20} color="var(--accent-indigo)" />
                  <h4 style={{ fontSize: '1.05rem', fontWeight: 700 }}>QueryResult ({result.result?.length || 0} rows)</h4>
                </div>
              </div>

              {result.result && result.result.length > 0 ? (
                <div style={{ overflowX: 'auto', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255, 255, 255, 0.04)', borderBottom: '1px solid var(--border-color)' }}>
                        {result.columns.map((col, idx) => (
                          <th key={idx} style={{ padding: '14px 18px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                            {col.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.result.map((row, rIdx) => (
                        <tr key={rIdx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)', transition: 'background 0.15s ease' }}>
                          {result.columns.map((col, cIdx) => (
                            <td key={cIdx} style={{ padding: '12px 18px', color: cIdx === 0 ? '#FFF' : 'var(--text-secondary)' }}>
                              {typeof row[col] === 'number' 
                                ? (Number.isInteger(row[col]) ? row[col].toLocaleString() : row[col].toFixed(2)) 
                                : String(row[col] ?? 'N/A')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No records returned from query.</p>
              )}
            </div>

          </div>
        )}

      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-color)', padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        Built with React, FastAPI, SQLite & Google Gemini — Ready for Vercel Deployment
      </footer>
    </div>
  );
}
