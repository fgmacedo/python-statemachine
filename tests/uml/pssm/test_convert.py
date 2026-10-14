"""Unit tests for the PSSM converter, on a tiny hand-written XMI shaped like the suite's."""

import xml.etree.ElementTree as ET

import pytest
import yaml

from . import convert as c
from .test_pssm_cases import TraceRecorder
from .test_pssm_cases import build_machine

GUARD = "this.count == 0"

XMI = """<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001"
         xmlns:uml="http://www.omg.org/spec/UML/20131001">
 <uml:Model xmi:type="uml:Model" xmi:id="model" name="Suite">
  <packagedElement xmi:type="uml:Package" xmi:id="util" name="Util">
   <packagedElement xmi:type="uml:Class" xmi:id="target" name="Target">
    <ownedOperation xmi:type="uml:Operation" xmi:id="trace" name="trace"/>
   </packagedElement>
   <packagedElement xmi:type="uml:Class" xmi:id="semanticTest" name="SemanticTest">
    <ownedAttribute xmi:type="uml:Property" xmi:id="expected" name="expectedTraces"/>
   </packagedElement>
   <packagedElement xmi:type="uml:Signal" xmi:id="startSignal" name="Start"/>
   <packagedElement xmi:type="uml:SignalEvent" xmi:id="start" signal="startSignal"/>
   <packagedElement xmi:type="uml:Signal" xmi:id="dataSignal" name="Data">
    <ownedAttribute xmi:type="uml:Property" xmi:id="dataValue" name="value"/>
   </packagedElement>
   <packagedElement xmi:type="uml:SignalEvent" xmi:id="data" signal="dataSignal"/>
   <packagedElement xmi:type="uml:Activity" xmi:id="tests" name="DemoTests">
    <node xmi:type="uml:StructuredActivityNode" xmi:id="stmt" name="1:Expression Statement">
     <edge xmi:type="uml:ObjectFlow" xmi:id="e0" source="created" target="object"/>
     <node xmi:type="uml:CreateObjectAction" xmi:id="create" classifier="demoTest">
      <result xmi:type="uml:OutputPin" xmi:id="created"/>
     </node>
     <node xmi:type="uml:AddStructuralFeatureValueAction" xmi:id="write"
           structuralFeature="expected">
      <object xmi:type="uml:InputPin" xmi:id="object"/>
     </node>
     <node xmi:type="uml:ValueSpecificationAction" xmi:id="oracle">
      <value xmi:type="uml:LiteralString" xmi:id="oracleValue"
             value="S1(entry)"/>
     </node>
    </node>
   </packagedElement>
  </packagedElement>
  <packagedElement xmi:type="uml:Package" xmi:id="demo" name="Demo">
   <packagedElement xmi:type="uml:Package" xmi:id="p001" name="001">
    <packagedElement xmi:type="uml:Class" xmi:id="demoTarget" name="Demo001_Test"
                     classifierBehavior="sm">
     <ownedAttribute xmi:type="uml:Property" xmi:id="count" name="count">
      <type href="http://www.omg.org/spec/UML/20131001/PrimitiveTypes.xmi#Integer"/>
      <defaultValue xmi:type="uml:LiteralInteger" xmi:id="countDefault"/>
     </ownedAttribute>
     <ownedBehavior xmi:type="uml:StateMachine" xmi:id="sm" name="behavior">
      <region xmi:type="uml:Region" xmi:id="r" name="Region1">
       <subvertex xmi:type="uml:Pseudostate" xmi:id="init" name="Initial1"/>
       <subvertex xmi:type="uml:State" xmi:id="wait" name="wait"/>
       <subvertex xmi:type="uml:State" xmi:id="s1" name="S1">
        <entry xmi:type="uml:Activity" xmi:id="s1Entry" name="entry">
         <edge xmi:type="uml:ObjectFlow" xmi:id="e1" source="s1Text" target="s1Segment"/>
         <node xmi:type="uml:ValueSpecificationAction" xmi:id="s1Value">
          <result xmi:type="uml:OutputPin" xmi:id="s1Text"/>
          <value xmi:type="uml:LiteralString" xmi:id="s1Literal" value="S1(entry)"/>
         </node>
         <node xmi:type="uml:CallOperationAction" xmi:id="s1Call" operation="trace">
          <argument xmi:type="uml:InputPin" xmi:id="s1Segment"/>
         </node>
        </entry>
        <region xmi:type="uml:Region" xmi:id="r1" name="Region1">
         <subvertex xmi:type="uml:Pseudostate" xmi:id="init1" name="Initial1"/>
         <subvertex xmi:type="uml:State" xmi:id="s11" name="S1.1"/>
         <subvertex xmi:type="uml:FinalState" xmi:id="fin1" name="FinalState1"/>
         <transition xmi:type="uml:Transition" xmi:id="t11" name="T1.1"
                     source="init1" target="s11"/>
         <transition xmi:type="uml:Transition" xmi:id="t12" name="T1.2"
                     source="s11" target="fin1"/>
        </region>
       </subvertex>
       <subvertex xmi:type="uml:State" xmi:id="s2" name="S2"/>
       <subvertex xmi:type="uml:FinalState" xmi:id="fin" name="FinalState1"/>
       <transition xmi:type="uml:Transition" xmi:id="t0" name="T0" source="init" target="wait"/>
       <transition xmi:type="uml:Transition" xmi:id="t1" name="T1" source="wait" target="s1">
        <trigger xmi:type="uml:Trigger" xmi:id="t1Trigger" event="start"/>
       </transition>
       <transition xmi:type="uml:Transition" xmi:id="t2" name="T2" source="s1" target="s2"
                   guard="t2Guard">
        <ownedRule xmi:type="uml:Constraint" xmi:id="t2Guard">
         <specification xmi:type="uml:OpaqueExpression" xmi:id="t2Spec">
          <language>Alf</language>
          <body>{guard}</body>
         </specification>
        </ownedRule>
        <trigger xmi:type="uml:Trigger" xmi:id="t2Trigger" event="data"/>
        <effect xmi:type="uml:Activity" xmi:id="t2Effect" name="effect">
         <ownedParameter xmi:type="uml:Parameter" xmi:id="t2Data" name="data"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e2" source="t2In" target="t2Object"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e3" source="t2Prefix" target="t2X"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e4" source="t2Read" target="t2Y"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e5" source="t2Joined" target="t2X2"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e6" source="t2Suffix" target="t2Y2"/>
         <edge xmi:type="uml:ObjectFlow" xmi:id="e7" source="t2Text" target="t2Segment"/>
         <node xmi:type="uml:ActivityParameterNode" xmi:id="t2In" parameter="t2Data"/>
         <node xmi:type="uml:ReadStructuralFeatureAction" xmi:id="t2ReadValue"
               structuralFeature="dataValue">
          <object xmi:type="uml:InputPin" xmi:id="t2Object"/>
          <result xmi:type="uml:OutputPin" xmi:id="t2Read"/>
         </node>
         <node xmi:type="uml:ValueSpecificationAction" xmi:id="t2PrefixValue">
          <result xmi:type="uml:OutputPin" xmi:id="t2Prefix"/>
          <value xmi:type="uml:LiteralString" xmi:id="t2PrefixLiteral" value="T2(effect)[in="/>
         </node>
         <node xmi:type="uml:CallBehaviorAction" xmi:id="t2Concat">
          <behavior href="fUML_Library.xmi#PrimitiveBehaviors-StringFunctions-Concat"/>
          <argument xmi:type="uml:InputPin" xmi:id="t2X"/>
          <argument xmi:type="uml:InputPin" xmi:id="t2Y"/>
          <result xmi:type="uml:OutputPin" xmi:id="t2Joined"/>
         </node>
         <node xmi:type="uml:ValueSpecificationAction" xmi:id="t2SuffixValue">
          <result xmi:type="uml:OutputPin" xmi:id="t2Suffix"/>
          <value xmi:type="uml:LiteralString" xmi:id="t2SuffixLiteral" value="]"/>
         </node>
         <node xmi:type="uml:CallBehaviorAction" xmi:id="t2Concat2">
          <behavior href="fUML_Library.xmi#PrimitiveBehaviors-StringFunctions-Concat"/>
          <argument xmi:type="uml:InputPin" xmi:id="t2X2"/>
          <argument xmi:type="uml:InputPin" xmi:id="t2Y2"/>
          <result xmi:type="uml:OutputPin" xmi:id="t2Text"/>
         </node>
         <node xmi:type="uml:CallOperationAction" xmi:id="t2Call" operation="trace">
          <argument xmi:type="uml:InputPin" xmi:id="t2Segment"/>
         </node>
        </effect>
       </transition>
       <transition xmi:type="uml:Transition" xmi:id="t3" name="T3" source="s1" target="fin"/>
       <transition xmi:type="uml:Transition" xmi:id="t4" name="T4" source="s2" target="fin"/>
      </region>
     </ownedBehavior>
    </packagedElement>
    <packagedElement xmi:type="uml:Class" xmi:id="demoTester" name="Demo001_Tester"
                     classifierBehavior="testerBehavior">
     <ownedBehavior xmi:type="uml:Activity" xmi:id="testerBehavior" name="tester">
      <edge xmi:type="uml:ObjectFlow" xmi:id="e8" source="sevenOut" target="sendValue"/>
      <node xmi:type="uml:ValueSpecificationAction" xmi:id="seven">
       <result xmi:type="uml:OutputPin" xmi:id="sevenOut"/>
       <value xmi:type="uml:LiteralInteger" xmi:id="sevenLiteral" value="7"/>
      </node>
      <node xmi:type="uml:SendSignalAction" xmi:id="send" signal="dataSignal">
       <argument xmi:type="uml:InputPin" xmi:id="sendValue"/>
      </node>
     </ownedBehavior>
    </packagedElement>
    <packagedElement xmi:type="uml:Class" xmi:id="demoTest" name="Demo001_SemanticTest"/>
   </packagedElement>
  </packagedElement>
 </uml:Model>
</xmi:XMI>
"""


