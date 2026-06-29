import { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import ExcelUpload from './components/ExcelUpload';
import InputPanel from './components/InputPanel';
import ModeToggle from './components/ModeToggle';
import ResultPanel from './components/ResultPanel';
import SimilarityChecker from './components/SimilarityChecker';
import TabBar from './components/TabBar';
import { API_BASE, AREAS } from './prompts';

function App() {
  const [mode, setMode] = useState('작성');
  const [area, setArea] = useState('자율활동');
  const [formValues, setFormValues] = useState({});
  const [reviewText, setReviewText] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const areaMax = useMemo(() => AREAS.find((item) => item.key === area)?.max ?? 500, [area]);

  function handleFieldChange(name, value) {
    setFormValues((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const endpoint = mode === '작성' ? '/api/generate' : '/api/review';
      const body = mode === '작성' ? { 영역: area, 입력: formValues } : { 영역: area, 문구: reviewText };
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.detail?.error ?? data.detail?.message ?? data.error ?? '요청 처리 실패');
      setResult(data);
      const sentence = mode === '작성' ? data.생성문장 : data.수정안;
      if (sentence) setHistory((previous) => [...previous, { area, sentence, id: `${previous.length + 1}` }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <p>2015 개정 교육과정 3학년 전용</p>
        <h1>학교생활기록부 작성·검토 프로그램</h1>
        <span>2026학년도 기재요령 기준 · Claude Sonnet 4.6 연동</span>
      </header>
      <ModeToggle mode={mode} onChange={setMode} />
      <TabBar area={area} onChange={(nextArea) => { setArea(nextArea); setResult(null); setError(''); }} />
      <main className="workspace">
        <InputPanel
          area={area}
          mode={mode}
          values={formValues}
          reviewText={reviewText}
          onFieldChange={handleFieldChange}
          onReviewTextChange={setReviewText}
          onSubmit={handleSubmit}
          loading={loading}
        />
        <ResultPanel mode={mode} result={result} areaMax={areaMax} error={error} />
      </main>
      <SimilarityChecker area={area} history={history} />
      <ExcelUpload />
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
