const AREA_LIMITS = {
  "자율·자치활동": 500,
  "자율활동": 500,
  "동아리활동": 500,
  "진로활동": 500,
  "과목별 세부능력 및 특기사항": 500,
  "행동특성 및 종합의견": 300,
};

const AREA_GUIDANCE = {
  "자율·자치활동": "활동 과정에서 드러난 책임감, 의견 조율, 행동 변화가 드러남.",
  "자율활동": "활동 과정에서 드러난 책임감, 의견 조율, 행동 변화가 드러남.",
  "동아리활동": "동아리 역할, 흥미, 역량, 태도의 변화가 드러남.",
  "진로활동": "진로 희망과 관련된 노력, 참여 태도, 상담 및 탐색 과정이 드러남.",
  "과목별 세부능력 및 특기사항": "수업과 수행평가에서 관찰된 성취 과정과 학습 변화가 드러남.",
  "행동특성 및 종합의견": "지속적으로 관찰된 행동특성과 성장 가능성이 드러남.",
};

const FORBIDDEN_PATTERNS = [
  { regex: /\b(TOEIC|TOEFL|TEPS|HSK|JPT|JLPT|DELF|DALF|TESTDAF|DSH|DSD|TORFL|DELE)\b|한자능력검정/gi, type: "금지어(가)", reason: "공인어학시험 참여 사실·성적·수상은 기재 불가." },
  { regex: /대회|수상|최우수상|우수상|장려상|입상|금상|은상|동상/g, type: "금지어(나)", reason: "교내·외 대회 참여·성적·수상 및 '대회' 표현은 수상경력 외 기재 불가." },
  { regex: /표창장|감사장|공로상/g, type: "금지어(다)", reason: "교외 기관·단체장이 수여한 상은 기재 불가." },
  { regex: /인증시험|자격증|한국사능력검정/g, type: "금지어(라)", reason: "교내·외 인증시험 참여 사실·성적은 기재 불가." },
  { regex: /모의고사|전국연합|원점수|석차|백분위|등급/g, type: "금지어(마)", reason: "모의고사·전국연합학력평가 성적은 기재 불가." },
  { regex: /논문|학회지|학회에서 발표|투고|등재/g, type: "금지어(바)", reason: "논문 투고·등재 또는 학회 발표 사실은 기재 불가." },
  { regex: /도서 출간|책을 출간|저서/g, type: "금지어(사)", reason: "도서 출간 사실은 기재 불가." },
  { regex: /특허|실용신안|상표|디자인권|지식재산권/g, type: "금지어(아)", reason: "지식재산권 출원·등록 사실은 기재 불가." },
  { regex: /해외|어학연수|국외|봉사활동을 다녀/g, type: "금지어(자)", reason: "어학연수·봉사 등 해외 활동실적은 기재 불가." },
  { regex: /아버지|어머니|부모|친인척|의사인|검사인|교수인|대표인/g, type: "금지어(차)", reason: "부모·친인척의 사회·경제적 지위 암시는 기재 불가." },
];

const PRIVACY_PATTERNS = [
  { regex: /\b\d{6,}\b/g, type: "개인정보", reason: "학번·주민등록번호 등으로 오인될 수 있는 6자리 이상 숫자 제거 필요." },
  { regex: /\b010[-\s]?\d{4}[-\s]?\d{4}\b/g, type: "개인정보", reason: "연락처는 출력에 포함할 수 없음." },
  { regex: /[가-힣]{2,4}\s?학생/g, type: "개인정보", reason: "학생 이름으로 보이는 표현은 제거 필요." },
];

const ENDING_PATTERN = /(했다|하였다|한다|합니다|했습니다|입니다|된다|되었다|이었다)\.?$/;

const form = document.querySelector("#record-form");
const modeEl = document.querySelector("#mode");
const curriculumEl = document.querySelector("#curriculum");
const areaEl = document.querySelector("#area");
const subjectEl = document.querySelector("#subject");
const subjectField = document.querySelector("#subject-field");
const contentEl = document.querySelector("#content");
const resultEl = document.querySelector("#result");
const charBadge = document.querySelector("#char-badge");
const sampleButton = document.querySelector("#sample-button");

function normalizeArea(curriculum, area) {
  if (curriculum === "2022개정" && area === "자율활동") return "자율·자치활동";
  if (curriculum === "2015개정" && area === "자율·자치활동") return "자율활동";
  return area;
}

