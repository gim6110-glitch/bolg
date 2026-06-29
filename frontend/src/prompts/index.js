export const AREAS = [
  { key: '자율활동', short: '자율', max: 500 },
  { key: '동아리활동', short: '동아리', max: 500 },
  { key: '진로활동', short: '진로', max: 500 },
  { key: '과목별 세부능력 및 특기사항', short: '세특', max: 500 },
  { key: '행동특성 및 종합의견', short: '행발', max: 300 },
];

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export const FIELD_CONFIG = {
  자율활동: [
    { name: '학생특성', label: '학생특성', type: 'textarea', required: false },
    { name: '활동1', label: '활동 1', type: 'textarea', required: true },
    { name: '결과물1', label: '결과물 1', type: 'textarea', required: false },
    { name: '활동2', label: '활동 2', type: 'textarea', required: false },
    { name: '결과물2', label: '결과물 2', type: 'textarea', required: false },
    { name: '활동3', label: '활동 3', type: 'textarea', required: false },
    { name: '결과물3', label: '결과물 3', type: 'textarea', required: false },
  ],
  동아리활동: [
    { name: '동아리명', label: '동아리명', type: 'text', required: true },
    { name: '학생평가', label: '학생평가', type: 'textarea', required: true },
    { name: '역할', label: '역할', type: 'textarea', required: false },
    { name: '협업', label: '협업', type: 'textarea', required: false },
    { name: '성장', label: '성장', type: 'textarea', required: false },
    { name: '심화탐구', label: '심화탐구', type: 'textarea', required: false },
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
    { name: '상담내용', label: '상담내용', type: 'textarea', required: false },
  ],
  '과목별 세부능력 및 특기사항': [
    { name: '과목명', label: '과목명', type: 'text', required: true },
    { name: '과제', label: '과제', type: 'textarea', required: true },
    { name: '학생평가', label: '학생평가', type: 'textarea', required: true },
    { name: '성취수준', label: '성취수준', type: 'select', required: true, options: ['상', '중상', '중', '중하', '하'] },
  ],
  '행동특성 및 종합의견': [
    { name: '지속행동', label: '지속적으로 관찰된 행동', type: 'textarea', required: false },
    { name: '리더십공동체', label: '리더십 및 공동체 기여', type: 'textarea', required: false },
    { name: '나눔배려협업', label: '나눔·배려·협업 행동', type: 'textarea', required: false },
    { name: '자기주도책임', label: '자기주도성 및 책임감', type: 'textarea', required: false },
    { name: '학습탐구', label: '학습과 탐구 행동', type: 'textarea', required: false },
    { name: '변화성장', label: '변화 및 성장', type: 'textarea', required: false },
    { name: '담임종합관찰', label: '담임교사 종합 관찰', type: 'textarea', required: true },
  ],
};
