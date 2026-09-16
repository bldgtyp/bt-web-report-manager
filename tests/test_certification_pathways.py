from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
import yaml

import bt_web_report_manager.certification_pathways as certification_pathways
from bt_web_report_manager.certification_pathways import (
    CatalogPathway,
    CertificationCatalogError,
    DEFAULT_CERTIFICATION_PATHWAY_IDS,
    load_certification_catalog,
)
from bt_web_report_manager.projects import (
    clear_certification_pathways,
    read_project_metadata,
    set_certification_pathways,
)


def test_load_certification_catalog_reads_renderer_catalog(tmp_path: Path) -> None:
    renderer = tmp_path / "renderer"
    catalog_path = renderer / "src" / "data" / "certification-pathways.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(json.dumps([{"id": "phi-classic", "title": "PHI Classic", "extra": True}]))

    assert load_certification_catalog(renderer) == [CatalogPathway("phi-classic", "PHI Classic")]


def test_load_certification_catalog_reports_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(certification_pathways, "_certification_catalog_candidates", lambda renderer_source: (missing,))

    with pytest.raises(CertificationCatalogError, match="was not found"):
        load_certification_catalog()


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"id": "phi-classic"}, "JSON array"),
        ([{"id": "Not Kebab", "title": "Title"}], "invalid kebab-case id"),
        ([{"id": "phi-classic"}], "no valid title"),
        (
            [
                {"id": "phi-classic", "title": "PHI Classic"},
                {"id": "phi-classic", "title": "Duplicate"},
            ],
            "duplicate id",
        ),
    ],
)
def test_load_certification_catalog_rejects_malformed_entries(tmp_path: Path, payload: object, message: str) -> None:
    renderer = tmp_path / "renderer"
    catalog_path = renderer / "src" / "data" / "certification-pathways.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(json.dumps(payload))

    with pytest.raises(CertificationCatalogError, match=message):
        load_certification_catalog(renderer)


def test_read_project_metadata_uses_none_when_block_is_absent(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    metadata = read_project_metadata(project)

    assert metadata.certification_pathways_show is None
    assert metadata.certification_pathways_recommended is None


def test_read_project_metadata_parses_certification_pathways(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    raw = yaml.safe_load((project / "project.yaml").read_text())
    raw["certification_pathways"] = {
        "show": ["enerphit-component", "phi-classic"],
        "recommended": "enerphit-component",
    }
    (project / "project.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))

    metadata = read_project_metadata(project)

    assert metadata.certification_pathways_show == ("enerphit-component", "phi-classic")
    assert metadata.certification_pathways_recommended == "enerphit-component"


def test_set_certification_pathways_writes_order_and_recommended(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    written = set_certification_pathways(
        project,
        ["enerphit-component", "phi-classic"],
        "enerphit-component",
    )

    raw = yaml.safe_load(written.read_text())
    assert raw["certification_pathways"] == {
        "show": ["enerphit-component", "phi-classic"],
        "recommended": "enerphit-component",
    }


def test_set_certification_pathways_omits_recommended_when_none(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    written = set_certification_pathways(project, ["phi-classic"], None)

    assert yaml.safe_load(written.read_text())["certification_pathways"] == {"show": ["phi-classic"]}


@pytest.mark.parametrize(
    "show, recommended, message",
    [
        ([], None, "at least one"),
        (["phi-classic", "phi-classic"], None, "unique"),
        (["phi-classic"], "phi-leb", "must be included"),
        (["PHI Classic"], None, "kebab-case"),
    ],
)
def test_set_certification_pathways_rejects_invalid_selection(
    tmp_path: Path, show: list[str], recommended: str | None, message: str
) -> None:
    project = _make_project(tmp_path)

    with pytest.raises(ValueError, match=message):
        set_certification_pathways(project, show, recommended)


def test_set_certification_pathways_rejects_unknown_id_when_catalog_is_supplied(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    catalog = [CatalogPathway("phi-classic", "PHI Classic")]

    with pytest.raises(ValueError, match="Unknown certification pathway"):
        set_certification_pathways(project, ["enerphit-component"], None, catalog)


def test_set_and_clear_certification_pathways_preserve_comments_and_other_keys(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    project_yaml = project / "project.yaml"
    project_yaml.write_text(
        "# project comment\n"
        "slug: sample\n"
        'project_title: "Quoted title"\n'
        "source_files:\n"
        "  # data comment\n"
        "  data_dir: data\n"
        "publishing:\n"
        "  production_url: https://sample.bldgtyp.com\n"
        "certification_pathways: # pathways comment\n"
        "  show: [phi-leb] # show comment\n"
        "  recommended: phi-leb\n"
    )

    set_certification_pathways(project, ["phi-classic"], "phi-classic")
    text_after_set = project_yaml.read_text()
    assert "# project comment" in text_after_set
    assert "# data comment" in text_after_set
    assert 'project_title: "Quoted title"' in text_after_set
    assert "certification_pathways:" in text_after_set
    assert "# pathways comment" in text_after_set
    assert "# show comment" in text_after_set

    clear_certification_pathways(project)
    text_after_clear = project_yaml.read_text()
    assert "certification_pathways:" not in text_after_clear
    assert "# project comment" in text_after_clear
    assert "# data comment" in text_after_clear
    assert 'project_title: "Quoted title"' in text_after_clear


def test_default_ids_match_template_when_present() -> None:
    source = (
        Path(__file__).parents[2] / "bt-web-report-template" / "src" / "data" / "certification-pathway-selection.mjs"
    )
    if not source.exists():
        pytest.skip("Template default pathway module is not present in this checkout.")
    match = re.search(r"DEFAULT_CERTIFICATION_PATHWAY_IDS\s*=\s*\[([^\]]+)]", source.read_text(), re.DOTALL)
    if match is None:
        pytest.fail(f"Could not find the template default pathway list in {source}")
    template_ids = tuple(re.findall(r'["\']([a-z0-9-]+)["\']', match.group(1)))
    assert DEFAULT_CERTIFICATION_PATHWAY_IDS == template_ids


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "Sample" / "04_Web"
    project.mkdir(parents=True)
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "sample",
                "project_title": "Sample",
                "source_files": {"data_dir": "data"},
                "publishing": {"production_url": "https://sample.bldgtyp.com"},
            },
            sort_keys=False,
        )
    )
    return project