function escapeHtml(value) {
  return value.replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

function compactWhitespace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function findViolations(text) {
  const violations = [];
  const allRules = [...FORBIDDEN_PATTERNS, ...PRIVACY_PATTERNS];
  allRules.forEach((rule) => {
    const matches = [...text.matchAll(rule.regex)];
    matches.forEach((match) => {
      violations.push({
        type: rule.type,
        severity: "높음",
        location: match[0],
        suggestion: "삭제",
        reason: rule.reason,
      });
    });
  });

  if (ENDING_PATTERN.test(text.trim())) {
    violations.push({
      type: "종결어미",
      severity: "중간",
      location: text.trim().split(/\s+/).slice(-4).join(" "),
      suggestion: "명사형 종결어미로 수정",
      reason: "모든 서술 문장은 '~함.', '~음.', '~임.', '~을 보임.'처럼 명사형 종결어미로 끝내야 함.",
    });
  }

  if (/[①②③④⑤]|\n\s*[-*]|\n\s*\d+\./.test(text)) {
    violations.push({
      type: "형식",
      severity: "중간",
      location: "번호 매기기 또는 문단 구분 기호",
      suggestion: "줄글로 정리",
      reason: "특수문자, 문단 구분 기호, 번호 매기기를 쓰지 않음.",
    });
  }

  return violations;
}

function sanitizeText(text) {
  let sanitized = text;
  [...FORBIDDEN_PATTERNS, ...PRIVACY_PATTERNS].forEach((rule) => {
    sanitized = sanitized.replace(rule.regex, "");
  });
  sanitized = sanitized
    .replace(/[①②③④⑤]/g, "")
    .replace(/\n\s*[-*]\s*/g, " ")
    .replace(/\n\s*\d+\.\s*/g, " ")
    .replace(/\b했다\.?$/g, "함.")
    .replace(/하였다\.?$/g, "함.")
    .replace(/합니다\.?$/g, "함.")
    .replace(/한다\.?$/g, "함.")
    .replace(/입니다\.?$/g, "임.");
  return compactWhitespace(sanitized);
}

function ensureNominalEnding(sentence) {
  const trimmed = sentence.replace(/[.。]+$/g, "").trim();
  if (!trimmed) return "관찰 내용이 부족하여 추가 기록이 필요함.";
  if (/(함|음|임|보임|나타냄|기여함)$/.test(trimmed)) return `${trimmed}.`;
  return `${trimmed}을 보임.`;
}

function trimToLimit(sentence, limit) {
  if (sentence.length <= limit) return sentence;
  const suffix = " 핵심 역량을 지속적으로 보임.";
  return `${sentence.slice(0, Math.max(0, limit - suffix.length)).trim()}${suffix}`;
}

function buildGeneratedSentence({ curriculum, area, subject, content }) {
  const normalizedArea = normalizeArea(curriculum, area);
  const clean = sanitizeText(content);
  const guidance = AREA_GUIDANCE[normalizedArea] || "학생의 개별적 특성과 성장 과정이 드러남.";
  const subjectPrefix = normalizedArea === "과목별 세부능력 및 특기사항" && subject ? `${subject} 수업에서 ` : "";
  const base = clean || "교사가 관찰한 구체적 활동 내용 보완이 필요함";
  return ensureNominalEnding(`${subjectPrefix}${base} ${guidance}`);
}

function renderMeta({ mode, curriculum, area, charCount, limit, over }) {
  return `
    <div class="meta-grid">
      <div class="meta"><strong>작업</strong>${mode}</div>
      <div class="meta"><strong>교육과정·영역</strong>${curriculum} · ${escapeHtml(area)}</div>
      <div class="meta"><strong>글자 수</strong>${charCount} / ${limit}${over ? " 초과" : ""}</div>
    </div>
  `;
}

function renderWriteResult(input) {
  const normalizedArea = normalizeArea(input.curriculum, input.area);
  const limit = AREA_LIMITS[normalizedArea];
  const violations = findViolations(input.content);
  const sentence = trimToLimit(buildGeneratedSentence(input), limit);
  const charCount = sentence.length;
  const over = charCount > limit;
  charBadge.textContent = `${charCount}/${limit}자`;
  charBadge.classList.toggle("is-over", over);

  const excluded = violations.filter((item) => item.severity === "높음");
  resultEl.innerHTML = `
    <div class="result-card">
      ${renderMeta({ mode: "작성", curriculum: input.curriculum, area: normalizedArea, charCount, limit, over })}
      <div>
        <h3>생성문장</h3>
        <div class="output-sentence">${escapeHtml(sentence)}</div>
      </div>
      <div>
        <h3>제외한 항목</h3>
        ${excluded.length ? `<ul class="list">${excluded.map((item) => `<li>${escapeHtml(item.location)}: ${escapeHtml(item.reason)}</li>`).join("")}</ul>` : "<p>제외한 금지 항목이 없습니다.</p>"}
      </div>
      <div class="checks">
        <span class="check ${excluded.length ? "fail" : ""}">금지어 ${excluded.length ? "제외됨" : "없음"}</span>
        <span class="check">명사형 종결</span>
        <span class="check">개인정보 제거</span>
        <span class="check ${over ? "fail" : ""}">글자 수 ${over ? "초과" : "적합"}</span>
      </div>
    </div>
  `;
}

function severityClass(severity) {
  return severity === "높음" ? "high" : severity === "중간" ? "medium" : "low";
}

function renderReviewResult(input) {
  const normalizedArea = normalizeArea(input.curriculum, input.area);
  const limit = AREA_LIMITS[normalizedArea];
  const violations = findViolations(input.content);
  const corrected = trimToLimit(ensureNominalEnding(sanitizeText(input.content)), limit);
  const charCount = input.content.length;
  const over = charCount > limit;
  charBadge.textContent = `${charCount}/${limit}자`;
  charBadge.classList.toggle("is-over", over);

  const allViolations = [...violations];
  if (over) {
    allViolations.push({
      type: "글자수",
      severity: "중간",
      location: `${charCount}자`,
      suggestion: `${limit}자 이내로 압축`,
      reason: `해당 영역의 최대 글자 수 ${limit}자를 초과함.`,
    });
  }

  resultEl.innerHTML = `
    <div class="result-card">
      ${renderMeta({ mode: "검토", curriculum: input.curriculum, area: normalizedArea, charCount, limit, over })}
      <div>
        <h3>위반사항</h3>
        ${allViolations.length ? allViolations.map((item) => `
          <div class="violation ${severityClass(item.severity)}">
            <strong>${escapeHtml(item.type)} · ${escapeHtml(item.severity)}</strong><br />
            원문 위치: ${escapeHtml(item.location)}<br />
            수정 제안: ${escapeHtml(item.suggestion)}<br />
            근거: ${escapeHtml(item.reason)}
          </div>`).join("") : "<p>자동 점검에서 발견된 위반사항이 없습니다.</p>"}
      </div>
      <div>
        <h3>수정안</h3>
        <div class="output-sentence">${escapeHtml(corrected)}</div>
      </div>
      <p><strong>종합의견</strong> ${allViolations.length ? "위반 가능성이 있는 표현을 삭제 또는 명사형 종결로 정리함." : "현재 문구는 주요 자동 점검 기준을 충족함."}</p>
    </div>
  `;
}

function getInput() {
  return {
    mode: modeEl.value,
    curriculum: curriculumEl.value,
    area: areaEl.value,
    subject: compactWhitespace(subjectEl.value),
    content: compactWhitespace(contentEl.value),
  };
}

function updateSubjectVisibility() {
  subjectField.style.display = areaEl.value === "과목별 세부능력 및 특기사항" ? "grid" : "none";
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const input = getInput();
  if (!input.content) {
    resultEl.innerHTML = '<div class="result-empty">학생 활동 내용 또는 기존 작성 문구를 먼저 입력하세요.</div>';
    charBadge.textContent = "0자";
    charBadge.classList.remove("is-over");
    return;
  }
  if (input.mode === "작성") renderWriteResult(input);
  else renderReviewResult(input);
});

form.addEventListener("reset", () => {
  setTimeout(() => {
    resultEl.innerHTML = '<div class="result-empty">입력 후 결과 생성을 누르면 작성 또는 검토 결과가 표시됩니다.</div>';
    charBadge.textContent = "0자";
    charBadge.classList.remove("is-over");
    updateSubjectVisibility();
  });
});

areaEl.addEventListener("change", updateSubjectVisibility);

sampleButton.addEventListener("click", () => {
  modeEl.value = "검토";
  curriculumEl.value = "2022개정";
  areaEl.value = "진로활동";
  contentEl.value = "김민준 학생은 교내 진로탐색대회에서 최우수상을 수상했고 TOEIC 900점을 받았다. 의사인 아버지의 조언을 바탕으로 해외 봉사활동을 다녀왔습니다.";
  updateSubjectVisibility();
});

updateSubjectVisibility();
