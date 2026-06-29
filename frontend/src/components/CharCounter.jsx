export default function CharCounter({ current = 0, max = 500 }) {
  const percent = max ? Math.min((current / max) * 100, 140) : 0;
  const status = current > max ? 'over' : percent >= 80 ? 'warn' : 'normal';
  return (
    <div className={`char-counter ${status}`}>
      <div className="char-counter__label">
        <strong>글자수</strong>
        <span>{current} / {max}</span>
      </div>
      <div className="char-counter__track">
        <div className="char-counter__bar" style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
      <small>한글 기준 공백·기호 포함 len() 값이며 NEIS 바이트 기준과 다를 수 있습니다.</small>
    </div>
  );
}
