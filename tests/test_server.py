import json

import pytest
from mcp import Client

from eae_mcp.config import Config
from eae_mcp.server import create_server

pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


async def test_tools_listed_and_read_only(golden_dir):
    server = create_server(Config(roots=[]))
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        names = {t.name for t in tools}
        assert {"eae_open_solution", "eae_explain", "eae_trace", "eae_cat_describe", "eae_hmi_describe"} <= names
        writers = {"eae_catalog_build", "eae_doc_scaffold", "eae_adapter_create", "eae_datatype_create", "eae_datatype_update",
                   "eae_basic_create", "eae_fb_update_interface", "eae_basic_upsert_algorithm", "eae_basic_update_ecc",
                   "eae_composite_create", "eae_subapp_create", "eae_net_add_fb", "eae_net_remove_fb",
                   "eae_net_connect", "eae_net_disconnect", "eae_net_set_param", "eae_map_to_resource", "eae_unmap"}
        assert {t.name for t in tools if not t.annotations.read_only_hint} == writers
        modifying = {t.name for t in tools if t.annotations.destructive_hint}
        assert modifying == {"eae_datatype_update", "eae_fb_update_interface", "eae_basic_upsert_algorithm",
                             "eae_basic_update_ecc", "eae_net_remove_fb", "eae_net_disconnect", "eae_net_set_param",
                             "eae_unmap"}


async def test_open_and_explain_over_mcp(golden_dir):
    server = create_server(Config(roots=[]))
    async with Client(server) as client:
        r = await client.call_tool("eae_open_solution", {"path": str(golden_dir)})
        assert not r.is_error
        r = await client.call_tool("eae_explain", {"target": "CAT1"})
        data = r.structured_content or json.loads(r.content[0].text)
        assert "CAT1" in json.dumps(data)
        r = await client.call_tool("eae_explain", {"target": "doesNotExist"})
        assert r.is_error


async def test_concept_resource(golden_dir):
    server = create_server(Config(roots=[]))
    async with Client(server) as client:
        res = await client.read_resource("eae://concepts/cat")
        assert "Composite Automation Type" in res.contents[0].text


async def test_tool_before_open_is_an_error():
    server = create_server(Config(roots=[]))
    async with Client(server) as client:
        r = await client.call_tool("eae_summary", {})
        assert r.is_error
