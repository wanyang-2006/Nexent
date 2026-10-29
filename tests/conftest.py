import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = ROOT / "Data and Rules"
EXAMPLE_DATA = SPEC / "examples" / "data"
FIXTURES = SPEC / "examples" / "fixtures"


@pytest.fixture(scope="session")
def validator():
    """按函数名取 schema 校验器：validator('get_account').validate(obj)。"""
    schemas = {p.name.replace(".schema.json", ""): json.loads(p.read_text(encoding="utf-8"))
               for p in (SPEC / "schemas").glob("*.schema.json")}
    registry = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])
    return lambda name: Draft202012Validator(schemas[name], registry=registry)


@pytest.fixture(autouse=True)
def _tickets_to_tmp(monkeypatch, tmp_path):
    """make_ticket 会落盘；测试中一律写到临时目录，避免样例数据的工单写进 tickets/。"""
    monkeypatch.setenv("FUNDTRACE_TICKET_DIR", str(tmp_path / "tickets"))


@pytest.fixture
def real_data(monkeypatch):
    """使用正式数据 data/。"""
    from core import store
    monkeypatch.delenv(store.DATA_DIR_ENV, raising=False)
    store.reset_store()
    yield store.get_store()
    store.reset_store()


@pytest.fixture
def example_data(monkeypatch):
    """使用规范自带的 10 账户样例数据（与 fixtures 自洽）。"""
    from core import store
    monkeypatch.setenv(store.DATA_DIR_ENV, str(EXAMPLE_DATA))
    store.reset_store()
    yield store.get_store()
    store.reset_store()
