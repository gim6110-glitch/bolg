import json
import subprocess
import sys

import main


def test_build_prompt_uses_2022_branch_and_normalizes_area():
    system, user = main.build_prompt(
        main.PromptInput(
            curriculum="2022개정",
            area="자율활동",
            content="학급 회의에서 의견을 조율함.",
        ),
        "작성",
    )

    assert "2022 개정 교육과정" in system
    assert "'자율활동'이 아니라 '자율·자치활동'" in system
    assert "[영역] 자율·자치활동" in system
    assert "교사 관찰 메모" in user
    assert "학급 회의에서 의견을 조율함." in user
    assert '"mode": "작성"' in user


def test_build_prompt_uses_2015_branch_and_review_schema():
    system, user = main.build_prompt(
        main.PromptInput(
            curriculum="2015개정",
            area="자율·자치활동",
            content="발표를 잘 하였다.",
        ),
        "검토",
    )

    assert "2015 개정 교육과정" in system
    assert "'자율·자치활동'이 아니라 '자율활동'" in system
    assert "기존 작성 문구" in user
    assert "발표를 잘 하였다." in user
    assert '"mode": "검토"' in user
    assert "위반사항" in user


def test_subject_and_max_chars_are_reflected():
    system, _ = main.build_prompt(
        main.PromptInput(
            curriculum="2022개정",
            area="과목별 세부능력 및 특기사항",
            content="자료를 분석함.",
            subject="통합사회",
        ),
        "작성",
    )

    assert "[과목명] 통합사회" in system
    assert main.get_max_chars("2022개정", "행동특성 및 종합의견") == 300
    assert main.get_max_chars("2022개정", "진로활동") == 500


def test_cli_outputs_json_prompt():
    completed = subprocess.run(
        [
            sys.executable,
            "main.py",
            "--curriculum",
            "2022개정",
            "--area",
            "진로활동",
            "--mode",
            "작성",
            "--content",
            "진로탐색 중임.",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(completed.stdout)
    assert set(payload) == {"system", "user"}
    assert "진로활동" in payload["system"]
    assert "진로탐색 중임." in payload["user"]
