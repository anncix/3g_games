"""Smoke test: log in as demo and exercise all fengyun routes."""
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    # login as demo via JSON endpoint
    r = client.post("/login", json={"username": "demo", "password": "demo123"},
                    headers={"accept": "application/json"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    client.cookies.set("qq_home_token", token)

    GETS = [
        "/games/fengyun",
        "/games/fengyun/create",
        "/games/fengyun/skills",
        "/games/fengyun/equip",
        "/games/fengyun/shop",
        "/games/fengyun/dungeons",
        "/games/fengyun/legion",
        "/games/fengyun/titles",
        "/games/fengyun/achievements",
        "/games/fengyun/training",
        "/games/fengyun/rules",
    ]
    for url in GETS:
        r = client.get(url, follow_redirects=False)
        status = "OK" if r.status_code == 200 else ("REDIR" if r.status_code in (303, 307) else "FAIL")
        print(f"GET {url:42s} -> {r.status_code} {status}")
        assert r.status_code == 200, f"{url} returned {r.status_code}: {r.text[:200]}"

    # POST create (pick assassin/wu)
    r = client.post("/games/fengyun/create",
                    data={"class_key": "assassin", "faction": "wu"},
                    follow_redirects=False)
    print(f"POST /create -> {r.status_code} {'REDIR-OK' if r.status_code == 303 else 'FAIL'}")
    assert r.status_code == 303

    # follow to home
    r = client.get("/games/fengyun")
    print(f"GET home after create -> {r.status_code}, has '刺客' class: {'刺客' in r.text}")
    assert r.status_code == 200 and "刺客" in r.text

    # learn the first skill (unlock level 1, sk_a_a1 影遁). Fresh user has 0 exp,
    # so this may legitimately fail with "经验不足" — either way the result page must render (200).
    r = client.post("/games/fengyun/skills/learn/sk_a_a1", follow_redirects=False)
    msg_ok = ("学会" in r.text) or ("不足" in r.text) or ("已学习" in r.text)
    print(f"POST learn skill -> {r.status_code} {'OK' if r.status_code == 200 and msg_ok else 'FAIL'}")
    assert r.status_code == 200 and msg_ok

    # start training
    r = client.post("/games/fengyun/training/start", follow_redirects=False)
    print(f"POST training start -> {r.status_code} {'OK' if r.status_code == 200 else 'FAIL'}")
    assert r.status_code == 200 and "开始演武" in r.text

    # buy first shop equip (assassin, level 1 -> can afford low tier)
    # find a cheap 普通 头 lvl10 equip
    r = client.get("/games/fengyun/shop")
    assert r.status_code == 200
    # buy fy_eq_pt_tou_10 (普通头, lvl10 req, price low)
    r = client.post("/games/fengyun/shop/buy/fy_eq_pt_tou_10", follow_redirects=False)
    print(f"POST shop buy -> {r.status_code} {'OK' if r.status_code == 200 else 'FAIL'}")
    assert r.status_code == 200

    # wear it
    r = client.get("/games/fengyun/equip")
    assert r.status_code == 200

    # try dungeon challenge (level too low for most; should get 等级不足 result, still 200)
    r = client.post("/games/fengyun/dungeon/dg_shu_huoshaobowang", follow_redirects=False)
    print(f"POST dungeon (low lvl) -> {r.status_code} {'OK' if r.status_code == 200 else 'FAIL'}")
    assert r.status_code == 200

    # legion create should fail (level<15) but return 200 result page
    r = client.post("/games/fengyun/legion/create", data={"name": "测试军团"},
                    follow_redirects=False)
    print(f"POST legion create (lvl<15) -> {r.status_code} {'OK' if r.status_code == 200 else 'FAIL'}")
    assert r.status_code == 200

    print("\nALL SMOKE TESTS PASSED")
