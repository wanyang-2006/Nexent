import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "multimodal/schemas/receipt.schema.json")
    .read_text(encoding="utf-8")
)


@pytest.mark.parametrize("currency", [None, "CNY", "USD"])
def test_currency_can_represent_unknown_or_explicit_code(currency):
    receipt = {
        "doc_type": "其他", "payee_name": None, "payee_account_tail": None,
        "payee_type": None, "amount": None, "time": None, "channel": None,
        "remark": None, "unreadable_fields": [], "currency": currency,
    }
    Draft202012Validator(SCHEMA).validate(receipt)


def test_currency_does_not_default_to_a_guessed_value():
    assert "default" not in SCHEMA["properties"]["currency"]
    assert not Draft202012Validator(SCHEMA["properties"]["currency"]).is_valid(42)
    assert not Draft202012Validator(SCHEMA["properties"]["currency"]).is_valid("")
