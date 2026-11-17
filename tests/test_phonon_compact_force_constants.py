"""Compact (primitive-row) force constants must expand via phonopy_data."""

from types import SimpleNamespace

import numpy as np
import pytest
from ase import Atoms

from dft_organizer import phonon_utils as pu

# 2-atom body-centered cell: the primitive has a single atom, so a compact
# force-constants array has one row per supercell atom-set while the
# extractor's primitive-less Phonopy instance expects two (unit-cell) rows.
ATOMS = Atoms(
    "Fe2",
    cell=np.eye(3) * 3.0,
    scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    pbc=True,
)
SUPERCELL = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]  # 16 supercell atoms


def _spring_full_fc(n_supercell, k=1.0):
    """Full FC of independent on-site springs (all frequencies positive)."""
    fc = np.zeros((n_supercell, n_supercell, 3, 3))
    for i in range(n_supercell):
        fc[i, i] = np.eye(3) * k
    return fc


class _FakePhonopy:
    """Stands in for the PhonopyData instance: expands to a known full FC."""

    def __init__(self, full_fc):
        self._fc = full_fc
        self.force_constants = None
        self.primitive = SimpleNamespace(p2s_map=[0])

    def produce_force_constants(self, calculate_full_force_constants):
        assert calculate_full_force_constants
        self.force_constants = self._fc


def _workchain(fake_phonopy):
    full_fc = _spring_full_fc(16)
    compact_fc = full_fc[[0]].copy()
    outputs = {
        "output_phonopy": SimpleNamespace(
            output_force_constants=SimpleNamespace(get_array=lambda name: compact_fc),
            output_parameters=SimpleNamespace(get_dict=lambda: {}),
        )
    }
    if fake_phonopy is not None:
        outputs["phonopy_data"] = SimpleNamespace(
            get_phonopy_instance=lambda: fake_phonopy
        )
    wc = SimpleNamespace(
        inputs=SimpleNamespace(
            structure=SimpleNamespace(get_ase=lambda: ATOMS),
            supercell_matrix=SimpleNamespace(get_list=lambda: SUPERCELL),
        ),
        outputs=SimpleNamespace(**outputs),
    )
    return wc, compact_fc, full_fc


@pytest.fixture
def centered(monkeypatch):
    wc, compact_fc, full_fc = _workchain(_FakePhonopy(_spring_full_fc(16)))
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)
    return compact_fc, full_fc


def test_compact_constants_expand_via_phonopy_data(centered):
    compact_fc, full_fc = centered
    freqs = pu.extract_frequencies_from_workchain(1, mesh=[2, 2, 2])
    assert "error" not in freqs
    assert freqs["n_imaginary"] == 0
    assert freqs["gamma_freqs_cm1"] is not None
    assert len(freqs["gamma_freqs_cm1"]) == 6
    # stored compact rows are untouched
    np.testing.assert_allclose(compact_fc, full_fc[[0]], atol=0)


def test_missing_phonopy_data_is_an_informative_error(monkeypatch):
    wc, _, _ = _workchain(fake_phonopy=None)
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)
    freqs = pu.extract_frequencies_from_workchain(1, mesh=[2, 2, 2])
    assert "error" in freqs
    assert "phonopy_data" in freqs["error"]


def test_inconsistent_expansion_is_rejected(monkeypatch):
    wrong_full = _spring_full_fc(16)
    wrong_full[0, 0] = np.eye(3) * 2.0  # disagrees with the stored row
    wc, compact_fc, _ = _workchain(_FakePhonopy(wrong_full))
    monkeypatch.setattr("aiida.orm.load_node", lambda pk: wc)
    freqs = pu.extract_frequencies_from_workchain(1, mesh=[2, 2, 2])
    assert "error" in freqs
    assert "disagree" in freqs["error"]
