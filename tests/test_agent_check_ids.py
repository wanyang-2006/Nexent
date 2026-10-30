import json

import pytest

from agent.check_ids import check_text, extract_ids, final_answer_from_sse, main


def test_variable_width_and_embedded_identifiers():
    assert extract_ids("A12345 T123456 L-T123456 TK-v2-A00001 A0001 A0001") == {
        "accounts": ["A00001", "A0001", "A12345"],
        "transactions": ["T123456"],
        "chains": ["L-T123456"],
    }
    assert not any(extract_ids("XA0001 A0001x T12345z A123 T1234").values())
    assert extract_ids("L-T123456")["transactions"] == []


def test_real_chain_version_and_unknown_ids(real_data):
    result = check_text("A0209 T01908 L-T01908")
    assert result["status"] == "PASS"
    assert check_text("L-T01338", "v1")["unknown"]["chains"] == ["L-T01338"]
    assert check_text("L-T01338", "v2")["status"] == "PASS"
    result = check_text("A9999 T99999 L-T99999")
    assert result["unknown"] == {
        "accounts": ["A9999"], "transactions": ["T99999"], "chains": ["L-T99999"]
    }
    assert result["status"] == "FAIL"


def test_empty_and_nonexistent_account_reply(real_data):
    assert check_text("没有提供编号")["status"] == "NO_IDS"
    assert check_text("A9999 不存在，未生成工单")["status"] == "FAIL"


def test_sse_excludes_tool_output():
    stream = "\n".join("data: " + json.dumps(event) for event in [
        {"type": "execution_logs", "content": "A9999 T99999"},
        {"type": "final_answer", "content": "A0209"},
    ])
    assert final_answer_from_sse(stream) == "A0209"
    with pytest.raises(ValueError, match="no final_answer"):
        final_answer_from_sse('data: {"type":"tool"}')
    with pytest.raises(ValueError):
        final_answer_from_sse('data: invalid')


def test_cli_files_and_exit_codes(tmp_path, real_data, capsys):
    answer = tmp_path / "answer.md"
    answer.write_text("A0209 L-T01908", encoding="utf-8-sig")
    assert main([str(answer), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    answer.write_text("A9999", encoding="utf-8")
    assert main([str(answer)]) == 1
    answer.write_text("", encoding="utf-8")
    assert main([str(answer)]) == 2
    assert main([str(tmp_path / "missing")]) == 2
