"""数据仓库：启动时把 data/ 下的两个 CSV 读入内存，按账户建好交易索引。

只读 data/，不读答案目录，也不 import 生成脚本（防泄题，见 Data and Rules/README.md）。
只用标准库，ECS 上不装 pandas 也能运行。
"""
from __future__ import annotations

import csv
import json
import os
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR_ENV = "FUNDTRACE_DATA_DIR"     # 可用环境变量改数据目录，如部署时挂载的只读卷

ACCOUNT_COLS = ["acct_id", "name", "acct_type", "open_date"]
TX_COLS = ["tx_id", "time", "from_acct", "to_acct", "amount", "tx_type"]
CASH = "CASH"                            # 现金出口，只会出现在提现交易的 to_acct


def default_data_dir() -> Path:
    return Path(os.environ.get(DATA_DIR_ENV) or ROOT / "data")


def _num(s: str):
    """金额：整数元保持 int，其余为 float。"""
    v = float(s)
    return int(v) if v.is_integer() else v


def _read_csv(path: Path, cols: list[str]) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in cols if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} 缺少列：{missing}")   # 多出的列直接忽略（兼容只增不改）
        return list(reader)


class Store:
    """不可变的数据快照。账户、交易的字典只读，调用方取用时请复制。"""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.accounts: dict[str, dict] = {}
        for r in _read_csv(self.data_dir / "accounts.csv", ACCOUNT_COLS):
            self.accounts[r["acct_id"]] = {c: r[c] for c in ACCOUNT_COLS}

        txs = []
        for r in _read_csv(self.data_dir / "transactions.csv", TX_COLS):
            t = {c: r[c] for c in TX_COLS}
            t["amount"] = _num(r["amount"])
            txs.append(t)
        txs.sort(key=lambda t: (t["time"], t["tx_id"]))
        self.transactions: list[dict] = txs
        self.tx_by_id: dict[str, dict] = {t["tx_id"]: t for t in txs}

        self.by_acct: dict[str, list[dict]] = defaultdict(list)   # 每个账户的全部交易，按 (time, tx_id) 升序
        for t in txs:
            self.by_acct[t["from_acct"]].append(t)
            if t["to_acct"] != t["from_acct"]:
                self.by_acct[t["to_acct"]].append(t)
        self.by_acct.pop(CASH, None)                              # CASH 不是账户

        meta_path = self.data_dir / "dataset_meta.json"
        self.meta: dict = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}

    @property
    def dataset_id(self) -> str | None:
        return self.meta.get("dataset_id")

    def has_account(self, acct_id: str) -> bool:
        return acct_id in self.accounts

    def account_txs(self, acct_id: str) -> list[dict]:
        return self.by_acct.get(acct_id, [])


_lock = threading.Lock()
_store: Store | None = None


def get_store() -> Store:
    """全局单例，第一次调用时加载。数据文件改动后需重启服务（或调用 reset_store）。"""
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = Store()
    return _store


def reset_store() -> None:
    """丢弃缓存，下一次 get_store() 重新加载。测试和换数据目录时使用。"""
    global _store
    with _lock:
        _store = None
