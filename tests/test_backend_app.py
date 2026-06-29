import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND = os.path.join(ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from prompts.builder import build_review_prompt, build_write_prompt, get_max_chars, normalize_area


def test_prompt_builder_is_2015_curriculum_and_area_specific():
    system, user = build_write_prompt('세특', {'과목명': '기계일반', '과제': '도면 해석'})

    assert normalize_area('세특') == '과목별 세부능력 및 특기사항'
    assert '2015 개정 교육과정' in system
    assert '2022 개정 영역명으로 바꾸지 않음' in system
    assert '공백 포함 300~350자' in system
    assert '"과목명": "기계일반"' in user
    assert get_max_chars('행발') == 300


def test_review_prompt_contains_checklist_and_schema():
    system, user = build_review_prompt('진로활동', '진로탐색대회에서 수상하였다.')

    assert '검토 체크리스트' in system
    assert '대학명·기관명·기업명·강사명' in system
    assert '기존 작성 문구' in user
    assert '위반사항' in user
    assert '최대글자수: 500' in user


def test_personal_info_masking_and_similarity_when_dependencies_available():
    pytest.importorskip('anthropic')
    from services import find_local_similarities, mask_personal_info

    masked, detected = mask_personal_info('홍길동 12번 010-1234-5678')

    assert detected is True
    assert '[개인정보 제거]' in masked

    result = find_local_similarities([
        {'식별자': '1', '문장': '자료를 비교 분석하며 문제 해결 과정을 구체화함.'},
        {'식별자': '2', '문장': '자료를 비교 분석하며 문제 해결 과정을 정리함.'},
    ])
    assert result['이상없음'] is False
    assert result['유사쌍'][0]['유사구절']


def test_excel_template_structure_when_dependencies_available():
    pytest.importorskip('openpyxl')
    from io import BytesIO
    from openpyxl import load_workbook
    from routers.excel import build_template_workbook

    wb = build_template_workbook()
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    loaded = load_workbook(stream, data_only=False)

    assert loaded.sheetnames == ['사용안내', '작성용', '검토용']
    assert loaded['작성용']['A2'].value == '연번'
    assert loaded['검토용']['E3'].value == '=IF(D3="","",LEN(D3))'
    assert loaded['작성용'].freeze_panes == 'A3'
