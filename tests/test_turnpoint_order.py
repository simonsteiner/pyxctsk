"""Test for correct field order in QRCode turnpoints."""

import json

from pyxctsk.qrcode_task import QRCodeTask, QRCodeTurnpoint, QRCodeTurnpointType


def test_turnpoint_field_order():
    """Test that the turnpoint fields are in the correct order."""
    # Create a simple turnpoint with different types
    sss_tp = QRCodeTurnpoint(
        lat=1.23456,
        lon=7.89012,
        radius=400,
        name="SSS",
        alt_smoothed=100,
        type=QRCodeTurnpointType.SSS,
        description="Start of Speed Section",
    )

    # Convert to dictionary
    sss_tp_dict = sss_tp.to_dict()

    # Get the keys in order
    keys = list(sss_tp_dict.keys())

    # Check order for fields: 'd', 'n', 't', 'z' is the expected order
    assert keys.index("d") < keys.index("n"), "Description should come before name"
    assert keys.index("n") < keys.index("t"), "Name should come before type"
    assert keys.index("t") < keys.index("z"), "Type should come before coordinates"

    # Create a turnpoint with ESS type
    ess_tp = QRCodeTurnpoint(
        lat=2.34567,
        lon=8.90123,
        radius=1000,
        name="ESS",
        alt_smoothed=200,
        type=QRCodeTurnpointType.ESS,
        description="End of Speed Section",
    )

    # Convert to dictionary
    ess_tp_dict = ess_tp.to_dict()
    keys = list(ess_tp_dict.keys())

    # Check order for ESS turnpoint
    assert keys.index("t") < keys.index(
        "z"
    ), "Type should come before coordinates in ESS"

    # Create a QRCode task with turnpoints that have types
    qr_task = QRCodeTask(turnpoints=[sss_tp, ess_tp])

    # Convert to JSON and parse back to check if structure is preserved
    task_json = qr_task.to_json()
    task_dict = json.loads(task_json)

    # Check if the turnpoint fields are in correct order
    assert "t" in task_dict, "Task should have turnpoints"
    assert len(task_dict["t"]) == 2, "Task should have 2 turnpoints"

    # Check SSS turnpoint
    sss_tp_json = task_dict["t"][0]
    sss_keys = list(sss_tp_json.keys())
    assert sss_keys.index("t") < sss_keys.index(
        "z"
    ), "Type should come before z in SSS turnpoint"

    # Check ESS turnpoint
    ess_tp_json = task_dict["t"][1]
    ess_keys = list(ess_tp_json.keys())
    assert ess_keys.index("t") < ess_keys.index(
        "z"
    ), "Type should come before z in ESS turnpoint"

    # Test with actual example from the spec
    spec_example = """{"g":{"d":"22:00:00Z","t":2},"s":{"d":2,"g":["17:00:00Z"],"t":1},"t":[{"d":"Take--Off--AGUAPANELA","n":"D02","t":1,"z":"b`dpMgc{YgsB_X"},{"d":"PUENTE ZARZAL - LA PAILA","n":"P31","t":2,"z":"xthoM}orYcy@owH"},{"d":"ZANJAS LA UNION","n":"P32","z":"tmeoMgjtZuw@gxG"},{"d":"ANTENAS ROLDANILLO","n":"P09","z":"trvoMquwYydA_|B"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@oK"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@otL"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@oK"},{"d":"X24","n":"X24","z":"|ltnMkgxWu`Co_h@"},{"d":"GOL PISTA-LOS CHANCOS","n":"G11","t":3,"z":"|kbpMuvnWe}@ozD"},{"d":"GOL PISTA-LOS CHANCOS","n":"G11","z":"|kbpMuvnWe}@oK"}],"taskType":"CLASSIC","tc":null,"to":null,"version":2}"""

    # Parse the example and check if our code can parse it correctly
    qr_task_from_spec = QRCodeTask.from_json(spec_example)

    # Generate JSON from the parsed task and compare with the spec
    generated_json = qr_task_from_spec.to_json()
    generated_dict = json.loads(generated_json)
    spec_dict = json.loads(spec_example)

    # Check turnpoints field ordering
    for i, tp in enumerate(spec_dict["t"]):
        if "t" in tp:
            gen_tp = generated_dict["t"][i]
            gen_keys = list(gen_tp.keys())
            if "t" in gen_tp:
                assert gen_keys.index("t") < gen_keys.index(
                    "z"
                ), f"Type should come before z in turnpoint {i}"
