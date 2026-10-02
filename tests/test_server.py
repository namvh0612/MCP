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
                   "eae_net_connect", "eae_net_disconnect", "eae_net_set_param", "eae_map_to_resource", "eae_unmap",
                   "eae_cat_create", "eae_ehmi_canvas_create", "eae_ehmi_place_symbol", "eae_ehmi_remove_object", "eae_opcua_expose",
                   "eae_ehmi_update_object", "eae_cat_add_symbol",
                   "eae_hmi_canvas_create", "eae_hmi_place_symbol", "eae_hmi_update_object", "eae_hmi_remove_object",
                   "eae_function_create", "eae_function_update",
                   "eae_rest_client_create", "eae_hmi_symbol_build", "eae_hmi_display_build"}
        assert {t.name for t in tools if not t.annotations.read_only_hint} == writers
        modifying = {t.name for t in tools if t.annotations.destructive_hint}
        assert modifying == {"eae_datatype_update", "eae_fb_update_interface", "eae_basic_upsert_algorithm",
                             "eae_basic_update_ecc", "eae_net_remove_fb", "eae_net_disconnect", "eae_net_set_param",
                             "eae_unmap", "eae_ehmi_remove_object", "eae_opcua_expose",
                             "eae_ehmi_update_object", "eae_hmi_update_object", "eae_hmi_remove_object",
                             "eae_function_update"}


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


async def test_description_to_hmi_over_mcp(golden_dir, library_store, tmp_path):
    """The design_hmi_from_description workflow, tool by tool, as an assistant would run it."""
    import json
    import shutil

    root = tmp_path / "plant"
    shutil.copytree(golden_dir, root)
    server = create_server(Config(roots=[tmp_path], allow_write=True, library_store=library_store))

    def data(r):
        assert not r.is_error, r.content[0].text
        return json.loads(r.content[0].text)

    async with Client(server) as client:
        assert data(await client.call_tool("eae_open_solution", {"path": str(root)}))
        hmi_vars = [{"name": "Flow", "type": "REAL"}, {"name": "State", "type": "INT"}, {"name": "Alarm", "type": "INT"}]
        data(await client.call_tool("eae_cat_create", {
            "name": "catPump", "hmi_event_inputs": [{"name": "REQ", "with_vars": ["Flow", "State", "Alarm"]}],
            "hmi_input_vars": hmi_vars, "dry_run": False}))
        draft = data(await client.call_tool("eae_hmi_design_suggest", {"cat": "catPump", "title": "Pump P-101"}))
        elements = draft["elements"]
        for e in elements:  # the assistant fills in what the description says
            if e["var"] == "Flow":
                e.update(unit="m3/h", range=[0, 120], normal=[40, 90], limits=[20, 105])
            if e["var"] == "State":
                e.update(states={"0": "Stopped", "1": "Running", "2": "Fault"}, abnormal=["2"], priority=1)
        r = data(await client.call_tool("eae_hmi_symbol_build", {"cat": "catPump", "title": draft["title"],
                                                                   "elements": elements, "dry_run": False}))
        assert r.get("written") or r.get("applied") or r
        for n in ("P101", "P102"):
            data(await client.call_tool("eae_net_add_fb", {"network": "APP1", "name": n, "type": "catPump",
                                                            "dry_run": False}))
            data(await client.call_tool("eae_map_to_resource", {"instance": n, "resource": "EcoRT_0/RES0",
                                                                 "dry_run": False}))
        for tech in ("hmi", "ehmi"):
            data(await client.call_tool("eae_hmi_display_build", {
                "canvas": "PumpStation", "title": "Pump station", "level": 2, "technology": tech,
                "device": "EcoRT_0", "sections": [{"title": "Feed pumps", "instances": ["P101", "P102"]}],
                "dry_run": False}))
        review = data(await client.call_tool("eae_hmi_review", {"name": "PumpStation", "level": 2}))
        assert {d["display"] for d in review["displays"]} == {"hmi canvas PumpStation", "ehmi canvas PumpStation"}
        assert all(f["severity"] != "warning" for d in review["displays"] for f in d["findings"])
        sym = data(await client.call_tool("eae_hmi_review", {"name": "sSA"}))
        assert sym["displays"][0]["findings"] == []
