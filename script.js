const AREA_LABELS = {
  자율활동: '자율활동',
  동아리활동: '동아리활동',
  진로활동: '진로활동',
  세특: '과목별 세부능력 및 특기사항',
  행발: '행동특성 및 종합의견',
};

const AREA_LIMITS = {
  자율활동: 500,
  동아리활동: 500,
  진로활동: 500,
  세특: 500,
  행발: 300,
};

const FIELD_CONFIG = {
  자율활동: [
    { name: '학생특성', label: '학생특성', type: 'textarea', required: false, full: true },
    { name: '활동1', label: '활동 1', type: 'textarea', required: true },
    { name: '결과물1', label: '결과물 1', type: 'textarea', required: false },
    { name: '활동2', label: '활동 2', type: 'textarea', required: false },
    { name: '결과물2', label: '결과물 2', type: 'textarea', required: false },
    { name: '활동3', label: '활동 3', type: 'textarea', required: false },
    { name: '결과물3', label: '결과물 3', type: 'textarea', required: false },
  ],
  진로활동: [
    { name: '희망분야', label: '희망분야', type: 'text', required: true },
    { name: '학생특성', label: '학생특성', type: 'textarea', required: false },
    { name: '활동1', label: '활동 1', type: 'textarea', required: true },
    { name: '결과물1', label: '결과물 1', type: 'textarea', required: false },
    { name: '활동2', label: '활동 2', type: 'textarea', required: false },
    { name: '결과물2', label: '결과물 2', type: 'textarea', required: false },
    { name: '활동3', label: '활동 3', type: 'textarea', required: false },
    { name: '결과물3', label: '결과물 3', type: 'textarea', required: false },
    { name: '상담내용', label: '상담내용', type: 'textarea', required: false, full: true },
  ],
  동아리활동: [
    { name: '동아리명', label: '동아리명', type: 'text', required: true, full: true },
    { name: '학생평가', label: '학생평가', type: 'textarea', required: true },
    { name: '역할', label: '역할', type: 'textarea', required: false },
    { name: '협업', label: '협업', type: 'textarea', required: false },
    { name: '성장', label: '성장', type: 'textarea', required: false },
    { name: '심화탐구', label: '심화탐구', type: 'textarea', required: false, full: true },
  ],
  세특: [
    { name: '과목명', label: '과목명', type: 'text', required: true },
    { name: '성취수준', label: '성취수준', type: 'select', required: true, options: ['상', '중상', '중', '중하', '하'] },
    { name: '과제', label: '과제', type: 'textarea', required: true, full: true },
    { name: '학생평가', label: '학생평가', type: 'textarea', required: true, full: true },
  ],
  행발: [
    { name: '지속관찰행동', label: '지속관찰행동', type: 'textarea', required: false },
    { name: '리더십공동체기여', label: '리더십공동체기여', type: 'textarea', required: false },
    { name: '나눔배려협업', label: '나눔배려협업', type: 'textarea', required: false },
    { name: '자기주도책임감', label: '자기주도책임감', type: 'textarea', required: false },
    { name: '학습탐구', label: '학습탐구', type: 'textarea', required: false },
    { name: '변화성장', label: '변화성장', type: 'textarea', required: false },
    { name: '담임교사종합관찰', label: '담임교사종합관찰', type: 'textarea', required: true, full: true },
  ],
};

const FORBIDDEN_RULES = [
  { regex: /\b(TOEIC|TOEFL|TEPS|HSK|JPT|JLPT|DELF|DALF|TESTDAF|DSH|DSD|TORFL|DELE)\b|한자능력검정/gi, type: '금지어(가)', reason: '공인어학시험 참여 사실·성적·수상은 기재 불가.' },
  { regex: /대회|수상|최우수상|우수상|장려상|입상|금상|은상|동상/g, type: '금지어(나)', reason: '교내·외 대회 참여·성적·수상 및 대회 표현은 기재 불가.' },
  { regex: /표창장|감사장|공로상/g, type: '금지어(다)', reason: '교외 기관·단체장이 수여한 상은 기재 불가.' },
  { regex: /모의고사|전국연합|원점수|석차|백분위|등급/g, type: '금지어(마)', reason: '모의고사·전국연합학력평가 성적은 기재 불가.' },
  { regex: /논문|학회지|투고|등재|도서 출간|특허|실용신안|상표|해외|어학연수/g, type: '금지어', reason: '학생부 공통 기재 금지 항목.' },
  { regex: /아버지|어머니|부모|친인척|의사인|검사인|교수인|대표인/g, type: '금지어(차)', reason: '부모·친인척의 사회·경제적 지위 암시는 기재 불가.' },
  { regex: /\b\d{6,}\b|\b010[-\s]?\d{4}[-\s]?\d{4}\b|[가-힣]{2,4}\s?학생/g, type: '개인정보', reason: '학생 이름·학번·연락처 등 개인정보는 제거 필요.' },
];

