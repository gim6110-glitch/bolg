import { FIELD_CONFIG } from '../prompts';

export default function InputPanel({ area, mode, values, reviewText, onFieldChange, onReviewTextChange, onSubmit, loading }) {
  const fields = FIELD_CONFIG[area] ?? [];
  return (
    <section className="panel input-panel">
      <h2>{mode === '작성' ? '교사 관찰 입력' : '기존 문구 검토'}</h2>
      <form onSubmit={onSubmit}>
        {mode === '검토' ? (
          <label className="field full">
            <span>기존 작성 문구 <em>필수</em></span>
            <textarea value={reviewText} onChange={(event) => onReviewTextChange(event.target.value)} rows={12} required />
          </label>
        ) : (
          <div className="field-grid">
            {fields.map((field) => (
              <label className={field.type === 'text' || field.type === 'select' ? 'field' : 'field full'} key={field.name}>
                <span>{field.label} {field.required && <em>필수</em>}</span>
                {field.type === 'select' ? (
                  <select value={values[field.name] ?? field.options[0]} onChange={(event) => onFieldChange(field.name, event.target.value)} required={field.required}>
                    {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                ) : field.type === 'text' ? (
                  <input value={values[field.name] ?? ''} onChange={(event) => onFieldChange(field.name, event.target.value)} required={field.required} />
                ) : (
                  <textarea value={values[field.name] ?? ''} onChange={(event) => onFieldChange(field.name, event.target.value)} rows={4} required={field.required} />
                )}
              </label>
            ))}
          </div>
        )}
        <button className="primary-button" type="submit" disabled={loading}>{loading ? '처리 중...' : mode === '작성' ? '문장 작성' : '문구 검토'}</button>
      </form>
    </section>
  );
}