def make_suite(guard: str = GUARD) -> c.Suite:
    return c.Suite(ET.fromstring(XMI.replace("{guard}", guard)))


def convert_demo(overlay: "dict | None" = None, guard: str = GUARD) -> dict:
    suite = make_suite(guard)
    ((_, test_id, package),) = suite.tests
    return suite.convert(test_id, package, overlay or {})


def test_discovers_tests_and_reads_the_oracle_from_compiled_activities():
    suite = make_suite()

    assert [(cat, tid) for cat, tid, _ in suite.tests] == [("Demo", "Demo_001")]
    assert suite.oracle == {"Demo_001": ["S1(entry)"]}


def test_converts_a_case():
    case = convert_demo()

    assert case["requires"] == []
    assert case["stimulus"] == [{"event": "Start"}, {"event": "Data", "kwargs": {"value": 7}}]
    assert case["behaviors"] == {
        "pssm_S1_entry": ["S1(entry)"],
        "pssm_T2_effect": ["T2(effect)[in={value}]"],
    }
    assert case["statechart"] == {
        "name": "Demo_001",
        "datamodel": {"count": "0"},
        "states": {
            "wait": {"initial": True, "transitions": [{"event": "Start", "target": "S1"}]},
            "S1": {
                "enter": ["pssm_S1_entry"],
                "states": {
                    "S1_1": {
                        "initial": True,
                        "transitions": [{"target": "S1_FinalState1"}],
                    },
                    "S1_FinalState1": {"final": True},
                },
                "transitions": [
                    {
                        "event": "Data",
                        "target": "S2",
                        "cond": "count == 0",
                        "on": ["pssm_T2_effect"],
                    },
                    {"event": "done.state.S1", "target": "FinalState1"},
                ],
            },
            "S2": {"transitions": [{"target": "FinalState1"}]},
            "FinalState1": {"final": True},
        },
    }


