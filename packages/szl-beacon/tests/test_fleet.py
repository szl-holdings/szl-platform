"""Fleet configuration tests: reference fleet validates; breakage caught."""

from __future__ import annotations

import copy
from pathlib import Path

from szl_beacon.fleet import (
    YamlSubsetError,
    load_fleet,
    parse_yaml_subset,
    validate_fleet,
)

FLEET_YAML = Path(__file__).resolve().parent.parent / "fleet" / "fleet.yaml"


def _reference_config() -> dict:
    return load_fleet(FLEET_YAML)


class TestReferenceFleet:
    def test_shipped_fleet_validates(self) -> None:
        config = _reference_config()
        report = validate_fleet(config)
        assert report["ok"], report["findings"]

    def test_shipped_fleet_has_50_nodes(self) -> None:
        config = _reference_config()
        assert len(config["nodes"]) == 50
        report = validate_fleet(config)
        assert report["node_count"] == 50

    def test_regions_cover_maritime_disaster_legal(self) -> None:
        config = _reference_config()
        regions = {node["region"] for node in config["nodes"]}
        assert {"maritime", "disaster", "legal"} <= regions

    def test_header_declares_reference_only(self) -> None:
        text = FLEET_YAML.read_text(encoding="utf-8")
        assert "Reference only" in text
        assert "Zero units deployed" in text
        assert "Not a claim of fielded hardware" in text
        config = _reference_config()
        assert config["deployed_units"] == 0


class TestValidator:
    def test_duplicate_node_id_fails(self) -> None:
        config = _reference_config()
        config["nodes"][1]["node_id"] = config["nodes"][0]["node_id"]
        report = validate_fleet(config)
        assert not report["ok"]
        assert any(f["code"] == "DUPLICATE_NODE_ID" for f in report["findings"])

    def test_broken_witness_group_fails(self) -> None:
        """A FIELD node whose groups provide < 2 distinct classes fails."""

        config = _reference_config()
        config["witness_groups"]["thin"] = ["INDEPENDENT_SENSOR"]
        config["nodes"][0]["witness_groups"] = ["thin"]
        report = validate_fleet(config)
        assert not report["ok"]
        codes = {f["code"] for f in report["findings"]}
        assert "WITNESS_GROUP_TOO_THIN" in codes
        assert "FIELD_WITHOUT_DIVERSITY" in codes

    def test_field_node_without_group_fails(self) -> None:
        config = _reference_config()
        config["nodes"][2]["witness_groups"] = []
        report = validate_fleet(config)
        assert not report["ok"]
        assert any(f["code"] == "FIELD_WITHOUT_GROUP" for f in report["findings"])

    def test_unknown_witness_group_reference_fails(self) -> None:
        config = _reference_config()
        config["nodes"][3]["witness_groups"] = ["nonexistent-group"]
        report = validate_fleet(config)
        assert not report["ok"]
        assert any(f["code"] == "UNKNOWN_WITNESS_GROUP" for f in report["findings"])

    def test_sync_window_bounds_enforced(self) -> None:
        config = _reference_config()
        config["nodes"][0]["sync_window_minutes"] = 121
        report = validate_fleet(config)
        assert not report["ok"]
        assert any(f["code"] == "BAD_SYNC_WINDOW" for f in report["findings"])

        config2 = _reference_config()
        config2["nodes"][0]["sync_window_minutes"] = 4
        report2 = validate_fleet(config2)
        assert not report2["ok"]

    def test_bad_role_fails(self) -> None:
        config = _reference_config()
        config["nodes"][0]["role"] = "CAPTAIN"
        report = validate_fleet(config)
        assert not report["ok"]
        assert any(f["code"] == "BAD_ROLE" for f in report["findings"])

    def test_relay_and_operator_need_no_witness_group(self) -> None:
        config = _reference_config()
        relay = next(n for n in config["nodes"] if n["role"] == "RELAY")
        relay["witness_groups"] = []
        report = validate_fleet(config)
        assert report["ok"], report["findings"]


class TestYamlSubset:
    def test_round_trip_scalars_and_lists(self) -> None:
        parsed = parse_yaml_subset(
            "name: demo\n"
            "count: 3\n"
            "tags: [a, b, c]\n"
            "nested:\n"
            "  inner: value\n"
        )
        assert parsed == {
            "name": "demo",
            "count": 3,
            "tags": ["a", "b", "c"],
            "nested": {"inner": "value"},
        }

    def test_comments_stripped(self) -> None:
        parsed = parse_yaml_subset("a: 1  # trailing comment\n# full line\nb: x\n")
        assert parsed == {"a": 1, "b": "x"}

    def test_outside_subset_fails_closed(self) -> None:
        import pytest

        with pytest.raises(YamlSubsetError):
            parse_yaml_subset("- just a top-level list\n- not a mapping\n")

    def test_deepcopy_of_config_still_validates(self) -> None:
        config = copy.deepcopy(_reference_config())
        assert validate_fleet(config)["ok"]
