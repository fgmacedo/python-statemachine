import pytest


@pytest.fixture()
def async_order_control_machine():
    from tests.examples.async_order_control_machine import OrderControl

    return OrderControl()


async def test_async_order_control_machine(async_order_control_machine):
    sm = async_order_control_machine

    assert await sm.async_add_to_order(3) == 3
    assert await sm.async_add_to_order(7) == 10

    assert await sm.async_receive_payment(4) == [4]
    assert sm.waiting_for_payment.is_active

    with pytest.raises(sm.TransitionNotAllowed):
        await sm.async_process_order()

    assert sm.waiting_for_payment.is_active

    assert await sm.async_receive_payment(6) == [4, 6]
    await sm.async_process_order()

    await sm.async_ship_order()
    assert sm.order_total == 10
    assert sm.payments == [4, 6]
    assert sm.completed.is_active