def test_converted_case_runs_on_the_harness():
    case = yaml.safe_load(c.dump_case(convert_demo()))
    recorder = TraceRecorder(case["behaviors"], is_async=False)
    sm = build_machine(case, recorder)

    for item in case["stimulus"]:
        sm.send(item["event"], **item.get("kwargs", {}))

    assert "::".join(recorder.trace) in case["expected_traces"]


def test_dumped_case_starts_with_the_generated_header():
    dumped = c.dump_case({"requires": []})

    assert dumped.startswith("# Generated by tests/uml/pssm/convert.py")
    assert "Do not edit." in dumped.splitlines()[0]


def test_same_name_as_datamodel_and_event_kwarg_fails_the_conversion():
    with pytest.raises(c.ConversionError, match="B8"):
        convert_demo(guard="this.value == evt.value")


def test_overlay_replaces_a_behavior():
    overlay = {
        "behaviors": {
            "t2Effect": [{"assign": {"location": "count", "expr": "count + 1"}}, {"trace": "T2"}]
        }
    }

    case = convert_demo(overlay)

    effect = case["statechart"]["states"]["S1"]["transitions"][0]["on"]
    assert effect == [{"assign": {"location": "count", "expr": "count + 1"}}, "pssm_T2_effect"]
    assert case["behaviors"]["pssm_T2_effect"] == ["T2"]


