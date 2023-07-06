import queue
import logging
import socket
import threading
from typing import Callable, Optional

from mserv.socketlib.buffer import Buffer
from mserv.socketlib.receive import receive_msg
from mserv.socketlib.send import send_msg


class ServerBase:
    """ Parent class for other server classes that implements some common methods.

        This class should not be instantiated.
    """

    def __init__(
            self,
            address: tuple[str, int],
            reconnect: bool = True,
            stop: Optional[Callable[[], bool]] = lambda: False,
            logger: Optional[logging.Logger] = None,
    ):
        self._address = address
        self._socket = None
        self._connection = None  # The client connection
        self._conn_details = None
        self._stop = stop

        self._reconnect = reconnect
        self._logger = logger

        self._run_thread = threading.Thread()

    @property
    def ip(self) -> str:
        return self._address[0]

    @property
    def port(self) -> int:
        return self._address[1]

    def listen(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(self._address)
        self._socket.listen()

    def accept_connection(self) -> None:
        self._connection, self._conn_details = self._socket.accept()
        if self._logger is not None:
            self._logger.info(
                f"{self.__class__.__name__}: "
                f"connection accepted from {self._conn_details}"
            )

    def start(self) -> None:
        self.listen()
        self._run_thread.start()

    def join(self) -> None:
        self._run_thread.join()

    def shutdown(self) -> None:
        self._stop = lambda: True
        self.join()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._connection is not None:
            self._connection.close()
        if self._socket is not None:
            self._socket.close()


class ServerReceiver(ServerBase):
    """ A server that receives messages from a single client.
    """
    def __init__(
            self,
            address: tuple[str, int],
            received: Optional[queue.Queue[bytes]] = None,
            reconnect: bool = True,
            stop: Optional[Callable[[], bool]] = lambda: False,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(address, reconnect, stop, logger)
        self.msg_end = b"\r\n"
        self._buffer = None  # type: Buffer
        self._received = received if received is not None else queue.Queue()
        self._run_thread = threading.Thread(
            target=self._recv, daemon=True
        )

    @property
    def received(self) -> queue.Queue[bytes]:
        return self._received

    def accept_connection(self) -> None:
        super().accept_connection()
        self._buffer = Buffer(self._connection)

    def _recv(self):
        self.accept_connection()
        receive_msg(
            self._buffer,
            self._received,
            self._stop,
            self.msg_end,
            self._logger,
        )

    def start_main_thread(self) -> None:
        self.listen()
        self._recv()


class ServerSender(ServerBase):
    """ A server that sends messages to a single client"""

    def __init__(
            self,
            address: tuple[str, int],
            to_send: Optional[queue.Queue[str]] = None,
            reconnect: bool = True,
            stop: Optional[Callable[[], bool]] = lambda: False,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(address, reconnect, stop, logger)
        self.msg_end = b"\r\n"
        self._to_send = to_send if to_send is not None else queue.Queue()
        self._run_thread = threading.Thread(
            target=self._send, daemon=True
        )

    @property
    def to_send(self) -> queue.Queue[str]:
        return self._to_send

    def start_main_thread(self) -> None:
        self.listen()
        self._send()

    def _send(self):
        self.accept_connection()
        send_msg(
            self._connection,
            self._to_send,
            self._stop,
            self.msg_end,
            self._logger
        )


class Server(ServerBase):
    """ A server that sends and receives messages to and from a single client.
    """

    def __init__(
            self,
            address: tuple[str, int],
            received: Optional[queue.Queue[bytes]] = None,
            to_send: Optional[queue.Queue[str]] = None,
            reconnect: bool = True,
            stop_receive: Optional[Callable[[], bool]] = lambda: False,
            stop_send: Optional[Callable[[], bool]] = lambda: False,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__(address, reconnect, logger=logger)
        self.msg_end = b"\r\n"
        self._buffer = None  # type: Optional[Buffer]

        self._received = received if received is not None else queue.Queue()
        self._to_send = to_send if to_send is not None else queue.Queue()
        self._stop_receive = stop_receive
        self._stop_send = stop_send

        self._send_thread = threading.Thread(target=self._send, daemon=True)
        self._recv_thread = threading.Thread(target=self._recv, daemon=True)
        self._wait_for_conn = threading.Event()

    @property
    def to_send(self) -> queue.Queue[str]:
        return self._to_send

    @property
    def received(self) -> queue.Queue[bytes]:
        return self._received

    @property
    def send_thread(self) -> threading.Thread:
        return self._send_thread

    @property
    def receive_thread(self) -> threading.Thread:
        return self._recv_thread

    def _send(self) -> None:
        self._wait_for_conn.wait()
        send_msg(
            self._connection,
            self._to_send,
            self._stop_send,
            self.msg_end,
            self._logger,
            self.__class__.__name__
        )

    def _recv(self):
        self._wait_for_conn.wait()
        receive_msg(
            self._buffer,
            self._received,
            self._stop_receive,
            self.msg_end,
            self._logger,
            self.__class__.__name__
        )

    def accept_connection(self) -> None:
        super().accept_connection()
        self._buffer = Buffer(self._connection)
        self._wait_for_conn.set()

    def start(self) -> None:
        """ Start this server in a new thread. """
        self.listen()
        accept = threading.Thread(target=self.accept_connection, daemon=True)
        accept.start()
        self._recv_thread.start()
        self._send_thread.start()

    def join(self) -> None:
        self._recv_thread.join()
        self._send_thread.join()

    def shutdown(self) -> None:
        self._stop_send = lambda: True
        self._stop_receive = lambda: True
        self.join()
