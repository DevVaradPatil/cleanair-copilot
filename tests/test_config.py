from pathlib import Path

import pytest
from pydantic import ValidationError

from cleanair.config import PipelineConfig, load_config

CONFIGS = Path(__file__).parent.parent / "configs"


def test_base_yaml_loads_typed():
    cfg = load_config(CONFIGS / "base.yaml")
    assert cfg.retrieval.fusion == "rrf"
    assert cfg.retrieval.rrf_k == 60
    assert cfg.chunker.type == "structure"


def test_typo_in_yaml_key_is_rejected():
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"name": "x", "retrieval": {"rerankk": True}})


def test_bad_enum_value_is_rejected():
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"name": "x", "retrieval": {"fusion": "max"}})