def test_unused_overlay_entry_fails_the_conversion():
    with pytest.raises(c.ConversionError, match="unused overlay"):
        convert_demo({"behaviors": {"nope": [{"trace": "X"}]}})


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("true", "True"),
        ("this.count < 10 && !this.done", "count < 10 and not done"),
        ("evt.value == false || data.ok", "value == False or ok"),
        ("this.count != 5", "count != 5"),
    ],
)
def test_alf_guard_bodies(body, expected):
    guards = c.Guards(c.Xmi(ET.fromstring(XMI)), None)  # type: ignore[arg-type]
    assert guards._from_alf(body) == expected


def test_unparseable_alf_guard_fails():
    guards = c.Guards(c.Xmi(ET.fromstring(XMI)), None)  # type: ignore[arg-type]

    with pytest.raises(c.ConversionError, match="cannot translate"):
        guards._from_alf("this.count ==")


@pytest.mark.parametrize(
    ("name", "expected"), [("S1.1", "S1_1"), ("wait'", "wait_"), ("1.3", "_1_3")]
)
def test_sanitize(name, expected):
    assert c.sanitize(name) == expected


def test_canonical_states_orders_keys():
    states = {"a": {"transitions": [{"on": ["x"], "target": "b"}], "initial": True}}

    ordered = c.canonical_states(states)

    assert list(ordered["a"]) == ["initial", "transitions"]
    assert list(ordered["a"]["transitions"][0]) == ["target", "on"]


def test_xmi_with_another_digest_is_rejected(tmp_path):
    xmi = tmp_path / "suite.xmi"
    xmi.write_text(XMI)

    with pytest.raises(c.ConversionError, match="sha256"):
        c.convert(xmi, tmp_path / "out")


def test_overlay_with_an_unknown_key_is_rejected(tmp_path):
    (tmp_path / "Demo_001.yaml").write_text("statechart: {}\n")

    with pytest.raises(c.ConversionError, match="unknown overlay keys"):
        c.load_overlay("Demo_001", tmp_path)


def test_cli_requires_an_xmi(monkeypatch, capsys):
    monkeypatch.delenv("PSSM_XMI", raising=False)

    with pytest.raises(SystemExit):
        c.main([])
    assert "PSSM_XMI" in capsys.readouterr().err
