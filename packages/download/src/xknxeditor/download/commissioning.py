"""Program a device's individual address before downloading an application.

A virgin device (or one whose address is unknown) has to be given its individual
address first. Two ways are supported, both delegating to ``xknx``'s network
management procedures:

- via programming mode: exactly one device on the bus must be in programming
  mode; its address is written by broadcast.
- via serial number: the target device is addressed by its serial number, so no
  programming mode is required and several devices may be on the bus.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from xknx.exceptions import ManagementConnectionError
from xknx.management.procedures.device.dm_restart_r_co import dm_restart_r_co
from xknx.management.procedures.network.nm_individual_address_check import (
    nm_individual_address_check_conn,
)
from xknx.management.procedures.network.nm_individual_address_read import (
    nm_individual_address_read,
)
from xknx.management.procedures.network.nm_individual_address_serial_number_write import (
    nm_individual_address_serial_number_write,
)
from xknx.telegram import apci
from xknx.telegram.address import IndividualAddress

if TYPE_CHECKING:
    from xknx import XKNX
    from xknx.telegram.address import IndividualAddressableType

logger = logging.getLogger(__name__)

# Individual address of a factory-fresh / unprogrammed device.
DEFAULT_INDIVIDUAL_ADDRESS = IndividualAddress("15.15.255")

# Wait after writing the address before verifying it, so the device has adopted it.
_ADDRESS_ADOPTION_DELAY_S = 1.0


async def program_individual_address(
    xknx: XKNX,
    individual_address: IndividualAddressableType,
    *,
    serial_number: bytes | None = None,
) -> None:
    """Program ``individual_address`` into a device.

    With ``serial_number`` the device is addressed by serial number; otherwise
    the single device currently in programming mode is addressed. ``xknx`` has to
    be started.
    """
    address = IndividualAddress(individual_address)
    if serial_number is not None:
        await nm_individual_address_serial_number_write(xknx, serial_number, address)
        return
    await _write_address_via_programming_mode(xknx, address)


async def _write_address_via_programming_mode(
    xknx: XKNX, address: IndividualAddress
) -> None:
    """Write ``address`` to the single device in programming mode, without restarting it.

    The device keeps its new address and stays reachable, so a following
    application download can connect immediately. xknx's
    :func:`nm_individual_address_write` restarts the device at this point (via
    ``dm_restart_r_co``), which leaves it briefly unreachable and races the
    download's first point-to-point connect ("No ACK received"). The address is
    therefore written directly and the device is left running. Occupancy is not
    re-checked here: commissioning only runs when no device already answers at
    ``address``.
    """
    devices = await nm_individual_address_read(xknx, raise_if_multiple=True)
    if not devices:
        raise ManagementConnectionError("No device in programming mode detected.")

    await xknx.management.send_broadcast(
        payload=apci.IndividualAddressWrite(address=address),
    )
    logger.debug("Wrote address %s to the device in programming mode.", address)

    # Give the device time to adopt its new address before the verifying connect;
    # connecting too soon races the device and yields "No ACK received".
    await asyncio.sleep(_ADDRESS_ADOPTION_DELAY_S)

    async with xknx.management.connection(address=address) as connection:
        if not await nm_individual_address_check_conn(connection):
            raise ManagementConnectionError(
                f"No device answered at {address} after the address write."
            )


async def reset_individual_address(xknx: XKNX) -> None:
    """Reset the individual address of the single device in programming mode to
    the default (15.15.255), returning it to the unprogrammed state.

    Exactly one device must be in programming mode. ``xknx`` has to be started.

    This does not go through :func:`nm_individual_address_write`: that procedure
    first checks whether the target address is occupied and aborts on a conflict,
    but the default address is the "unprogrammed" marker and answers/refuses on
    many buses, so the check misfires. The address is written directly instead.
    """
    devices = await nm_individual_address_read(xknx, raise_if_multiple=True)
    if not devices:
        raise ManagementConnectionError("No device in programming mode detected.")

    await xknx.management.send_broadcast(
        payload=apci.IndividualAddressWrite(address=DEFAULT_INDIVIDUAL_ADDRESS),
    )
    logger.debug("Reset device %s to the default address.", devices[0])

    # Restart the device to leave programming mode. Writing the address above is
    # the essential step, so a restart that does not complete is not fatal.
    with contextlib.suppress(ManagementConnectionError):
        async with xknx.management.connection(
            address=DEFAULT_INDIVIDUAL_ADDRESS
        ) as connection:
            await dm_restart_r_co(connection)
