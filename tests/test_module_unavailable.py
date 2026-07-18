"""ModuleUnavailableError parsing — the engine's module-outage 503 shapes."""
import json

from saebooks_desktop.services.api_client import (
    ModuleUnavailableError,
    _module_unavailable_from_503,
)


class TestModuleUnavailableParsing:
    def test_circuit_breaker_problem_json(self) -> None:
        body = json.dumps(
            {
                "type": "https://saebooks.io/problems/module_unavailable",
                "title": "Module Unavailable",
                "status": 503,
                "code": "module_unavailable",
                "detail": "The capture module is temporarily unavailable.",
                "module": "capture",
            }
        )
        err = _module_unavailable_from_503(body)
        assert isinstance(err, ModuleUnavailableError)
        assert err.module == "capture"
        assert err.status_code == 503

    def test_fail_closed_gate_plain_detail(self) -> None:
        body = json.dumps(
            {"detail": "capture module disabled: CAPTURE_TOKEN is not configured"}
        )
        err = _module_unavailable_from_503(body)
        assert isinstance(err, ModuleUnavailableError)
        assert err.module == "capture"

    def test_guarded_import_stub(self) -> None:
        body = json.dumps({"module": "billing.router", "status": "unavailable"})
        err = _module_unavailable_from_503(body)
        assert isinstance(err, ModuleUnavailableError)
        assert err.module == "billing"

    def test_other_503_is_not_module_outage(self) -> None:
        # Stripe-not-configured style 503 must stay a plain APIError.
        assert _module_unavailable_from_503(json.dumps({"detail": "Stripe not configured"})) is None
        assert _module_unavailable_from_503("Service Unavailable") is None
        assert _module_unavailable_from_503("") is None
