import asyncio
import logging
from datetime import datetime
import signal

try:
    import websockets
except ModuleNotFoundError:
    print("This example relies on the 'websockets' package.")
    print("Please install it by running: ")
    print()
    print(" $ pip install websockets")
    import sys
    sys.exit(1)

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus

logging.basicConfig(level=logging.INFO)

# Dictionary to store connected charge points for persistence
charge_points = {}


class ChargePoint(cp):
    @on(Action.BootNotification)
    def on_boot_notification(self, charge_point_vendor: str, charge_point_model: str, **kwargs):
        logging.info(f"BootNotification from {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotification(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    @on(Action.Heartbeat)
    def on_heartbeat(self):
        logging.info("Received Heartbeat")
        return call_result.Heartbeat(current_time=datetime.utcnow().isoformat())

    @on(Action.Authorize)
    def on_authorize(self, id_tag: str):
        logging.info(f"Authorize request for ID Tag: {id_tag}")
        # Example handling of authorization
        return call_result.Authorize(id_tag_info={"status": "Accepted"})

    # Additional handlers for StartTransaction, StopTransaction, etc.


async def on_connect(websocket, path):
    """For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """
    try:
        requested_protocols = websocket.request_headers["Sec-WebSocket-Protocol"]
        if websocket.subprotocol:
            logging.info("Protocols Matched: %s", websocket.subprotocol)
        else:
            logging.warning(
                "Protocols Mismatched | Expected Subprotocols: %s, but client supports %s | Closing connection",
                websocket.available_subprotocols,
                requested_protocols,
            )
            return await websocket.close()

        charge_point_id = path.strip("/")
        cp = ChargePoint(charge_point_id, websocket)

        # Store connected charge point in a dictionary
        charge_points[charge_point_id] = cp

        await cp.start()

    except websockets.exceptions.ConnectionClosed as e:
        logging.error("Connection closed with exception: %s", e)
    except Exception as e:
        logging.exception("An unexpected error occurred: %s", e)
    finally:
        # Remove charge point from storage on disconnect
        if charge_point_id in charge_points:
            del charge_points[charge_point_id]


async def main():
    server = await websockets.serve(
        on_connect, "0.0.0.0", 9000, subprotocols=["ocpp1.6"]
    )

    logging.info("Server started listening to new connections...")

    # Setup signal handler for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.close()))

    await server.wait_closed()

if __name__ == "__main__":
    # asyncio.run() is used when running this example with Python >= 3.7v
    asyncio.run(main())
