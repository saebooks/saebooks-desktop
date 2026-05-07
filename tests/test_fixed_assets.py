"""Tests for fixed assets service and views — offscreen Qt, mocked API.

Covers:
  - saebooks_desktop.services.fixed_assets (unit tests via APIClient mock)
  - saebooks_desktop.views.fixed_assets.FixedAssetsView (list view)
  - saebooks_desktop.views.fixed_assets.FixedAssetDetail (detail view)
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_UUID_MODEL = "m0000000-0000-0000-0000-000000000001"

_SAMPLE_ASSETS = [
    {
        "id": "fa-001",
        "name": "Laser Cutter",
        "code": "FA-0001",
        "purchase_date": "2023-01-15",
        "purchase_price": "15000.00",
        "net_book_value": "12000.00",
        "status": "active",
        "depreciation_model_id": _UUID_MODEL,
    },
    {
        "id": "fa-002",
        "name": "CNC Router",
        "code": "FA-0002",
        "purchase_date": "2022-06-01",
        "purchase_price": "8000.00",
        "net_book_value": "0.00",
        "status": "disposed",
        "depreciation_model_id": _UUID_MODEL,
    },
    {
        "id": "fa-003",
        "name": "Work Vehicle",
        "code": "FA-0003",
        "purchase_date": "2024-03-10",
        "purchase_price": "45000.00",
        "net_book_value": "43000.00",
        "status": "active",
        "depreciation_model_id": _UUID_MODEL,
    },
]

_SAMPLE_ASSET_DETAIL = {
    "id": "fa-001",
    "name": "Laser Cutter",
    "code": "FA-0001",
    "purchase_date": "2023-01-15",
    "purchase_price": "15000.00",
    "net_book_value": "12000.00",
    "status": "active",
    "depreciation_model_id": _UUID_MODEL,
    "depreciation_runs": [
        {
            "period_date": "2023-12-31",
            "depreciation_amount": "1500.00",
            "nbv_after": "13500.00",
        },
        {
            "period_date": "2024-12-31",
            "depreciation_amount": "1500.00",
            "nbv_after": "12000.00",
        },
    ],
}

_SAMPLE_ASSET_DISPOSED = {
    "id": "fa-002",
    "name": "CNC Router",
    "code": "FA-0002",
    "purchase_date": "2022-06-01",
    "purchase_price": "8000.00",
    "net_book_value": "0.00",
    "status": "disposed",
    "depreciation_model_id": _UUID_MODEL,
    "depreciation_runs": [],
}


# ===========================================================================
# Service layer tests
# ===========================================================================


class TestListFixedAssetsService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import list_fixed_assets

        client = MagicMock()
        client.get.return_value = {"items": _SAMPLE_ASSETS}
        result = list_fixed_assets(client)
        client.get.assert_called_once_with(
            "/api/v1/fixed_assets", params={"page": 1, "page_size": 50}
        )
        assert result == _SAMPLE_ASSETS

    def test_status_filter_added_to_params(self) -> None:
        from saebooks_desktop.services.fixed_assets import list_fixed_assets

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_fixed_assets(client, status_filter="active")
        call_params = client.get.call_args[1]["params"]
        assert call_params["status"] == "active"

    def test_status_filter_none_not_in_params(self) -> None:
        from saebooks_desktop.services.fixed_assets import list_fixed_assets

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_fixed_assets(client, status_filter=None)
        call_params = client.get.call_args[1]["params"]
        assert "status" not in call_params

    def test_returns_empty_list_when_no_items(self) -> None:
        from saebooks_desktop.services.fixed_assets import list_fixed_assets

        client = MagicMock()
        client.get.return_value = {}
        assert list_fixed_assets(client) == []


class TestGetFixedAssetService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import get_fixed_asset

        client = MagicMock()
        client.get.return_value = _SAMPLE_ASSET_DETAIL
        result = get_fixed_asset(client, "fa-001")
        client.get.assert_called_once_with("/api/v1/fixed_assets/fa-001")
        assert result == _SAMPLE_ASSET_DETAIL


class TestCreateFixedAssetService:
    def test_calls_post_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import create_fixed_asset

        client = MagicMock()
        client.post.return_value = {"id": "fa-new"}
        data = {"name": "Welder", "purchase_price": "2500.00"}
        result = create_fixed_asset(client, data)
        client.post.assert_called_once_with("/api/v1/fixed_assets", json=data)
        assert result == {"id": "fa-new"}


class TestUpdateFixedAssetService:
    def test_calls_patch_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import update_fixed_asset

        client = MagicMock()
        client.patch.return_value = (200, {"id": "fa-001"})
        status, result = update_fixed_asset(client, "fa-001", {"name": "Updated"})
        client.patch.assert_called_once_with(
            "/api/v1/fixed_assets/fa-001", json={"name": "Updated"}
        )
        assert status == 200


class TestRunDepreciationService:
    def test_calls_depreciate_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import run_depreciation

        client = MagicMock()
        client.post.return_value = _SAMPLE_ASSET_DETAIL
        result = run_depreciation(client, "fa-001")
        client.post.assert_called_once_with(
            "/api/v1/fixed_assets/fa-001/depreciate", json={}
        )

    def test_passes_data_to_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import run_depreciation

        client = MagicMock()
        client.post.return_value = _SAMPLE_ASSET_DETAIL
        run_depreciation(client, "fa-001", {"period_date": "2024-12-31"})
        call_kwargs = client.post.call_args[1]
        assert call_kwargs["json"] == {"period_date": "2024-12-31"}


class TestDisposeAssetService:
    def test_calls_dispose_endpoint(self) -> None:
        from saebooks_desktop.services.fixed_assets import dispose_asset

        client = MagicMock()
        client.post.return_value = _SAMPLE_ASSET_DISPOSED
        data = {"disposal_type": "sale", "disposal_date": "2024-06-01", "sale_price": "500.00"}
        result = dispose_asset(client, "fa-002", data)
        client.post.assert_called_once_with(
            "/api/v1/fixed_assets/fa-002/dispose", json=data
        )
        assert result == _SAMPLE_ASSET_DISPOSED


# ===========================================================================
# FixedAssetsView (list view) tests
# ===========================================================================


def _make_assets_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.fixed_assets import FixedAssetsView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.fixed_assets.list_fixed_assets",
            side_effect=side_effect,
        ):
            return FixedAssetsView()
    else:
        with patch(
            "saebooks_desktop.views.fixed_assets.list_fixed_assets",
            return_value=items if items is not None else [],
        ):
            return FixedAssetsView()


class TestFixedAssetsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_assets_view(qapp, items=[])
        assert view is not None

    def test_has_six_columns(self, qapp) -> None:
        view = _make_assets_view(qapp, items=[])
        assert view._model.columnCount() == 6

    def test_column_headers(self, qapp) -> None:
        expected = ["Name", "Code", "Purchase Date", "Purchase Price", "Net Book Value", "Status"]
        view = _make_assets_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected

    def test_has_new_asset_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_assets_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Asset"

    def test_has_status_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        view = _make_assets_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        view = _make_assets_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Active", "Disposed"]


class TestFixedAssetsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._model.rowCount() == 3

    def test_name_column_populated(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._model.item(0, 0).text() == "Laser Cutter"

    def test_code_column_populated(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._model.item(0, 1).text() == "FA-0001"

    def test_purchase_date_column(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._model.item(0, 2).text() == "2023-01-15"

    def test_status_column(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._model.item(0, 5).text() == "active"
        assert view._model.item(1, 5).text() == "disposed"

    def test_asset_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "fa-001"

    def test_purchase_price_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        item = view._model.item(0, 3)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_assets_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestFixedAssetsViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_assets_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_on_success(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert view._offline_label.isHidden()


class TestFixedAssetsViewDoubleClick:
    def test_double_click_emits_asset_selected(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        received: list[str] = []
        view.asset_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["fa-001"]

    def test_new_asset_signal_emitted(self, qapp) -> None:
        view = _make_assets_view(qapp, items=[])
        triggered = []
        view.new_asset_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()
        assert triggered == [True]


class TestFixedAssetsViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_assets_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        view = _make_assets_view(qapp, items=_SAMPLE_ASSETS)
        assert not view._load_more_btn.isEnabled()


# ===========================================================================
# FixedAssetDetail tests
# ===========================================================================


def _make_detail_view(qapp, data=None, side_effect=None):
    from saebooks_desktop.views.fixed_assets import FixedAssetDetail

    view = FixedAssetDetail()
    asset_id = (data or {}).get("id", "fa-test")
    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.fixed_assets.get_fixed_asset",
            side_effect=side_effect,
        ):
            view.load(asset_id)
    else:
        with patch(
            "saebooks_desktop.views.fixed_assets.get_fixed_asset",
            return_value=data if data is not None else {},
        ):
            view.load(asset_id)
    return view


class TestFixedAssetDetailInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        from saebooks_desktop.views.fixed_assets import FixedAssetDetail

        view = FixedAssetDetail()
        assert view is not None

    def test_runs_table_has_three_columns(self, qapp) -> None:
        from saebooks_desktop.views.fixed_assets import FixedAssetDetail

        view = FixedAssetDetail()
        assert view._runs_model.columnCount() == 3

    def test_runs_column_headers(self, qapp) -> None:
        from saebooks_desktop.views.fixed_assets import FixedAssetDetail

        view = FixedAssetDetail()
        headers = [
            view._runs_model.horizontalHeaderItem(i).text()
            for i in range(view._runs_model.columnCount())
        ]
        assert headers == ["Period Date", "Depreciation Amount", "NBV After"]


class TestFixedAssetDetailHeaderFields:
    def test_name_populated(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._name_label.text() == "Laser Cutter"

    def test_code_populated(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._code_label.text() == "FA-0001"

    def test_purchase_date_populated(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._purchase_date_label.text() == "2023-01-15"

    def test_purchase_price_populated(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._purchase_price_label.text() == "15000.00"

    def test_nbv_populated(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._nbv_label.text() == "12000.00"

    def test_status_badge_text(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._status_badge.text() == "ACTIVE"


class TestFixedAssetDetailDepreciationRuns:
    def test_runs_row_count(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._runs_model.rowCount() == 2

    def test_run_period_date(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._runs_model.item(0, 0).text() == "2023-12-31"

    def test_run_depreciation_amount(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._runs_model.item(0, 1).text() == "1500.00"

    def test_run_nbv_after(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._runs_model.item(0, 2).text() == "13500.00"

    def test_empty_runs(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DISPOSED)
        assert view._runs_model.rowCount() == 0


class TestFixedAssetDetailButtons:
    def test_depreciate_enabled_for_active(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._depreciate_btn.isEnabled()

    def test_dispose_enabled_for_active(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._dispose_btn.isEnabled()

    def test_depreciate_disabled_for_disposed(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DISPOSED)
        assert not view._depreciate_btn.isEnabled()

    def test_dispose_disabled_for_disposed(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DISPOSED)
        assert not view._dispose_btn.isEnabled()

    def test_back_button_emits_signal(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view._back_btn.click()
        assert received == [True]

    def test_depreciate_emits_signal_on_confirm(self, qapp, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        received: list[str] = []
        view.depreciate_requested.connect(received.append)
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        view._on_depreciate_clicked()
        assert received == ["fa-001"]

    def test_depreciate_no_emit_on_cancel(self, qapp, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        received: list[str] = []
        view.depreciate_requested.connect(received.append)
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        view._on_depreciate_clicked()
        assert received == []

    def test_dispose_emits_signal_on_confirm(self, qapp, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        received: list[str] = []
        view.dispose_requested.connect(received.append)
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        view._on_dispose_clicked()
        assert received == ["fa-001"]


class TestFixedAssetDetailOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_detail_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_detail_view(qapp, data=_SAMPLE_ASSET_DETAIL)
        assert view._offline_label.isHidden()
