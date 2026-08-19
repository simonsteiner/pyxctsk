"""The front door's format adapters, each asked its two questions on its own.

`parser.py` has always said its adapters are "testable in isolation". Until the
recognition question existed there was nothing to test in isolation — an
adapter could only be exercised through `parse_task`, and "not my format" was
indistinguishable from "my format, malformed". These tests are what that claim
was supposed to mean.

The behaviour they pin is the defect the recognition question removed: the QR
JSON adapter accepted *any* JSON object, so every full-format `.xctsk` document
was also a valid input to it, and only the adapters' order kept the two apart.
"""

import json

import pytest

from pyxctsk import InvalidFormatError, parse_task
from pyxctsk.parser import (
    FORMAT_ADAPTERS,
    FULL_FORMAT_ONLY_KEYS,
    QR_FORMAT_ONLY_KEYS,
    Input,
)
from tests.corpus import reference_task, reference_tasks


def _adapter(name):
    """The adapter under test, by the name it publishes."""
    return next(a for a in FORMAT_ADAPTERS if a.name == name)


class TestExactlyOneAdapterRecognizesAPayload:
    """The property that makes the adapters' order a tie-break, not a guard."""

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_every_corpus_payload_is_claimed_once(self, reference):
        """One task in four spellings; each is exactly one adapter's."""
        qr = reference.task.to_qr_code_task()
        payloads = {
            "XCTSK: URL": qr.to_string(),
            "task JSON": reference.task.to_json(),
            "QR JSON": qr.to_json(),
        }
        for expected, payload in payloads.items():
            inp = Input.of(payload)
            claimed = [a.name for a in FORMAT_ADAPTERS if a.recognizes(inp)]
            assert claimed == [expected], payload[:80]

    def test_the_compressed_scheme_is_the_url_adapters_too(self):
        """XCTSKZ: is base64, so no other adapter may recognize it."""
        payload = (
            reference_task("task_bevo")
            .task.to_qr_code_task()
            .to_string(compressed=True)
        )
        inp = Input.of(payload)

        assert [a.name for a in FORMAT_ADAPTERS if a.recognizes(inp)] == ["XCTSK: URL"]

    def test_a_qr_image_is_only_the_image_adapters(self, tmp_path):
        """Binary input decodes as no text, so no text adapter sees it."""
        from pyxctsk import generate_qrcode_image

        qr_string = reference_task("task_bevo").task.to_qr_code_task().to_string()
        png = tmp_path / "task.png"
        generate_qrcode_image(qr_string, size=512).save(png)

        inp = Input.of(png.read_bytes())

        assert [a.name for a in FORMAT_ADAPTERS if a.recognizes(inp)] == ["QR image"]


class TestTheQrJsonAdapterNoLongerAcceptsEverything:
    """`_parse_qrcode_json` was a total function on JSON objects.

    A ten-turnpoint competition task read as a task with *zero* turnpoints and
    its whole content in `unknown`, and the only thing preventing it was the
    full-format adapter sitting one line earlier in the tuple.
    """

    def test_a_full_format_document_is_not_a_qr_payload(self):
        """The corpus task the over-acceptance was demonstrated on."""
        inp = Input.of(reference_task("task_bevo").task.to_json())

        assert not _adapter("QR JSON").recognizes(inp)
        assert _adapter("task JSON").recognizes(inp)

    def test_a_qr_payload_is_not_a_full_format_document(self):
        """And the converse, which was already true and now is checked."""
        inp = Input.of(reference_task("task_bevo").task.to_qr_code_task().to_json())

        assert not _adapter("task JSON").recognizes(inp)
        assert _adapter("QR JSON").recognizes(inp)

    @pytest.mark.parametrize(
        "payload", ["{}", '{"hello":"world"}', '{"taskType":"CLASSIC","version":2}']
    )
    def test_a_json_object_that_is_neither_is_refused(self, payload):
        """It used to be read as a task, and written back out as one."""
        with pytest.raises(InvalidFormatError, match="not a task in any format"):
            parse_task(payload)

    def test_the_order_would_no_longer_matter(self):
        """Reversing the tuple changes nothing, because at most one claims it."""
        for reference in reference_tasks():
            for payload in (
                reference.task.to_json(),
                reference.task.to_qr_code_task().to_json(),
            ):
                inp = Input.of(payload)
                assert sum(a.recognizes(inp) for a in FORMAT_ADAPTERS) == 1


class TestTheKeySetsAreDerived:
    """Listing them here is how a recognizer comes to claim a key nothing reads."""

    def test_the_two_sets_are_disjoint(self):
        """Two adapters claiming one key is the ambiguity order used to hide."""
        assert not (FULL_FORMAT_ONLY_KEYS & QR_FORMAT_ONLY_KEYS)

    def test_they_are_what_the_shapes_declare(self):
        """Derived, not listed — the reason ``KNOWN_KEYS`` is derived too."""
        from pyxctsk.model.task import TASK_SHAPE
        from pyxctsk.qrcode.task import QR_TASK_SHAPE, QR_WAYPOINTS_TASK_SHAPE

        qr_keys = QR_TASK_SHAPE.keys | QR_WAYPOINTS_TASK_SHAPE.keys

        assert FULL_FORMAT_ONLY_KEYS == TASK_SHAPE.keys - qr_keys
        assert QR_FORMAT_ONLY_KEYS == qr_keys - TASK_SHAPE.keys
        # The overlap is real and is why "only" is in both names.
        assert TASK_SHAPE.keys & qr_keys == {"taskType", "version"}


class TestARecognizedPayloadThatCannotBeReadSaysSo:
    """It used to fall through to an adapter whose format it is not."""

    def test_a_malformed_full_format_document(self):
        """``turnpoints`` is present but is not a list of turnpoints."""
        payload = json.dumps({"taskType": "CLASSIC", "version": 1, "turnpoints": 7})

        with pytest.raises(InvalidFormatError, match="recognized the task JSON format"):
            parse_task(payload)

    def test_a_malformed_qr_document(self):
        """A ``z`` polyline that is not one; the QR adapter owns saying so."""
        payload = json.dumps({"taskType": "CLASSIC", "version": 2, "t": [{"z": "!!"}]})

        with pytest.raises(InvalidFormatError, match="recognized the QR JSON format"):
            parse_task(payload)

    @pytest.mark.parametrize("payload", ["[]", "[1,2,3]", "null", '"x"'])
    def test_json_that_is_not_an_object_is_a_format_error(self, payload):
        """These left the library as a bare ``TypeError``, past the CLI."""
        with pytest.raises(InvalidFormatError):
            parse_task(payload)


class TestInputIsDecodedOnce:
    """The value that removed three dead parameters and two extra json.loads."""

    def test_bytes_and_text_agree(self):
        """One payload, two argument types, one decoding."""
        payload = reference_task("task_bevo").task.to_json()

        assert Input.of(payload).document == Input.of(payload.encode()).document

    def test_binary_input_has_no_text(self):
        """Which is how the text adapters decline an image without trying."""
        inp = Input.of(b"\x89PNG\r\n\x1a\n\xff\xfe")

        assert inp.text is None and inp.keys == frozenset()

    def test_a_json_null_is_not_the_same_as_not_json(self):
        """``None`` is a document; the sentinel is the absence of one."""
        assert Input.of("null").looks_like_json
        assert not Input.of("not json at all").looks_like_json
