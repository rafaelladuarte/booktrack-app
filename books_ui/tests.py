from unittest.mock import MagicMock, patch

import httpx
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .api_client import api_request


def fake_response(status=200, payload=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {}
    return resp


class ApiClientTests(TestCase):
    def make_request(self, **session):
        request = RequestFactory().get("/")
        request.session = MagicMock()
        store = dict(session)
        request.session.get.side_effect = store.get
        request.session.__setitem__.side_effect = store.__setitem__
        request._store = store
        return request

    @patch("books_ui.api_client.httpx.request")
    def test_injects_bearer_token(self, mock_req):
        mock_req.return_value = fake_response(200)
        request = self.make_request(access_token="abc")
        api_request(request, "GET", "/books")
        headers = mock_req.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer abc")

    @patch("books_ui.api_client.httpx.request")
    def test_normalizes_endpoint_without_leading_slash(self, mock_req):
        mock_req.return_value = fake_response(200)
        api_request(self.make_request(), "GET", "books")
        url = mock_req.call_args.args[1]
        self.assertTrue(url.endswith("/books"))
        self.assertNotIn("//books", url)

    @patch("books_ui.api_client.httpx.post")
    @patch("books_ui.api_client.httpx.request")
    def test_refreshes_token_on_401_and_retries(self, mock_req, mock_post):
        mock_req.side_effect = [fake_response(401), fake_response(200)]
        mock_post.return_value = fake_response(
            200, {"access_token": "new", "refresh_token": "newref"}
        )
        request = self.make_request(access_token="old", refresh_token="ref")
        resp = api_request(request, "GET", "/books")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(request._store["access_token"], "new")
        self.assertEqual(request._store["refresh_token"], "newref")
        self.assertEqual(mock_req.call_count, 2)

    @patch("books_ui.api_client.httpx.post")
    @patch("books_ui.api_client.httpx.request")
    def test_flushes_session_when_refresh_fails(self, mock_req, mock_post):
        mock_req.return_value = fake_response(401)
        mock_post.return_value = fake_response(401)
        request = self.make_request(access_token="old", refresh_token="ref")
        resp = api_request(request, "GET", "/books")
        self.assertEqual(resp.status_code, 401)
        request.session.flush.assert_called_once()

    @patch("books_ui.api_client.httpx.request")
    def test_flushes_session_on_401_without_refresh_token(self, mock_req):
        mock_req.return_value = fake_response(401)
        request = self.make_request(access_token="old")
        api_request(request, "GET", "/books")
        request.session.flush.assert_called_once()

    @patch("books_ui.api_client.httpx.request")
    def test_propagates_network_errors(self, mock_req):
        mock_req.side_effect = httpx.ConnectError("boom")
        with self.assertRaises(httpx.RequestError):
            api_request(self.make_request(), "GET", "/books")


class AuthViewTests(TestCase):
    def test_login_page_renders(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)

    @patch("books_ui.views.httpx.post")
    def test_login_success_stores_tokens_and_redirects(self, mock_post):
        mock_post.return_value = fake_response(
            200, {"access_token": "a", "refresh_token": "r"}
        )
        resp = self.client.post(reverse("login"), {"username": "u", "password": "p"})
        self.assertRedirects(resp, reverse("library"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["access_token"], "a")

    @patch("books_ui.views.httpx.post")
    def test_login_failure_shows_error(self, mock_post):
        mock_post.return_value = fake_response(401)
        resp = self.client.post(reverse("login"), {"username": "u", "password": "x"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "incorretos")

    @patch("books_ui.views.httpx.post")
    def test_login_api_down_shows_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("down")
        resp = self.client.post(reverse("login"), {"username": "u", "password": "p"})
        self.assertContains(resp, "Erro ao conectar")

    def test_logout_clears_session_and_redirects(self):
        session = self.client.session
        session["access_token"] = "a"
        session.save()
        resp = self.client.get(reverse("logout"))
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)


class ProtectedViewTests(TestCase):
    def test_library_requires_login(self):
        resp = self.client.get(reverse("library"))
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)

    def test_book_detail_requires_login(self):
        resp = self.client.get(reverse("book_detail", args=[1]))
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)

    def test_delete_book_get_does_not_call_api(self):
        with patch("books_ui.views.api_request") as mock_api:
            resp = self.client.get(reverse("delete_book", args=[1]))
        mock_api.assert_not_called()
        self.assertEqual(resp.status_code, 302)
