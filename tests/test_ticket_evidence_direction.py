from core import api
from core.store import get_store


def test_third_party_support_explicitly_names_real_payer(real_data):
    ticket = api.make_ticket("A0209", "v1")
    store = get_store()
    third_party = []
    for evidence in ticket["supporting_evidence"]:
        tx = store.tx_by_id[evidence["tx_id"]]
        if "A0209" not in (tx["from_acct"], tx["to_acct"]):
            third_party.append(evidence)
            assert tx["from_acct"] in evidence["desc"]
            assert tx["to_acct"] in evidence["desc"]
            assert "链上其他账户交易" in evidence["desc"]
    assert third_party
