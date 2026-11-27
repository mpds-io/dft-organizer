"""Geometry-optimization provenance classification for phonon rows."""

from types import SimpleNamespace

from dft_organizer import phonon_utils as pu


def _link(label, node):
    return SimpleNamespace(link_label=label, node=node)


def _with_incoming(node, links):
    node.base = SimpleNamespace(
        links=SimpleNamespace(
            get_incoming=lambda: SimpleNamespace(all=lambda: list(links))
        )
    )
    return node


def _options_node(flag):
    return SimpleNamespace(get_dict=lambda: {"options": {"optimize_structure": flag}})


def _phonon_node(process_type, structure, caller=None, incoming=()):
    node = SimpleNamespace(
        process_type=process_type,
        pk=1,
        inputs=SimpleNamespace(structure=structure),
        caller=caller,
    )
    return _with_incoming(node, list(incoming))


def _optgeom_calc(pk=11, label="Al2O3/167: Geometry optimization [1]"):
    return SimpleNamespace(
        pk=pk,
        process_type="aiida.calculations:crystal_dft.parallel",
        label=label,
        exit_status=0,
    )


def test_crystal_optgeom_same_engine(monkeypatch):
    structure = SimpleNamespace(pk=10, creator=_optgeom_calc())
    calc = _phonon_node("aiida.calculations:crystal_dft.parallel", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: calc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "yes"
    assert result["geometry_source"].startswith("same-engine optimization:")
    assert "pk=11" in result["geometry_source"]
    assert "Geometry optimization" in result["geometry_source"]


def test_fleur_on_crystal_optimized_geometry(monkeypatch):
    structure = SimpleNamespace(pk=10, creator=_optgeom_calc())
    wc = _phonon_node("aiida.workflows:phonopy.fleur", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "questionable"
    assert result["geometry_source"].startswith("other-engine optimization:")
    assert (
        "creator engine 'crystal' differs from row engine 'fleur'"
        in result["geometry_source"]
    )


def test_pristine_structure_with_optimize_false(monkeypatch):
    structure = SimpleNamespace(pk=20, creator=None)
    parent = _with_incoming(
        SimpleNamespace(process_type="aiida.workflows:abacus.mpds"),
        [_link("workchain_options", _options_node(False))],
    )
    wc = _phonon_node("aiida.workflows:phonopy.abacus", structure, caller=parent)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "no"
    assert result["geometry_source"].startswith("pristine:")
    assert "structure pk=20" in result["geometry_source"]
    assert "optimize_structure=False" in result["geometry_source"]


def test_manual_calcfunction_transform(monkeypatch):
    transform = SimpleNamespace(
        pk=30,
        process_type="__main__.double_mgo_cell",
        label="double_mgo_cell",
        exit_status=0,
    )
    structure = SimpleNamespace(pk=31, creator=transform)
    wc = _phonon_node("aiida.workflows:phonopy.abacus", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "questionable"
    assert result["geometry_source"].startswith("manual transform:")
    assert "pk=30" in result["geometry_source"]


def test_same_engine_workchain_creator(monkeypatch):
    optimizer = SimpleNamespace(
        pk=40,
        process_type="aiida.workflows:reoptimize.fleur.cgd",
        label="",
        exit_status=0,
    )
    structure = SimpleNamespace(pk=41, creator=optimizer)
    wc = _phonon_node("aiida.workflows:phonopy.fleur", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "yes"
    assert result["geometry_source"].startswith("same-engine optimization:")


def test_unloadable_node_is_questionable(monkeypatch):
    def boom(pk):
        raise ValueError("gone")

    monkeypatch.setattr("aiida.orm.load_node", boom)

    result = pu.classify_geometry_provenance(999)

    assert result["geometry_optimized"] == "questionable"
    assert result["geometry_source"].startswith("unresolved:")
    assert "gone" in result["geometry_source"]


def test_non_optimization_calc_creator_is_questionable(monkeypatch):
    scf = SimpleNamespace(
        pk=50,
        process_type="aiida.calculations:crystal_dft.parallel",
        label="Al2O3/167: SCF [1]",
        exit_status=0,
    )
    structure = SimpleNamespace(pk=51, creator=scf)
    calc = _phonon_node("aiida.calculations:crystal_dft.parallel", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: calc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "questionable"
    assert "unresolved:" in result["geometry_source"]
    assert "not a geometry optimization" in result["geometry_source"]


def test_relax_calc_creator_with_relax_chain_is_yes(monkeypatch):
    relax_wc = SimpleNamespace(
        pk=60,
        process_type="aiida.workflows:abacus.relax",
        label="Si/227 - optimization",
        caller=None,
    )
    base_wc = SimpleNamespace(
        pk=61,
        process_type="aiida.workflows:abacus.base",
        label="",
        caller=relax_wc,
    )
    relax_calc = SimpleNamespace(
        pk=62,
        process_type="aiida.calculations:abacus.abacus",
        label="",
        exit_status=0,
        caller=base_wc,
    )
    structure = SimpleNamespace(pk=63, creator=relax_calc)
    wc = _phonon_node("aiida.workflows:phonopy.abacus", structure)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "yes"
    assert "same-engine optimization:" in result["geometry_source"]
    assert "optimization chain: pk=60" in result["geometry_source"]


def test_unprovenanced_copy_with_optimizer_in_caller_is_questionable(monkeypatch):
    structure = SimpleNamespace(pk=70, creator=None)
    optimizer = SimpleNamespace(
        pk=71,
        process_type="aiida.workflows:reoptimize.CDGFleurSCFOptimizer",
        label="TaP/109 - optimization",
    )
    wc = _phonon_node("aiida.workflows:phonopy.fleur", structure)
    parent = SimpleNamespace(
        pk=72,
        label="TaP/109",
        caller=None,
        called=[optimizer, wc],
    )
    wc.caller = parent
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)

    result = pu.classify_geometry_provenance(1)

    assert result["geometry_optimized"] == "questionable"
    assert result["geometry_source"].startswith("unprovenanced copy:")
    assert "CDGFleurSCFOptimizer" in result["geometry_source"]
    assert "no provenance link" in result["geometry_source"]
