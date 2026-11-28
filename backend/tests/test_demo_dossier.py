"""Demo scenarios, the report dossier and the "new scam" loop users see."""

import pytest

from app.services.demo import DEMOS_LIST, SHARED_MULE


def _run(client, demo_id):
    started = client.post("/api/demo/start", params={"id": demo_id}).json()
    assert started["demo"]["id"] == demo_id
    cid = started["id"]
    for line in started["demo_lines"]:
        assert client.post(f"/api/conversations/{cid}/messages", json={"text": line}).status_code == 200
    return cid


@pytest.mark.parametrize("demo", DEMOS_LIST, ids=[d["id"] for d in DEMOS_LIST])
def test_each_demo_files_the_relation_it_promises(client, demo):
    cid = _run(client, demo["id"])
    outcome = client.post(f"/api/conversations/{cid}/extract").json()
    script = outcome["script"]
    assert script["status"] == "pending"
    if demo["kind"] == "new":
        assert script["relation"] == "new_root", (demo["id"], script.get("novelty_note"))
        assert not script["parent_id"]
    else:
        assert script["relation"] in {"duplicate", "variant"}
        assert demo["expected_script"] in {script.get("merge_target"), script.get("parent_id")}


def test_dossier_lists_confirmed_destination_and_digest(client):
    cid = _run(client, "moi-phat-nguoi-ong-sau")
    dossier = client.get(f"/api/conversations/{cid}/dossier").json()
    assert dossier["case_id"].startswith("HP-")
    values = {row["value"]: row for row in dossier["destinations"]}
    assert SHARED_MULE in values
    assert values[SHARED_MULE]["confirmed"] is True
    assert "Techcombank" in values[SHARED_MULE]["action"]
    assert any("0977001122" in value for value in values)
    assert any("csgt-phatnguoi.top" in url["value"] for url in dossier["contacts"]["urls"])
    assert len(dossier["integrity"]["transcript_digest"]) == 64
    assert dossier["timeline"][0]["role"] == "scammer"
    # The decoy's own fake profile is never listed as the scammer's account.
    started = client.get(f"/api/conversations/{cid}").json()
    assert started["persona"]["fake_profile"]["bank_account"] not in values


def test_shared_mule_links_two_stories(client):
    first = _run(client, "moi-phat-nguoi-ong-sau")
    second = _run(client, "moi-doi-bang-lai-khoa")
    for cid in (first, second):
        client.post(f"/api/conversations/{cid}/extract")
    rows = client.get("/api/intel/destinations").json()["items"]
    mule = next(row for row in rows if row["value"] == SHARED_MULE)
    assert mule["count"] == 2
    assert len(mule["stories"]) == 2
    assert rows[0]["value"] == SHARED_MULE
    dossier = client.get(f"/api/conversations/{second}/dossier").json()
    row = next(item for item in dossier["destinations"] if item["value"] == SHARED_MULE)
    assert row["seen_elsewhere"]
    csv = client.get("/api/intel/destinations", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert SHARED_MULE in csv.text


def test_published_new_scam_reaches_users_then_reset_clears_it(client):
    cid = _run(client, "moi-vac-xin-thu")
    script = client.post(f"/api/conversations/{cid}/extract").json()["script"]
    assert client.get("/api/library/fresh").json()["items"] == []
    assert client.post(f"/api/moderation/{script['id']}/approve").json()["status"] == "published"
    fresh = client.get("/api/library/fresh").json()["items"]
    assert [item["id"] for item in fresh] == [script["id"]]
    # Running the same scam again is now recognised instead of filed as new.
    again = _run(client, "moi-vac-xin-thu")
    second = client.post(f"/api/conversations/{again}/extract").json()["script"]
    assert second["relation"] in {"duplicate", "variant"}
    assert script["id"] in {second.get("merge_target"), second.get("parent_id")}
    reset = client.post("/api/demo/reset").json()
    assert reset["conversations"] == 2
    assert reset["scripts"] >= 2
    assert client.get("/api/library/fresh").json()["items"] == []
    assert client.get(f"/api/scripts/{script['id']}").status_code == 404


def test_new_scam_draft_reads_like_a_warning(client):
    cid = _run(client, "moi-phat-nguoi-ong-sau")
    script = client.post(f"/api/conversations/{cid}/extract").json()["script"]
    assert script["title"].startswith("Giả phòng CSGT: nộp phạt qua")
    assert "Kịch bản mới từ hội thoại" not in script["title"]
    assert script["red_flags"]
    assert "đường dẫn" in script["advice"]
    cid = _run(client, "moi-binh-chon-minh")
    script = client.post(f"/api/conversations/{cid}/extract").json()["script"]
    assert script["title"].startswith("Nhờ bình chọn qua đường dẫn")
    assert "mã xác nhận" in script["title"]


def test_checker_recognises_a_new_scam_once_published(client):
    message = "Phòng CSGT báo xe của anh có biên bản phạt nguội, vào csgt-phatnguoi.top nộp phạt trong hôm nay."
    before = client.post("/api/check", json={"text": message}).json()
    cid = _run(client, "moi-phat-nguoi-ong-sau")
    script = client.post(f"/api/conversations/{cid}/extract").json()["script"]
    client.post(f"/api/moderation/{script['id']}/approve")
    after = client.post("/api/check", json={"text": message}).json()
    assert (before.get("matched_script") or {}).get("id") != script["id"]
    assert after["matched_script"]["id"] == script["id"]
    client.post("/api/demo/reset")
