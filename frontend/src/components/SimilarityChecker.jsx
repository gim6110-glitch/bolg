import { useState } from 'react';
import { API_BASE } from '../prompts';

export default function SimilarityChecker({ area, history }) {
  const [result, setResult] = useState(null);
  const candidates = history.filter((item) => item.area === area && item.sentence);
  if (candidates.length < 2) return null;

  async function runCheck() {
    const response = await fetch(`${API_BASE}/api/similarity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 영역: area, 문장목록: candidates.map((item, index) => ({ 식별자: item.id ?? `${index + 1}`, 문장: item.sentence })) }),
    });
    setResult(await response.json());
  }

  return (
    <section className="panel similarity-panel">
      <button type="button" className="secondary-button" onClick={runCheck}>같은 영역 결과 유사도 검사</button>
      {result && (
        <div>
          <h3>유사도 검사 결과</h3>
          {result.이상없음 ? <p>10자 이상 연속 일치 구절이 없습니다.</p> : result.유사쌍.map((pair, index) => (
            <p key={index}><b>{pair.학생들.join(' · ')}</b> {pair.유사구절} ({pair.심각도})</p>
          ))}
        </div>
      )}
    </section>
  );
}
