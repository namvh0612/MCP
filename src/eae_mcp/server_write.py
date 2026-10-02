"""M2 write tools: create/edit Adapter, DataType, Basic FB; validate. All default to dry_run=True."""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import services
from .model import Algorithm, DataTypeDef, ECAction, ECState, ECTransition, EnumValue, Event, Interface, Var
from .project import cat_edit, edit, network_edit

CREATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
MODIFY = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


class VarSpec(BaseModel):
    name: str
    type: str = Field(description="IEC type, e.g. BOOL, INT, REAL, STRING[32], TIME, or a DataType name")
    initial_value: str | None = None
    array_size: str | None = Field(None, description="e.g. '10' for an array of 10 elements")
    comment: str | None = None

    def to_model(self) -> Var:
        return Var(self.name, self.type, initial_value=self.initial_value, array_size=self.array_size,
                   comment=self.comment)


class EventSpec(BaseModel):
    name: str
    comment: str | None = None
    with_vars: list[str] = Field(default_factory=list,
                                 description="Data sampled (inputs) or sent (outputs) with this event")

    def to_model(self) -> Event:
        return Event(self.name, comment=self.comment, with_vars=list(self.with_vars))


class ActionSpec(BaseModel):
    algorithm: str | None = None
    output: str | None = Field(None, description="Output event to emit after the algorithm (or adapter event 'Plug.CNF')")


class StateSpec(BaseModel):
    name: str
    comment: str | None = None
    actions: list[ActionSpec] = Field(default_factory=list)

    def to_model(self) -> ECState:
        return ECState(self.name, self.comment, [ECAction(a.algorithm, a.output) for a in self.actions])


class TransitionSpec(BaseModel):
    source: str
    destination: str
    condition: str = Field("", description="Input event, guard expression, or '1' (always)")

    def to_model(self) -> ECTransition:
        return ECTransition(self.source, self.destination, self.condition)


class AlgorithmSpec(BaseModel):
    name: str
    text: str = Field(description="Structured Text body")
    comment: str | None = None
    local_vars: list[VarSpec] = Field(default_factory=list)

    def to_model(self) -> Algorithm:
        return Algorithm(self.name, self.text, comment=self.comment, local_vars=[v.to_model() for v in self.local_vars])


class EnumValueSpec(BaseModel):
    name: str
    value: str | None = None


def _interface(event_inputs, event_outputs, input_vars, output_vars) -> Interface:
    return Interface(
        event_inputs=[e.to_model() for e in event_inputs or []],
        event_outputs=[e.to_model() for e in event_outputs or []],
        input_vars=[v.to_model() for v in input_vars or []],
        output_vars=[v.to_model() for v in output_vars or []],
    )


def _datatype(kind, members, values, base_type, ranges) -> DataTypeDef:
    return DataTypeDef(
        kind=kind,
        base_type=base_type,
        members=[m.to_model() for m in members or []],
        values=[EnumValue(v.name, v.value) for v in values or []],
        ranges=[(str(r[0]), str(r[1])) for r in ranges or []],
    )


