import shutil
from pathlib import Path

import pytest

from backend.app.build import ReportBlocked, build_aetops_mensual
from backend.app.models import Period
from backend.app.pipeline import run_aetops
from tests.fixtures import build_base


def test_blocked_result_cannot_generate_a_report(tmp_path):
    res = run_aetops(build_base(tmp_path / "dup", mom_identical=True), "mensual", Period("AETOPS", "mensual", 2026, 9))
    assert not res.can_generate
    with pytest.raises(ReportBlocked) as e:
        build_aetops_mensual(res, Period("AETOPS", "mensual", 2026, 9), Path("no_importa.pptx"), tmp_path / "out")
    assert "IDENTICAL_PERIODS" in str(e.value) and not (tmp_path / "out").exists()
