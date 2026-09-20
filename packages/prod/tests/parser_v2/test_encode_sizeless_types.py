"""Integration regression for the size_in_bit gate over sizeless parameter types.

Five value types carry no ``size_in_bit`` XML attribute because their encoding fixes
the width: Float, Date, IPAddress, Color and RawData. The memory/property writers used
to gate on a plain ``getattr(tc, "size_in_bit", None)``, which returned ``None`` for all
five, so every such parameter was silently skipped and its cells were left at the segment
seed - a wrong device image. These tests drive each type end to end through
``encode_to_memory`` (the actual write path, not just ``_encode_value`` in isolation) and
assert the bytes are written and round-trip through ``decode_memory_parameters``.
"""

from __future__ import annotations

import pytest

from xknxeditor.namespaces.intermediate import ApplicationProgram
from xknxeditor.namespaces.intermediate.application_program_static_t import (
    ApplicationProgramStatic,
)
from xknxeditor.namespaces.intermediate.application_program_static_t_code import (
    ApplicationProgramStaticCode,
)
from xknxeditor.namespaces.intermediate.application_program_static_t_code_absolute_segment import (
    ApplicationProgramStaticCodeAbsoluteSegment,
)
from xknxeditor.namespaces.intermediate.application_program_static_t_parameter_types import (
    ApplicationProgramStaticParameterTypes,
)
from xknxeditor.namespaces.intermediate.application_program_static_t_parameters import (
    ApplicationProgramStaticParameters,
)
from xknxeditor.namespaces.intermediate.application_program_static_t_parameters_parameter import (
    ApplicationProgramStaticParametersParameter,
)
from xknxeditor.namespaces.intermediate.application_program_type_t import (
    ApplicationProgramType,
)
from xknxeditor.namespaces.intermediate.load_procedure_style_t import LoadProcedureStyle
from xknxeditor.namespaces.intermediate.memory_parameter_t import MemoryParameter
from xknxeditor.namespaces.intermediate.parameter_type_t import ParameterType
from xknxeditor.namespaces.intermediate.parameter_type_t_type_color import (
    ParameterTypeTypeColor,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_color_space import (
    ParameterTypeTypeColorSpace,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_date import (
    ParameterTypeTypeDate,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_date_encoding import (
    ParameterTypeTypeDateEncoding,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_float import (
    ParameterTypeTypeFloat,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_float_encoding import (
    ParameterTypeTypeFloatEncoding,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_ipaddress import (
    ParameterTypeTypeIpaddress,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_ipaddress_address_type import (
    ParameterTypeTypeIpaddressAddressType,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_ipaddress_version import (
    ParameterTypeTypeIpaddressVersion,
)
from xknxeditor.namespaces.intermediate.parameter_type_t_type_raw_data import (
    ParameterTypeTypeRawData,
)
from xknxeditor.prod.errors import EncodingError
from xknxeditor.prod.parser_v2.application_indexer import ApplicationIndexer
from xknxeditor.prod.parser_v2.encode import (
    decode_memory_parameters,
    encode_to_memory,
    encode_to_memory_masked,
    written_bit_mask,
)

_PT_ID = "PT1"
_SEG_ID = "SEG1"


def _app(
    choice: object, value: str, seg_size: int = 32, seg_data: bytes | None = None
) -> tuple[ApplicationProgram, ApplicationIndexer]:
    """Build a one-segment app with a single memory parameter of the given type."""
    param = ApplicationProgramStaticParametersParameter(
        id="P1",
        name="",
        text="",
        parameter_type=_PT_ID,
        value=value,
        choice=MemoryParameter(code_segment=_SEG_ID, offset=0, bit_offset=0),
    )
    app = ApplicationProgram(
        id="APP",
        name="",
        application_number=1,
        application_version=1,
        program_type=ApplicationProgramType.APPLICATION_PROGRAM,
        mask_version="BV20",
        load_procedure_style=LoadProcedureStyle.DEFAULT_PROCEDURE,
        pei_type=0,
        default_language="en",
        dynamic_table_management=False,
        linkable=False,
        static=ApplicationProgramStatic(
            code=ApplicationProgramStaticCode(
                absolute_segment=[
                    ApplicationProgramStaticCodeAbsoluteSegment(
                        id=_SEG_ID, size=seg_size, address=0, data=seg_data
                    )
                ]
            ),
            parameter_types=ApplicationProgramStaticParameterTypes(
                parameter_type=[ParameterType(id=_PT_ID, name="T", choice=choice)]  # type: ignore[arg-type]
            ),
            parameters=ApplicationProgramStaticParameters(choice=[param]),
        ),
    )
    return app, ApplicationIndexer(app)


def test_float_dpt9_written_to_memory() -> None:
    tc = ParameterTypeTypeFloat(
        encoding=ParameterTypeTypeFloatEncoding.DPT_9, min_inclusive=0, max_inclusive=0
    )
    app, idx = _app(tc, "21.0")
    mem = encode_to_memory(app, idx, {})
    assert mem[_SEG_ID][0:2] == b"\x0c\x1a"  # 0x0C1A, not left at the seed
    assert decode_memory_parameters(app, idx, {_SEG_ID: mem[_SEG_ID]})["P1"] == "21.0"


def test_date_dpt11_written_to_memory() -> None:
    tc = ParameterTypeTypeDate(
        encoding=ParameterTypeTypeDateEncoding.DPT_11, display_the_year=True
    )
    app, idx = _app(tc, "2024-03-15")
    mem = encode_to_memory(app, idx, {})
    assert mem[_SEG_ID][0:3] == b"\x0f\x03\x18"  # day 15, month 3, year 24
    assert (
        decode_memory_parameters(app, idx, {_SEG_ID: mem[_SEG_ID]})["P1"]
        == "2024-03-15"
    )


def test_ipaddress_v4_written_to_memory() -> None:
    tc = ParameterTypeTypeIpaddress(
        address_type=ParameterTypeTypeIpaddressAddressType.HOST_ADDRESS,
        version=ParameterTypeTypeIpaddressVersion.IPV4,
    )
    app, idx = _app(tc, "192.168.1.10")
    mem = encode_to_memory(app, idx, {})
    assert mem[_SEG_ID][0:4] == bytes([192, 168, 1, 10])
    assert (
        decode_memory_parameters(app, idx, {_SEG_ID: mem[_SEG_ID]})["P1"]
        == "192.168.1.10"
    )


def test_color_rgb_written_to_memory() -> None:
    tc = ParameterTypeTypeColor(space=ParameterTypeTypeColorSpace.RGB)
    app, idx = _app(tc, "#0A0B0C")
    mem = encode_to_memory(app, idx, {})
    assert mem[_SEG_ID][0:3] == b"\x0a\x0b\x0c"
    assert (
        decode_memory_parameters(app, idx, {_SEG_ID: mem[_SEG_ID]})["P1"] == "#0A0B0C"
    )


def test_raw_data_written_to_memory() -> None:
    tc = ParameterTypeTypeRawData(max_size=16)
    app, idx = _app(tc, "Cgs=")  # base64 of b"\x0a\x0b"
    mem = encode_to_memory(app, idx, {})
    # 4-octet big-endian length prefix + payload. MaxSize bounds the payload (16 octets);
    # the KNX standard reserves +4 for the prefix, so the field is 20 octets total. Only
    # the prefix and the real payload are written; the reserved tail stays at the seed.
    assert mem[_SEG_ID][0:6] == b"\x00\x00\x00\x02\x0a\x0b"
    assert all(b == 0 for b in mem[_SEG_ID][6:20])
    assert decode_memory_parameters(app, idx, {_SEG_ID: mem[_SEG_ID]})["P1"] == "Cgs="


def test_raw_data_leaves_reserved_tail_at_seed() -> None:
    # Past the prefix+payload the field is NOT zero-filled: the reserved tail keeps the
    # segment seed. A non-zero seed makes the distinction observable (a zero seed would
    # hide it) and matches the KNX standard, which writes only the real payload length.
    tc = ParameterTypeTypeRawData(max_size=16)
    seed = bytes(range(1, 21))  # 20 non-zero octets, one per field byte
    app, idx = _app(tc, "Cgs=", seg_size=20, seg_data=seed)
    mem = encode_to_memory(app, idx, {})
    assert mem[_SEG_ID][0:6] == b"\x00\x00\x00\x02\x0a\x0b"  # prefix + payload written
    assert mem[_SEG_ID][6:20] == seed[6:20]  # reserved tail untouched (still the seed)


def test_raw_data_mask_covers_only_prefix_and_payload() -> None:
    # The write mask marks only the prefix+payload as written, so a partial download does
    # not overwrite the reserved tail with zeros (which over-reported the change extent).
    tc = ParameterTypeTypeRawData(max_size=16)
    app, idx = _app(tc, "Cgs=", seg_size=20)
    data, mask = encode_to_memory_masked(app, idx, {})[_SEG_ID]
    assert data[0:6] == b"\x00\x00\x00\x02\x0a\x0b"
    assert mask[0:6] == b"\xff" * 6
    assert mask[6:20] == b"\x00" * 14  # reserved tail not marked written


def test_raw_data_bit_mask_covers_only_prefix_and_payload() -> None:
    # The bit-granular mask (used by pre-flight to tell parameter bits apart from restored
    # seed bits) must also narrow to prefix+payload, not the full reserved field. Otherwise
    # pre-flight reports the untouched reserved tail as parameter-controlled.
    tc = ParameterTypeTypeRawData(max_size=16)  # 20 octet field
    app, idx = _app(tc, "Cgs=", seg_size=20)  # 2-octet payload -> 6 octets written
    mask = written_bit_mask(app, idx, {})[_SEG_ID]
    assert mask[0:6] == b"\xff" * 6  # every prefix+payload bit driven
    assert mask[6:20] == b"\x00" * 14  # reserved tail not marked


def test_raw_data_truncated_segment_is_skipped_not_fabricated() -> None:
    # A segment shorter than the field must not be decoded: _read_bits would zero-fill the
    # missing octets and fabricate a plausible RawData value. The decoder skips the field
    # (as decode_property_parameters already does) rather than inventing bytes.
    tc = ParameterTypeTypeRawData(max_size=16)  # 20 octet field
    app, idx = _app(tc, "Cgs=")
    decoded = decode_memory_parameters(app, idx, {_SEG_ID: b"\x00\x00"})
    assert "P1" not in decoded


def test_unencodable_value_raises_instead_of_skipping() -> None:
    # A value that cannot encode against its declared type is corrupt data; the writer
    # must fail loudly rather than emit a partial image that gets programmed to a device.
    tc = ParameterTypeTypeFloat(
        encoding=ParameterTypeTypeFloatEncoding.DPT_9, min_inclusive=0, max_inclusive=0
    )
    app, idx = _app(tc, "not-a-float")
    with pytest.raises(EncodingError):
        encode_to_memory(app, idx, {})