def register_write_tools(mcp: MCPServer, ws: services.Workspace, run, sol) -> None:
    def change(solution, build, dry_run):
        s = sol(solution)
        return run(services.run_change, ws, s, lambda: build(s), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_adapter_create(name: str, event_inputs: list[EventSpec] | None = None,
                           event_outputs: list[EventSpec] | None = None, input_vars: list[VarSpec] | None = None,
                           output_vars: list[VarSpec] | None = None, comment: str | None = None,
                           folder: str | None = None, library: str | None = None, dry_run: bool = True,
                           solution: str | None = None) -> dict:
        """Create an Adapter type (.adp + .doc.xml, registered in the .dfbproj).

        Directions are from the plug side: event_inputs/input_vars flow socket → plug,
        event_outputs/output_vars flow plug → socket. folder: logical folder like '.Connectors'.
        library: write into a library project (e.g. 'SE.Agile') instead of the main project.
        dry_run (default true) returns the diff without writing.
        """
        itf = _interface(event_inputs, event_outputs, input_vars, output_vars)
        return change(solution, lambda s: edit.create_adapter(s, name, itf, comment, folder, library), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_datatype_create(name: str, kind: Literal["struct", "enum", "array", "subrange"],
                            members: list[VarSpec] | None = None, values: list[EnumValueSpec] | None = None,
                            base_type: str | None = None, ranges: list[list[int]] | None = None,
                            comment: str | None = None, folder: str | None = None, library: str | None = None,
                            dry_run: bool = True, solution: str | None = None) -> dict:
        """Create a DataType (IEC61499/DataType/<name>.dt + .doc.xml, registered in the .dfbproj).

        struct: members. enum: values (+ base_type, default USINT). array: base_type + ranges [[0, 9]].
        subrange: base_type + ranges [[0, 100]]. Reserved words (e.g. ON) are rejected.
        """
        dt = _datatype(kind, members, values, base_type, ranges)
        return change(solution, lambda s: edit.create_datatype(s, name, dt, comment, folder, library), dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_datatype_update(name: str, kind: Literal["struct", "enum", "array", "subrange"],
                            members: list[VarSpec] | None = None, values: list[EnumValueSpec] | None = None,
                            base_type: str | None = None, ranges: list[list[int]] | None = None,
                            dry_run: bool = True, solution: str | None = None) -> dict:
        """Replace the definition of an existing DataType (members/values/ranges)."""
        dt = _datatype(kind, members, values, base_type, ranges)
        return change(solution, lambda s: edit.replace_datatype(s, name, dt), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_basic_create(name: str, event_inputs: list[EventSpec], event_outputs: list[EventSpec],
                         input_vars: list[VarSpec] | None = None, output_vars: list[VarSpec] | None = None,
                         internal_vars: list[VarSpec] | None = None, states: list[StateSpec] | None = None,
                         transitions: list[TransitionSpec] | None = None,
                         algorithms: list[AlgorithmSpec] | None = None, comment: str | None = None,
                         folder: str | None = None, library: str | None = None, dry_run: bool = True,
                         solution: str | None = None) -> dict:
        """Create a Basic FB (.fbt + .doc.xml + .meta.xml) with interface, ECC and ST algorithms.

        START is added automatically if missing. Each transition needs a condition (input event,
        guard, or '1'). Typical template: INIT(with QI)→INITO(with QO), REQ→CNF.
        """
        itf = _interface(event_inputs, event_outputs, input_vars, output_vars)
        build = lambda s: edit.create_basic(  # noqa: E731
            s, name, itf, [v.to_model() for v in internal_vars or []], [st.to_model() for st in states or []],
            [t.to_model() for t in transitions or []], [a.to_model() for a in algorithms or []],
            comment, folder, library)
        return change(solution, build, dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_fb_update_interface(name: str, add_event_inputs: list[EventSpec] | None = None,
                                add_event_outputs: list[EventSpec] | None = None,
                                add_input_vars: list[VarSpec] | None = None,
                                add_output_vars: list[VarSpec] | None = None, remove: list[str] | None = None,
                                set_with: dict[str, list[str]] | None = None, force: bool = False,
                                dry_run: bool = True, solution: str | None = None) -> dict:
        """Change the interface of an Adapter, Basic, Composite or CAT type.

        remove: pin names; refused while a pin is used in any network, ECC action or transition
        (unless force=true). set_with: {event: [vars]} replaces an event's WITH list.
        New pins get new IDs; existing IDs (and therefore connections) are preserved.
        """
        events = [("input", e.to_model()) for e in add_event_inputs or []] + \
                 [("output", e.to_model()) for e in add_event_outputs or []]
        vars_ = [("input", v.to_model()) for v in add_input_vars or []] + \
                [("output", v.to_model()) for v in add_output_vars or []]
        return change(solution, lambda s: edit.update_interface(s, name, events, vars_, remove, set_with, force),
                      dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_basic_upsert_algorithm(name: str, algorithm: str, text: str, comment: str | None = None,
                                   local_vars: list[VarSpec] | None = None, dry_run: bool = True,
                                   solution: str | None = None) -> dict:
        """Add a new ST algorithm to a Basic FB, or replace the ST code of an existing one."""
        lv = [v.to_model() for v in local_vars] if local_vars is not None else None
        return change(solution, lambda s: edit.upsert_algorithm(s, name, algorithm, text, comment, lv), dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_basic_update_ecc(name: str, add_states: list[StateSpec] | None = None,
                             remove_states: list[str] | None = None,
                             add_transitions: list[TransitionSpec] | None = None,
                             remove_transitions: list[TransitionSpec] | None = None,
                             set_actions: dict[str, list[ActionSpec]] | None = None, dry_run: bool = True,
                             solution: str | None = None) -> dict:
        """Edit a Basic FB's ECC: add/remove states and transitions, or replace a state's actions.
        Removing a state also removes its transitions. START cannot be removed."""
        actions = {k: [ECAction(a.algorithm, a.output) for a in v] for k, v in (set_actions or {}).items()}
        build = lambda s: edit.update_ecc(  # noqa: E731
            s, name, [st.to_model() for st in add_states or []], remove_states,
            [t.to_model() for t in add_transitions or []], [t.to_model() for t in remove_transitions or []],
            actions)
        return change(solution, build, dry_run)

    # -- M3: networks ---------------------------------------------------------------------------

    @mcp.tool(annotations=CREATE)
    def eae_composite_create(name: str, event_inputs: list[EventSpec] | None = None,
                             event_outputs: list[EventSpec] | None = None, input_vars: list[VarSpec] | None = None,
                             output_vars: list[VarSpec] | None = None, comment: str | None = None,
                             folder: str | None = None, library: str | None = None, dry_run: bool = True,
                             solution: str | None = None) -> dict:
        """Create a Composite FB with its interface and an empty network (boundary pins included).
        Then fill it with eae_net_add_fb / eae_net_connect using network=<name>."""
        itf = _interface(event_inputs, event_outputs, input_vars, output_vars)
        return change(solution, lambda s: network_edit.create_composite(s, name, itf, comment, folder, library),
                      dry_run)

    # -- M4: CATs ------------------------------------------------------------------------------

    @mcp.tool(annotations=CREATE)
    def eae_cat_create(name: str, event_inputs: list[EventSpec] | None = None,
                       event_outputs: list[EventSpec] | None = None, input_vars: list[VarSpec] | None = None,
                       output_vars: list[VarSpec] | None = None, hmi_event_inputs: list[EventSpec] | None = None,
                       hmi_event_outputs: list[EventSpec] | None = None, hmi_input_vars: list[VarSpec] | None = None,
                       hmi_output_vars: list[VarSpec] | None = None, symbol: str = "sDefault",
                       web_symbol: str | None = "seDefault", comment: str | None = None, folder: str | None = None,
                       library: str | None = None, dry_run: bool = True, solution: str | None = None) -> dict:
        """Create a CAT exactly like EAE's "New CAT": <name>.fbt (composite network with the IThis
        HMI interface instance, QI=TRUE), <name>_HMI.fbt, .cfg, doc/meta/offline/opcua files, the .NET
        HMI symbol `symbol` (+ generated .event.cs/.def.cs) and the eHMI symbol `web_symbol`
        (null = no eHMI symbol). All files are registered in the .dfbproj / HMI.csproj / WEB.htmlproj.

        CAT interface: omit event/var lists to get EAE's default (INIT/REQ, INITO/CNF, QI, QO).
        HMI interface (IThis): INIT/INITO/QI/QO/STATUS are always present. hmi_event_inputs with
        hmi_input_vars carry values from the CAT to the HMI (e.g. REQ WITH OUT1); hmi_event_outputs
        with hmi_output_vars carry commands from the HMI back. Supported HMI types: BOOL, BYTE, SINT,
        INT, DINT, LINT, USINT, UINT, UDINT, REAL, LREAL, STRING.
        Wire the inside with eae_net_add_fb / eae_net_connect using network=<name> (pins of IThis are
        addressed as IThis.<pin>). Open the CAT in EAE afterwards to draw the symbols."""
        given = any(x for x in (event_inputs, event_outputs, input_vars, output_vars))
        itf = _interface(event_inputs, event_outputs, input_vars, output_vars) if given else None
        hmi = _interface(hmi_event_inputs, hmi_event_outputs, hmi_input_vars, hmi_output_vars)
        return change(solution, lambda s: cat_edit.create_cat(s, name, itf, hmi, symbol, web_symbol or None, folder,
                                                              library, comment), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_subapp_create(name: str, application: str = "APP1", instance: str | None = None,
                          event_inputs: list[EventSpec] | None = None, event_outputs: list[EventSpec] | None = None,
                          dry_run: bool = True, solution: str | None = None) -> dict:
        """Create a SubApp inside an application (packaging of application content, not a reusable
        type). EAE stores its content in IEC61499/<name>/<name>.app; the application gets an instance
        (default name: NAME in upper case). Fill it with eae_net_* using network=<name>.
        Event pins only (data pins are not supported yet)."""
        itf = _interface(event_inputs, event_outputs, None, None)
        return change(solution, lambda s: network_edit.create_subapp(s, name, application, instance, itf), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_net_add_fb(network: str, name: str, type: str, namespace: str | None = None,
                       parameters: dict[str, str] | None = None, x: float | None = None, y: float | None = None,
                       dry_run: bool = True, solution: str | None = None) -> dict:
        """Add an FB/CAT instance to a network. type: solution type or system-library type
        (e.g. E_DELAY; run eae_catalog_build first). parameters: {input var: ST literal},
        e.g. {"DT": "T#1s", "Name": "'Pump1'"}. Position is chosen automatically unless x/y given.
        network: a Composite/CAT/SubApp type name, or an application ('APP1' or 'APP1/Layer').
        """
        return change(solution, lambda s: network_edit.add_fb(s, network, name, type, namespace, parameters, x, y),
                      dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_net_remove_fb(network: str, name: str, force: bool = False, dry_run: bool = True,
                          solution: str | None = None) -> dict:
        """Remove an instance and all its connections. In an application this also removes its
        mapped resource copy; refused while it is shown on an HMI/eHMI canvas (unless force=true).
        network: a Composite/CAT/SubApp type, an application ('APP1', 'APP1/Layer') or a resource
        ('EcoRT_0/RES0')."""
        return change(solution, lambda s: network_edit.remove_fb(s, network, name, force), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_net_connect(network: str, source: str, destination: str, replace: bool = False,
                        dry_run: bool = True, solution: str | None = None) -> dict:
        """Connect two pins: 'Instance.Pin' or a boundary pin name of the enclosing type ('REQ').
        Kind (event/data/adapter) is inferred; direction is checked (reversed order is accepted).
        A data input accepts one source (replace=true replaces it). In an application, the
        connection is also copied into a resource when both FBs are mapped to it.
        network: a Composite/CAT/SubApp type, an application ('APP1', 'APP1/Layer') or a resource
        ('EcoRT_0/RES0')."""
        return change(solution, lambda s: network_edit.connect(s, network, source, destination, replace), dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_net_disconnect(network: str, source: str, destination: str, dry_run: bool = True,
                           solution: str | None = None) -> dict:
        """Remove a connection (and its resource copy for application networks).
        network: a Composite/CAT/SubApp type, an application ('APP1', 'APP1/Layer') or a resource
        ('EcoRT_0/RES0')."""
        return change(solution, lambda s: network_edit.disconnect(s, network, source, destination), dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_net_set_param(network: str, instance: str, var: str, value: str | None, dry_run: bool = True,
                          solution: str | None = None) -> dict:
        """Set (or clear with value=null) a parameter on an instance input. Values are ST literals:
        5, TRUE, T#1s, 'text'. Application parameters are synced to the mapped resource copy.
        network: a Composite/CAT/SubApp type, an application ('APP1', 'APP1/Layer') or a resource
        ('EcoRT_0/RES0')."""
        return change(solution, lambda s: network_edit.set_param(s, network, instance, var, value), dry_run)

    @mcp.tool(annotations=CREATE)
    def eae_map_to_resource(instance: str, resource: str, application: str | None = None, dry_run: bool = True,
                            solution: str | None = None) -> dict:
        """Map an application instance to a resource ('EcoRT_0/RES0'): creates the resource copy
        (new ID, Mapping=<application FB ID>, same parameters) and copies connections to FBs already
        mapped to the same resource. Cross-resource communication is not generated."""
        return change(solution, lambda s: network_edit.map_to_resource(s, instance, resource, application), dry_run)

    @mcp.tool(annotations=MODIFY)
    def eae_unmap(instance: str, application: str | None = None, dry_run: bool = True,
                  solution: str | None = None) -> dict:
        """Remove an application instance's resource copy (and its resource connections)."""
        return change(solution, lambda s: network_edit.unmap(s, instance, application), dry_run)

    @mcp.tool(annotations=READ_ONLY)
    def eae_validate(name: str | None = None, solution: str | None = None) -> dict:
        """Static checks: identifiers and reserved words, duplicate pins/IDs, WITH associations,
        ECC consistency, unresolved connections, multiple sources on a data input, unknown types,
        and project registration. Pass a type name, or omit to check the whole solution.
        This does not replace EAE's compiler (Tools › Check Changes)."""
        return run(services.validate, sol(solution), name)
