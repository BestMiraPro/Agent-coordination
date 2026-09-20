from uuid import uuid4

from packages.core.domain.models import (
    CrossPollinationKind,
    CrossPollinationPacket,
)


def test_cross_pollination_packet_is_explicit_and_targeted() -> None:
    packet = CrossPollinationPacket(
        run_id=uuid4(),
        generation_id=uuid4(),
        target_agent_id=uuid4(),
        source_submission_id=uuid4(),
        kind=CrossPollinationKind.TRY,
        payload={
            "summary": "Alternative combinatorial route",
            "discoveries": ["small cases suggest parity structure"],
        },
    )

    assert packet.kind == CrossPollinationKind.TRY
    assert packet.target_agent_id != packet.source_submission_id
    assert "summary" in packet.payload
