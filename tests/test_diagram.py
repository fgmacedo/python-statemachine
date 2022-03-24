from statemachine.diagram import dot_data_from_machine
from statemachine import StateMachine


def visualize_diagram_in_png(data):
    import pydot

    graph = pydot.graph_from_dot_data(data)[0]
    graph.write_png('output.png')


def test_diagram_from_dummy_machine():
    class DummyMachine(StateMachine):
        pass

    expected = 'digraph DummyMachine{ labelloc="t"; label="DummyMachine";}'

    data = dot_data_from_machine(DummyMachine)
    assert set(data.replace(' ', '').split(';')) == set(expected.replace(' ', '').split(';'))
    # visualize_diagram_in_png(data)


def test_diagram_for_campaign_machine(campaign_machine):
    expected = (
        'digraph CampaignMachine { labelloc="t"; label="CampaignMachine"; '
        'closed;draft [color=blue];producing; draft -> draft [label="add_job"];'
        'draft -> producing [label="produce"];producing -> producing [label="add_job"];'
        'producing -> closed [label="deliver"]; }'
    )

    data = dot_data_from_machine(campaign_machine)
    assert set(data.replace(' ', '').split(';')) == set(expected.replace(' ', '').split(';'))
    # visualize_diagram_in_png(data)


def test_diagram_for_traffic_light_machine(traffic_light_machine):
    expected = (
        'digraph TrafficLightMachine { labelloc="t"; label="TrafficLightMachine"; '
        'green [color=blue];red;yellow; green -> yellow [label="cycle"];'
        'green -> yellow [label="slowdown"];red -> green [label="cycle"];'
        'red -> green [label="go"];yellow -> red [label="cycle"];yellow -> red [label="stop"]; }'
    )

    data = dot_data_from_machine(traffic_light_machine)
    assert set(data.replace(' ', '').split(';')) == set(expected.replace(' ', '').split(';'))
    # visualize_diagram_in_png(data)
