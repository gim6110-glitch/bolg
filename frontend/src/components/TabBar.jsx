import { AREAS } from '../prompts';

export default function TabBar({ area, onChange }) {
  return (
    <nav className="tab-bar" aria-label="학생부 영역 선택">
      {AREAS.map((item) => (
        <button
          key={item.key}
          type="button"
          className={area === item.key ? 'tab is-active' : 'tab'}
          onClick={() => onChange(item.key)}
        >
          <span>{item.short}</span>
          <small>{item.max}자</small>
        </button>
      ))}
    </nav>
  );
}
