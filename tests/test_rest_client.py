import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from eae_mcp.config import Config
from eae_mcp.io import xmlrt
from eae_mcp.project import rest_client as rc
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution, resolve_reference
from eae_mcp.project.validate import validate_solution
from eae_mcp.rest_probe import ProbeRefused, probe

SAMPLE = {"version": "4", "data": [{"network_region": "NSW1", "results": [{"date": "2026-10-02T10:00", "price": 85.3}]},
                                   {"network_region": "QLD1", "results": [{"date": "2026-10-02T10:00", "price": 72.1}]}]}
SPEC = rc.RestClientSpec(name="PriceApi", host="api.openelectricity.org.au",
                         path="/v4/market/network/NEM?metrics=price&interval=5m",
                         fields=[rc.RestField("pNSW", "price"), rc.RestField("pQLD", "price", occurrence=2),
                                 rc.RestField("ts", "date", "STRING")])


def test_extractor_semantics():
    text = json.dumps(SAMPLE)
    assert rc.extract(text, "price") == "85.3" and rc.extract(text, "price", 2) == "72.1"
    assert rc.extract(text, "date") == "2026-10-02T10:00"
    assert rc.extract(text, "data.network_region", 2) == "QLD1"
    assert rc.extract(text, "nope") == ""


def test_request_text_and_secrets():
    text = rc.request_text(SPEC, "TOKEN")
    assert text.startswith("GET /v4/market/network/NEM?metrics=price&interval=5m HTTP/1.1\r\nHost: ")
    assert "Authorization: Bearer TOKEN\r\n" in text and text.endswith("Connection: close\r\n\r\n")
    assert rc.st_literal("a$b'c\r\n") == "'a$$b$'c$R$N'"
    bad = rc.RestClientSpec(name="X", host="h.example", headers={"Authorization": "Bearer abc"},
                            fields=[rc.RestField("v", "v")])
    with pytest.raises(EditError, match="secrets"):
        rc.check_spec(bad)
    with pytest.raises(EditError, match="reserved"):
        rc.check_spec(rc.RestClientSpec(name="X", host="h.example", fields=[rc.RestField("Status", "s")]))


def test_generate_rest_client_cat(golden_dir, library_store, tmp_path):
    root = tmp_path / "g"
    shutil.copytree(golden_dir, root)
    cs = rc.create_rest_client(load_solution(root, library_store=library_store), SPEC)
    assert not any("TOKEN" in ch.new.decode("utf-8", "replace") for ch in cs.changes.values())
    cs.apply()
    sol = load_solution(root, library_store=library_store)
    assert validate_solution(sol)["counts"]["error"] == 0
    td = sol.find_type("PriceApi")
    assert td.kind == "cat" and td.folder == ".RestApi"
    conns = {(str(resolve_reference(c.source, td.network, sol, td)), str(resolve_reference(c.destination, td.network, sol, td)))
             for c in td.network.connections}
    assert {("Net.IND", "Rsp.REQ"), ("Rsp.NEXT", "Net.ACK"), ("Req.Package", "Net.SD"), ("Endpoint", "Net.ENDPOINT"),
            ("Rsp.pQLD", "IThis.pQLD"), ("Token", "Req.Token"), ("Poll.EO", "Req.REQ")} <= conns
    net = next(i for i in td.network.instances if i.name == "Net")
    assert net.type == rc.NETIO_TYPE and net.attributes["Configuration.GenericFBType.InterfaceParams"] == rc.NETIO_PARAMS
    assert sol.find_type("PriceApi_Json").interface.return_type == "STRING[255]"
    rsp = sol.find_type("PriceApi_Response")
    parse = next(a for a in rsp.algorithms if a.name == "Parse").text
    assert "pQLD := STRING_TO_REAL(PriceApi_Json(Body := body, Path := 'price', Occurrence := 2));" in parse
    for rel in cs.changes:
        if rel.endswith((".fbt", ".fct", ".cfg", "proj")):
            assert xmlrt.roundtrips(root / rel), rel


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps(SAMPLE).encode()
        self.send_response(200 if self.headers.get("Authorization") == "Bearer secret" else 401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n")

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v4/x"
    srv.shutdown()


def test_probe_gating(server):
    with pytest.raises(ProbeRefused, match="disabled"):
        probe(Config(), server)
    with pytest.raises(ProbeRefused, match="allowed_hosts"):
        probe(Config(http_probe=True, http_probe_hosts=["example.com"]), server)
    with pytest.raises(ProbeRefused, match="GET and HEAD"):
        probe(Config(http_probe=True, http_probe_hosts=["127.0.0.1"]), server, method="POST")


def test_probe_suggests_extractor_fields(server):
    cfg = Config(http_probe=True, http_probe_hosts=["127.0.0.1"])
    assert probe(cfg, server)["status"] == 401
    r = probe(cfg, server, token="secret")
    assert r["status"] == 200 and r["json"] and r["chunked"] and r["fits_generated_client"]
    assert "secret" not in json.dumps(r)
    by = {f["json"]: f for f in r["fields"]}
    assert (by["data[1].results[0].price"]["path"], by["data[1].results[0].price"]["occurrence"]) == ("price", 2)
    assert by["data[0].network_region"]["type"] == "STRING"


def _simulate(answer: bytes, chunk: int, spec=SPEC):
    """Run the generated Rx/Parse/Json ST against an answer delivered in NETIO-sized pieces."""
    import st_sim

    fn = f"{spec.name}_Json"
    json_code = rc.JSON_FN.replace("@FN@", fn).replace("@VLEN@", str(rc.VALUE_LEN))

    def json_fn(Body, Path, Occurrence):  # noqa: N803
        return st_sim.run(json_code, {"Body": Body, "Path": Path, "Occurrence": Occurrence})[fn]

    state = st_sim.run(rc.INIT_ALG, {})
    rx = rc.RX_ALG.replace("@BUF@", str(rc.BUF))
    parse = rc.PARSE_ALG.replace("@FIELDS@", "".join(rc._field_st(fn, f) for f in spec.fields))
    text = answer.decode()
    pieces = [text[i:i + chunk] for i in range(0, len(text), chunk)] + [""]
    for piece in pieces:
        state = st_sim.run(rx, {**state, "RD": piece, "RD_LEN": len(piece)})
        if state["done"]:
            return st_sim.run(parse, {**state, fn: json_fn})
    raise AssertionError("never done")


@pytest.mark.parametrize("chunk", [7, 100, 1024])
def test_generated_st_parses_chunked_and_content_length(chunk):
    body = json.dumps(SAMPLE)
    chunked = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
               + f"{40:x}\r\n".encode() + body[:40].encode() + b"\r\n"
               + f"{len(body) - 40:x}\r\n".encode() + body[40:].encode() + b"\r\n0\r\n\r\n")
    plain = (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body.encode())
    for answer in (chunked, plain):
        r = _simulate(answer, chunk)
        assert (r["Status"], r["pNSW"], r["pQLD"], r["ts"]) == (200, 85.3, 72.1, "2026-10-02T10:00")


def test_generated_st_error_status():
    r = _simulate(b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 2\r\n\r\n{}", 1024)
    assert r["Status"] == 401 and "pNSW" not in r
