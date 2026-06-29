import CharCounter from './CharCounter';
import ViolationCard from './ViolationCard';

function CopyButton({ text }) {
  return <button type="button" className="copy-button" onClick={() => navigator.clipboard?.writeText(text ?? '')}>복사</button>;
}

export default function ResultPanel({ mode, result, areaMax, error }) {
  if (error) {
    return <section className="panel result-panel"><h2>오류</h2><div className="error-box">{error}</div></section>;
  }
  if (!result) {
    return <section className="panel result-panel empty"><h2>결과 표시</h2><p>입력 후 실행하면 AI 작성·검토 결과가 표시됩니다.</p></section>;
  }

  const isWrite = mode === '작성';
  const sentence = isWrite ? result.생성문장 : result.수정안;
  const count = result.글자수 ?? sentence?.length ?? 0;
  const max = result.최대글자수 ?? areaMax;

  return (
    <section className="panel result-panel">
      <header className="result-title">
        <h2>{isWrite ? '✅ 생성 완료' : `🔍 검토 결과 ${result.위반사항?.length ?? 0}건`}</h2>
        <CopyButton text={sentence} />
      </header>

      {!isWrite && result.원문 && (
        <div className="result-block">
          <h3>원문</h3>
          <p className="original-text">{result.원문}</p>
        </div>
      )}

      <div className="result-block">
        <h3>{isWrite ? '생성된 문장' : '수정안'}</h3>
        <p className="generated-text">{sentence}</p>
      </div>

      <CharCounter current={count} max={max} />

      {isWrite ? (
        <div className="result-block">
          <h3>제외된 항목</h3>
          {result.제외한항목?.length ? result.제외한항목.map((item, index) => (
            <span className="excluded-badge" key={`${item.내용}-${index}`}>🟡 {item.내용} → {item.사유}</span>
          )) : <p className="muted">제외된 항목이 없습니다.</p>}
          <h3>자가점검</h3>
          <div className="self-check">
            {Object.entries(result.자가점검 ?? {}).map(([key, value]) => <span key={key}>{value ? '✅' : '⚠️'} {key}</span>)}
          </div>
        </div>
      ) : (
        <div className="result-block">
          <h3>위반 항목</h3>
          {result.위반사항?.length ? result.위반사항.map((violation, index) => <ViolationCard key={index} violation={violation} />) : <p className="muted">위반사항이 없습니다.</p>}
          <p className="summary"><b>종합의견</b> {result.종합의견}</p>
        </div>
      )}
    </section>
  );
}
