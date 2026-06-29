export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode-toggle" role="group" aria-label="작성 검토 모드">
      {['작성', '검토'].map((item) => (
        <button key={item} type="button" className={mode === item ? 'is-active' : ''} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}
