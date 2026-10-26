import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from auth import read_users, write_users
from test_support import TEST_EMAIL, TEST_HASH, TEST_PASSWORD


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("ports", "services"):
            (self.root / f"{name}.json").write_text("[]", encoding="utf-8")
        self.auth_root = self.root / "auth"
        self.users_path = self.auth_root / "users.json"
        write_users(self.users_path, [{"email": TEST_EMAIL, "passwordHash": TEST_HASH}])
        self.app = create_app(self.root, auth_root=self.auth_root)
        self.client = self.app.test_client()

    def token(self, client=None):
        client = client or self.client
        with client.session_transaction() as state:
            return state["csrf_token"]

    def login(self, client=None, email=TEST_EMAIL, password=TEST_PASSWORD):
        client = client or self.client
        client.get("/login")
        return client.post("/login", data={"email": email, "password": password, "csrf_token": self.token(client)})

    def change_password(self, **overrides):
        data = {
            "current_password": TEST_PASSWORD,
            "new_password": "changed-password-456",
            "confirm_password": "changed-password-456",
            "csrf_token": self.token(),
            **overrides,
        }
        return self.client.post("/profile", data=data)

    def test_all_dashboard_and_api_routes_require_login(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/profile").status_code, 302)
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith("/api/"):
                continue
            path = rule.rule.replace("<ship_id>", "unknown").replace("<service_id>", "unknown").replace("<proforma_id>", "unknown").replace("<port_id>", "unknown")
            for method in rule.methods - {"OPTIONS", "HEAD"}:
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.client.open(path, method=method).status_code, 401)

    def test_login_logout_and_csrf(self):
        self.assertEqual(self.client.post("/login", data={"email": TEST_EMAIL, "password": TEST_PASSWORD}).status_code, 400)
        self.assertEqual(self.login(password="incorrect").status_code, 401)
        self.assertEqual(self.login(email=TEST_EMAIL.upper()).status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/plan").status_code, 200)
        self.assertEqual(self.client.post("/api/fleet", json={}).status_code, 400)
        self.assertEqual(self.client.post("/logout").status_code, 400)
        self.assertEqual(self.client.post("/logout", data={"csrf_token": self.token()}).status_code, 302)
        self.assertEqual(self.client.get("/api/plan").status_code, 401)

    def test_anonymous_api_request_does_not_invalidate_open_login_form(self):
        self.client.get("/login")
        token = self.token()
        self.assertEqual(self.client.get("/api/plan").status_code, 401)
        self.assertEqual(self.token(), token)
        response = self.client.post("/login", data={"email": TEST_EMAIL, "password": TEST_PASSWORD, "csrf_token": token})
        self.assertEqual(response.status_code, 302)

    def test_auth_ui_has_profile_and_no_browser_toggle(self):
        self.login()
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/profile"', page)
        self.assertIn('action="/logout"', page)
        self.assertIn('name="csrf-token"', page)
        self.assertNotIn('id="import-browser"', page)
        self.assertNotIn("Headless:", page)
        self.assertNotIn(TEST_HASH, page)
        self.assertNotIn(TEST_PASSWORD, page)
        profile = self.client.get("/profile").get_data(as_text=True)
        self.assertIn('name="current_password"', profile)
        self.assertIn(TEST_EMAIL, profile)

    def test_password_change_persists_and_revokes_other_sessions(self):
        other = self.app.test_client()
        self.login()
        self.login(other)
        before = self.users_path.read_bytes()
        self.assertEqual(self.change_password().status_code, 302)
        self.assertNotEqual(self.users_path.read_bytes(), before)
        self.assertNotIn("changed-password-456", self.users_path.read_text(encoding="utf-8"))
        self.assertEqual(self.client.get("/api/plan").status_code, 200)
        self.assertEqual(other.get("/api/plan").status_code, 401)
        fresh = self.app.test_client()
        self.assertEqual(self.login(fresh).status_code, 401)
        self.assertEqual(self.login(fresh, password="changed-password-456").status_code, 302)
        restarted = create_app(self.root, auth_root=self.auth_root).test_client()
        self.assertEqual(self.login(restarted, password="changed-password-456").status_code, 302)

    def test_invalid_password_changes_preserve_file(self):
        self.login()
        before = self.users_path.read_bytes()
        for changes in (
            {"current_password": "incorrect"},
            {"new_password": "short", "confirm_password": "short"},
            {"confirm_password": "does-not-match"},
            {"new_password": TEST_PASSWORD, "confirm_password": TEST_PASSWORD},
            {"csrf_token": "invalid"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.change_password(**changes).status_code, 400)
                self.assertEqual(self.users_path.read_bytes(), before)

    def test_write_failure_is_reported_and_preserves_password(self):
        self.login()
        before = self.users_path.read_bytes()
        with patch("auth.os.replace", side_effect=OSError("Test write failure")):
            self.assertEqual(self.change_password().status_code, 503)
        self.assertEqual(self.users_path.read_bytes(), before)
        self.assertEqual(list(self.auth_root.glob("*.tmp")), [])
        self.assertEqual(self.client.get("/api/plan").status_code, 200)

    def test_external_json_additions_and_removals_apply_without_restart(self):
        users = read_users(self.users_path)
        users.append({"email": "second@example.test", "passwordHash": TEST_HASH})
        write_users(self.users_path, users)
        self.assertEqual(self.login(email="second@example.test").status_code, 302)
        write_users(self.users_path, users[:1])
        self.assertEqual(self.client.get("/api/plan").status_code, 401)

    def test_missing_or_invalid_user_file_fails_closed(self):
        self.login()
        self.users_path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.client.get("/api/plan").status_code, 503)
        self.users_path.unlink()
        self.assertEqual(self.client.get("/api/plan").status_code, 503)
        self.assertEqual(self.login().status_code, 503)

    def test_session_headers_and_persistent_signing_key(self):
        response = self.login()
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.app.secret_key, create_app(self.root, auth_root=self.auth_root).secret_key)
        with patch.dict("os.environ", {"PHOCA_HTTPS": "1"}):
            self.assertTrue(create_app(self.root, auth_root=self.auth_root).config["SESSION_COOKIE_SECURE"])

    def test_login_attempts_are_limited(self):
        for _ in range(10):
            self.assertEqual(self.login(password="wrong").status_code, 401)
        self.assertEqual(self.login().status_code, 429)

    def test_cli_creates_user_and_hash_without_plaintext_storage(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["create-user", "--email", "new@example.test"], input="new-password-123\nnew-password-123\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("new-password-123", self.users_path.read_text(encoding="utf-8"))
        self.assertEqual(self.login(email="new@example.test", password="new-password-123").status_code, 302)
        duplicate = runner.invoke(args=["create-user", "--email", TEST_EMAIL], input="new-password-123\nnew-password-123\n")
        self.assertNotEqual(duplicate.exit_code, 0)
        hashed = runner.invoke(args=["hash-password"], input="new-password-123\nnew-password-123\n")
        self.assertEqual(hashed.exit_code, 0, hashed.output)
        self.assertIn("scrypt:", hashed.output)

    def test_user_file_rejects_plain_passwords_and_duplicates(self):
        for users in (
            [{"email": TEST_EMAIL, "password": TEST_PASSWORD}],
            [{"email": TEST_EMAIL, "passwordHash": TEST_PASSWORD}],
            [{"email": TEST_EMAIL, "passwordHash": TEST_HASH}] * 2,
        ):
            self.users_path.write_text(json.dumps(users), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_users(self.users_path)


if __name__ == "__main__":
    unittest.main()
