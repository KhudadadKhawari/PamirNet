from unittest.mock import patch

from django.test import TestCase, override_settings


class ProductionHealthTests(TestCase):
    @override_settings(PAMIRNET_BUILD_SHA="test-build")
    def test_liveness_reports_build(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["build"], "test-build")

    @patch("core.views.Redis.from_url")
    def test_readiness_checks_database_and_redis(self, redis_from_url):
        redis_from_url.return_value.ping.return_value = True
        response = self.client.get("/api/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertTrue(response.json()["checks"]["database"])
        self.assertTrue(response.json()["checks"]["redis"])

    @patch("core.views.Redis.from_url")
    def test_readiness_fails_when_redis_is_unavailable(self, redis_from_url):
        redis_from_url.side_effect = OSError("redis down")
        response = self.client.get("/api/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertTrue(response.json()["checks"]["database"])
        self.assertFalse(response.json()["checks"]["redis"])
