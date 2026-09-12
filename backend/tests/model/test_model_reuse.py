import os
import pytest
from model.model_loader import ModelSingletonManager

def test_model_singleton_reuse():
    """Verify that model initialization loads once and subsequent calls return the exact same instance."""
    ModelSingletonManager.reset()
    
    os.environ["OFFLINE_MODE"] = "1"
    try:
        model1, tok1, status1, load_time1 = ModelSingletonManager.get_instance()
        assert model1 is not None
        assert tok1 is not None
        assert status1 is not None
        
        # Second call
        model2, tok2, status2, load_time2 = ModelSingletonManager.get_instance()
        
        # Must be identical in-memory objects
        assert id(model1) == id(model2)
        assert id(tok1) == id(tok2)
        assert status1 == status2
        assert load_time1 == load_time2
    finally:
        os.environ.pop("OFFLINE_MODE", None)
        ModelSingletonManager.reset()


def test_require_adapter_missing_fails():
    """Verify that REQUIRE_ADAPTER=1 raises RuntimeError when adapter_config.json is absent."""
    ModelSingletonManager.reset()
    os.environ["REQUIRE_ADAPTER"] = "1"
    os.environ["OFFLINE_MODE"] = "1"
    try:
        with pytest.raises(RuntimeError, match="REQUIRE_ADAPTER=1 configured but adapter_config.json missing"):
            ModelSingletonManager.get_instance(adapter_path="outputs/non_existent_adapter_dir")
    finally:
        os.environ.pop("REQUIRE_ADAPTER", None)
        os.environ.pop("OFFLINE_MODE", None)
        ModelSingletonManager.reset()
