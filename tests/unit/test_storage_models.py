from sqlalchemy import UniqueConstraint
from vda_platform.storage import ConversationMember, Message


def test_storage_models_encode_message_and_membership_idempotency_constraints() -> None:
    message_constraints = {
        constraint.name
        for constraint in Message.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    member_constraints = {
        constraint.name
        for constraint in ConversationMember.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert any(
        {"conversation_id", "sender_id", "client_message_id"}.issubset(
            {column.name for column in constraint.columns}
        )
        for constraint in Message.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert member_constraints
    assert message_constraints
