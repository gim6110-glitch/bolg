export default function ViolationCard({ violation }) {
  const severity = violation.심각도 === '높음' ? 'high' : violation.심각도 === '중간' ? 'medium' : 'low';
  return (
    <article className={`violation-card ${severity}`}>
      <div>
        <strong>{violation.유형}</strong>
        <span>{violation.심각도}</span>
      </div>
      <p><b>원문위치</b> {violation.원문위치}</p>
      <p><b>수정제안</b> {violation.수정제안}</p>
      <p><b>근거</b> {violation.근거}</p>
    </article>
  );
}
