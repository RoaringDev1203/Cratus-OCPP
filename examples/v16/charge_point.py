import asyncio
import logging
from datetime import datetime

try:
    import websockets
except ModuleNotFoundError:
    print("This example relies on the 'websockets' package.")
    print("Please install it by running: ")
    print()
    print(" $ pip install websockets")
    import sys
    sys.exit(1)

from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call, call_result
from ocpp.v16.enums import RegistrationStatus, Action
from ocpp.routing import on

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.transaction_id = 0  # Example of transaction state

    async def send_boot_notification(self):
        """Send a BootNotification to the Central System to register the charge point."""
        request = call.BootNotificationPayload(
            charge_point_model="Optimus", charge_point_vendor="The Mobility House"
        )

        response = await self.call(request)

        if response.status == RegistrationStatus.accepted:
            logging.info("Connected to central system.")
        elif response.status == RegistrationStatus.pending:
            logging.info("Registration pending. Retrying in 10 seconds...")
            await asyncio.sleep(10)
            await self.send_boot_notification()
        else:
            logging.error("Registration rejected. Check your configuration and try again.")

    async def send_heartbeat(self):
        """Periodically send a heartbeat message to the Central System."""
        while True:
            await asyncio.sleep(300)  # 5 minutes interval
            request = call.HeartbeatPayload()
            response = await self.call(request)
            logging.info(f"Heartbeat sent. Server time: {response.current_time}")

    async def start(self):
        """Start the charge point and initialize communication with the Central System."""
        await asyncio.gather(
            super().start(),
            self.send_boot_notification(),
            self.send_heartbeat(),
        )

    @on(Action.Authorize)
    async def on_authorize(self, id_tag):
        """Handle an Authorize request from the Central System."""
        # Example logic: always accept authorization for demo purposes
        return call_result.AuthorizePayload(id_tag_info={'status': 'Accepted'})

    @on(Action.StartTransaction)
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, reservation_id=None):
        """Handle a StartTransaction request."""
        self.transaction_id += 1  # Increment transaction ID for each transaction
        # Store the transaction or perform any needed operation here
        return call_result.StartTransactionPayload(transaction_id=self.transaction_id, id_tag_info={'status': 'Accepted'})

    @on(Action.StopTransaction)
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, id_tag=None):
        """Handle a StopTransaction request."""
        # Example logic: acknowledge stop transaction
        return call_result.StopTransactionPayload(id_tag_info={'status': 'Accepted'})

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        """Respond to a Heartbeat request from the Central System."""
        return call_result.HeartbeatPayload(current_time=datetime.utcnow().isoformat())

    @on(Action.StatusNotification)
    async def on_status_notification(self, connector_id, status, error_code, **kwargs):
        """Handle a StatusNotification request."""
        # Handle status notification logic here
        logging.info(f"Received status notification: Connector {connector_id} is {status}")
        return call_result.StatusNotificationPayload()


async def main():
    while True:
        try:
            async with websockets.connect(
                "ws://localhost:9000/CP_1", subprotocols=["ocpp1.6"]
            ) as ws:
                charge_point = ChargePoint("CP_1", ws)
                await charge_point.start()
        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError) as e:
            logging.error(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