let currentMode = '작성';
let currentArea = '자율활동';
let latestText = '';

const form = document.querySelector('#record-form');
const fieldsEl = document.querySelector('#dynamic-fields');
const inputTitle = document.querySelector('#input-title');
const limitBadge = document.querySelector('#limit-badge');
const resultEl = document.querySelector('#result');
const copyButton = document.querySelector('#copy-button');
const uploadInput = document.querySelector('#excel-upload');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
}

function compact(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function nominal(sentence) {
  const cleaned = compact(sentence).replace(/[.。]+$/g, '');
  if (!cleaned) return '입력된 관찰 근거가 부족하여 추가 기록이 필요함.';
  if (/(함|음|임|보임|드러냄|기여함|확인됨|발휘함|탐색함|분석함|구체화함|실천함)$/.test(cleaned)) return `${cleaned}.`;
  return `${cleaned}을 보임.`;
}

function renderFields() {
  const areaLabel = AREA_LABELS[currentArea];
  const limit = AREA_LIMITS[currentArea];
  inputTitle.textContent = `${areaLabel} ${currentMode} 입력`;
  limitBadge.textContent = `최대 ${limit}자`;
  form.reset();

  if (currentMode === '검토') {
    fieldsEl.innerHTML = `
      <label class="field full">
        <span>기존 작성 문구 <em>필수</em></span>
        <textarea name="기존작성문구" rows="12" required placeholder="검토할 기존 학생부 문장을 입력하세요."></textarea>
      </label>
    `;
    return;
  }

  fieldsEl.innerHTML = FIELD_CONFIG[currentArea].map((field) => {
    const required = field.required ? 'required' : '';
    const mark = field.required ? '<em>필수</em>' : '<small>선택</small>';
    const cls = field.full ? 'field full' : 'field';
    if (field.type === 'select') {
      return `<label class="${cls}"><span>${field.label} ${mark}</span><select name="${field.name}" ${required}>${field.options.map((option) => `<option value="${option}">${option}</option>`).join('')}</select></label>`;
    }
    if (field.type === 'text') {
      return `<label class="${cls}"><span>${field.label} ${mark}</span><input name="${field.name}" ${required} /></label>`;
    }
    return `<label class="${cls}"><span>${field.label} ${mark}</span><textarea name="${field.name}" rows="4" ${required}></textarea></label>`;
  }).join('');
}

function collectFormData() {
  const data = {};
  new FormData(form).forEach((value, key) => {
    const cleaned = compact(value);
    if (cleaned) data[key] = cleaned;
  });
  return data;
}

function findViolations(text) {
  const violations = [];
  FORBIDDEN_RULES.forEach((rule) => {
    [...text.matchAll(rule.regex)].forEach((match) => {
      violations.push({ type: rule.type, severity: '높음', location: match[0], suggestion: '삭제', reason: rule.reason });
    });
  });
  if (/(했다|하였다|한다|합니다|했습니다|입니다|된다|되었다)\.?$/.test(text.trim())) {
    violations.push({ type: '종결어미', severity: '중간', location: text.trim().split(/\s+/).slice(-4).join(' '), suggestion: '명사형 종결어미로 수정', reason: '모든 문장은 명사형 종결어미로 끝내야 함.' });
  }
  return violations;
}

function sanitizedText(text) {
  let output = text;
  FORBIDDEN_RULES.forEach((rule) => { output = output.replace(rule.regex, ''); });
  return output.replace(/하였다\.?$/g, '함.').replace(/했다\.?$/g, '함.').replace(/합니다\.?$/g, '함.').replace(/입니다\.?$/g, '임.');
}

function sentenceFromData(data) {
  const parts = Object.entries(data).map(([key, value]) => `${key}: ${value}`);
  const guidance = {
    자율활동: '활동 과정에서 역할 수행, 문제 해결, 공동체 기여가 드러남',
    동아리활동: '동아리 내 역할과 협업 과정에서의 구체적 기여가 드러남',
    진로활동: '진로 탐색 과정에서 비교와 상담 내용을 바탕으로 인식 변화가 드러남',
    세특: '수업 과제 수행 과정에서 학업 역량과 문제 해결 과정이 드러남',
    행발: '지속적으로 관찰된 행동을 통해 책임감과 공동체성이 확인됨',
  }[currentArea];
  return nominal(`${parts.join(' ')} ${guidance}`);
}

function trimToLimit(text, limit) {
  if (text.length <= limit) return text;
  return nominal(text.slice(0, Math.max(0, limit - 18)).trim());
}

function renderCharCounter(count, limit) {
  const pct = limit ? Math.min(100, (count / limit) * 100) : 0;
  const state = count > limit ? 'over' : pct >= 80 ? 'warn' : '';
  return `<div class="char-counter ${state}"><strong><span>글자수</span><span>${count} / ${limit}</span></strong><div class="track"><div class="bar" style="width:${pct}%"></div></div></div>`;
}

function renderWrite(data) {
  const limit = AREA_LIMITS[currentArea];
  const source = Object.values(data).join(' ');
  const violations = findViolations(source);
  const sentence = trimToLimit(sentenceFromData(Object.fromEntries(Object.entries(data).map(([key, value]) => [key, sanitizedText(value)]))), limit);
  latestText = sentence;
  resultEl.innerHTML = `
    <div class="result-card">
      <h3>✅ 생성 완료</h3>
      <div class="generated-text">${escapeHtml(sentence)}</div>
      ${renderCharCounter(sentence.length, limit)}
      <h3>제외된 항목</h3>
      <div class="badge-list">${violations.length ? violations.map((item) => `<span class="excluded-badge">🟡 ${escapeHtml(item.location)} → ${escapeHtml(item.reason)}</span>`).join('') : '<span class="excluded-badge">제외된 항목 없음</span>'}</div>
    </div>`;
}

function renderReview(text) {
  const limit = AREA_LIMITS[currentArea];
  const violations = findViolations(text);
  const fixed = trimToLimit(nominal(sanitizedText(text)), limit);
  latestText = fixed;
  resultEl.innerHTML = `
    <div class="result-card">
      <h3>🔍 검토 결과 ${violations.length + (text.length > limit ? 1 : 0)}건</h3>
      <div><h3>원문</h3><div class="original-text">${escapeHtml(text)}</div></div>
      <div><h3>위반 항목</h3>${violations.map((item) => `<article class="violation ${item.severity === '높음' ? 'high' : ''}"><b>${escapeHtml(item.type)} · ${escapeHtml(item.severity)}</b><br>원문위치: ${escapeHtml(item.location)}<br>수정제안: ${escapeHtml(item.suggestion)}<br>근거: ${escapeHtml(item.reason)}</article>`).join('') || '<p>자동 점검에서 발견된 위반사항이 없습니다.</p>'}${text.length > limit ? `<article class="violation"><b>글자수 · 중간</b><br>원문위치: ${text.length}자<br>수정제안: ${limit}자 이내로 압축<br>근거: 최대 글자 수 초과.</article>` : ''}</div>
      <div><h3>수정안</h3><div class="generated-text">${escapeHtml(fixed)}</div></div>
      ${renderCharCounter(text.length, limit)}
    </div>`;
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = collectFormData();
  if (currentMode === '검토') renderReview(data.기존작성문구 || '');
  else renderWrite(data);
});

document.querySelectorAll('[data-mode]').forEach((button) => {
  button.addEventListener('click', () => {
    currentMode = button.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach((item) => item.classList.toggle('is-active', item === button));
    resultEl.className = 'empty-result';
    resultEl.textContent = '영역별 입력 후 결과 생성을 누르면 작성 또는 검토 결과가 표시됩니다.';
    renderFields();
  });
});

document.querySelectorAll('[data-area]').forEach((button) => {
  button.addEventListener('click', () => {
    currentArea = button.dataset.area;
    document.querySelectorAll('[data-area]').forEach((item) => item.classList.toggle('is-active', item === button));
    resultEl.className = 'empty-result';
    resultEl.textContent = '영역별 입력 후 결과 생성을 누르면 작성 또는 검토 결과가 표시됩니다.';
    renderFields();
  });
});

copyButton.addEventListener('click', () => navigator.clipboard?.writeText(latestText));

uploadInput.addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch('/api/excel/upload', { method: 'POST', body: formData });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'saenggibu_results.xlsx';
  anchor.click();
  URL.revokeObjectURL(url);
});

renderFields();
