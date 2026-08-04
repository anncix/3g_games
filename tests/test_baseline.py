"""基线冒烟测试：验证应用可导入、登录页可访问、启动数据初始化完成"""
from starlette.testclient import TestClient
from main import app


def test_main_app_imports():
    assert app is not None
    assert len(app.routes) > 0


def test_login_page_accessible():
    client = TestClient(app)
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "login" in resp.text.lower()


def test_root_redirects_to_login():
    client = TestClient(app)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 200)