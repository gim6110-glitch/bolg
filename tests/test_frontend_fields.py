from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_static_ui_has_fixed_2015_and_area_tabs():
    html = (ROOT / 'index.html').read_text()

    assert '2015개정 교육과정 3학년 고정' in html
    assert 'data-area="자율활동"' in html
    assert 'data-area="동아리활동"' in html
    assert 'data-area="진로활동"' in html
    assert 'data-area="세특"' in html
    assert 'data-area="행발"' in html
    assert 'id="curriculum"' not in html
    assert '엑셀 양식 다운로드' in html
    assert '엑셀 업로드·일괄처리' in html


def test_root_static_script_has_area_specific_fields():
    script = (ROOT / 'script.js').read_text()

    for label in ['학생특성', '활동 1', '결과물 1', '희망분야', '상담내용', '동아리명', '학생평가', '역할', '협업', '성장', '심화탐구', '과목명', '과제', '성취수준', '담임교사종합관찰']:
        assert label in script
    assert "options: ['상', '중상', '중', '중하', '하']" in script
    assert "자율·자치활동" not in script


def test_react_field_config_matches_requested_labels():
    prompts = (ROOT / 'frontend/src/prompts/index.js').read_text()

    assert "{ key: '자율활동'" in prompts
    assert "{ key: '동아리활동'" in prompts
    assert "{ key: '진로활동'" in prompts
    assert "{ key: '과목별 세부능력 및 특기사항'" in prompts
    assert "{ key: '행동특성 및 종합의견'" in prompts
    assert "label: '결과물'" not in prompts
    assert "label: '리더십공동체기여'" in prompts
