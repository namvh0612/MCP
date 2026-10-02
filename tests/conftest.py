import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"
LIBRARY_STORE = FIXTURES / "library_store"


@pytest.fixture(scope="session")
def solar_dir(tmp_path_factory) -> Path:
    """SolarPlantDemo (trimmed), extracted from tests/fixtures/solar_demo.zip."""
    dest = tmp_path_factory.mktemp("solar")
    with zipfile.ZipFile(FIXTURES / "solar_demo.zip") as z:
        z.extractall(dest)
    return dest / "solar_demo"


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return GOLDEN


@pytest.fixture(scope="session")
def library_store() -> Path:
    return LIBRARY_STORE
