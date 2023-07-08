import argparse
import logging
from mserv.services.samples import MessageGenerator, MessageLogger
from mserv.socketlib import (
    Client,
    ClientReceiver,
    ClientSender,
    Server,
    ServerReceiver,
    ServerSender,
)
from mserv.utils.logger import get_module_logger


def start_socket(
        address: tuple[str, int],
        client: bool,
        sock_type: str,
        reconnect: bool,
        logger: logging.Logger
) -> None:
    valid_types = ["multi", "receiver", "sender"]
    if client and sock_type == "client":
        sock_type = "multi"
    elif not client and sock_type == "server":
        sock_type = "multi"

    if sock_type not in valid_types:
        raise ValueError(f"Unexpected type {sock_type}")

    msg_logger = None
    msg_gen = None
    name = "Client" if client else "Server"

    if sock_type == "multi":
        if client:
            socket = Client(address, reconnect=reconnect, logger=logger)
        else:
            socket = Server(address, reconnect=reconnect, logger=logger)
        msg_logger = MessageLogger(socket.received, logger)
        msg_gen = MessageGenerator(socket.to_send, name, logger)

    elif sock_type == "receiver":
        if client:
            socket = ClientReceiver(address, reconnect=reconnect, logger=logger)
        else:
            socket = ServerReceiver(address, reconnect=reconnect, logger=logger)
        msg_logger = MessageLogger(socket.received, logger)

    elif sock_type == "sender":
        if client:
            socket = ClientSender(address, reconnect=reconnect, logger=logger)
        else:
            socket = ServerSender(address, reconnect=reconnect, logger=logger)
        msg_gen = MessageGenerator(socket.to_send, name, logger)

    else:
        raise ValueError(f"Unexpected type {sock_type}")

    with socket:
        if isinstance(socket,
                      (Client, ClientReceiver, ClientSender)):
            socket.connect()

        socket.start()
        if msg_logger is not None:
            msg_logger.start()

        if msg_gen is not None:
            msg_gen.start()

        try:
            socket.join()
        except KeyboardInterrupt:
            socket.shutdown()
            if msg_logger is not None:
                msg_logger.shutdown()
            if msg_gen is not None:
                msg_gen.shutdown()

    logger.info("Graceful shutdown")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a socket client or a socket server")

    parser.add_argument(
        "--ip",
        "-i",
        type=str,
        default="localhost",
        help="The ip where the client will connect or where the server will connect"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=12345,
        help="The port where the client will connect or where the server will connect"
    )
    parser.add_argument(
        "--server",
        "-s",
        action="store_true",
        help="If this flag is passed a server will be started. If not a client"
    )
    parser.add_argument(
        "--type",
        "-t",
        type=str,
        choices=["multi", "receiver", "sender"],
        default="multi",
        help="The type of the server or client. Can be multi, receiver or sender"
    )
    parser.add_argument(
        "--reconnect",
        "-r",
        action="store_true",
        help="Whether the client or server should try to reconnect if the connection is lost"
    )

    args = parser.parse_args()
    address = (args.ip, args.port)
    return address, args.server, args.type, args.reconnect


def main():
    address, server, sock_type, reconnect = parse_args()
    logger = get_module_logger(__name__, config="dev", use_file_handler=False)
    start_socket(
        address,
        client=not server,
        sock_type=sock_type,
        reconnect=reconnect,
        logger=logger
    )


if __name__ == "__main__":
    main()