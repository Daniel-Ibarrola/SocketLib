import queue
import pytest
from socketlib import (
    Client,
    ClientReceiver,
    ClientSender,
    Server,
    ServerReceiver,
    ServerSender,
)


class TestClientReceiverAndServerSender:

    @pytest.mark.timeout(3)
    def test_client_receives_and_server_sends(self):
        address = ("localhost", 12345)
        received = queue.Queue()
        client = ClientReceiver(
            address,
            received,
            reconnect=False,
            stop=lambda: received.qsize() >= 2
        )

        to_send = queue.Queue()
        server = ServerSender(
            address,
            to_send,
            reconnect=False,
            stop=lambda: to_send.empty()
        )
        server.to_send.put("Hello")
        server.to_send.put("World")

        with server:
            server.start()
            with client:
                client.connect(timeout=1)
                client.start()
                client.join()
            server.join()

        assert server.to_send.empty()
        assert not client.received.empty()
        assert client.received.get() == b"Hello"
        assert client.received.get() == b"World"


class TestClientSenderAndServerReceiver:

    @pytest.mark.timeout(3)
    def test_client_sends_and_server_receives(self):
        address = ("localhost", 12345)
        received = queue.Queue()
        server = ServerReceiver(
            address,
            received,
            reconnect=False,
            stop=lambda: received.qsize() >= 2
        )

        to_send = queue.Queue()
        client = ClientSender(
            address,
            to_send,
            reconnect=False,
            stop=lambda: to_send.empty()
        )
        client.to_send.put("Hello")
        client.to_send.put("World")

        with server:
            server.start()
            with client:
                client.connect(timeout=2)
                client.start()
                client.join()
            server.join()

        assert client.to_send.empty()
        assert not server.received.empty()
        assert server.received.get() == b"Hello"
        assert server.received.get() == b"World"


class TestClientAndServer:

    @pytest.mark.timeout(3)
    def test_client_and_server_send_and_receive(self):
        address = ("localhost", 12345)

        client_received = queue.Queue()
        client_to_send = queue.Queue()
        client = Client(
            address,
            client_received,
            client_to_send,
            reconnect=False,
            stop_receive=lambda: client_received.qsize() >= 2,
            stop_send=lambda: client_to_send.empty()
        )
        client.to_send.put("Hello from client")
        client.to_send.put("World from client")

        server_received = queue.Queue()
        server_to_send = queue.Queue()
        server = Server(
            address,
            server_received,
            server_to_send,
            reconnect=False,
            stop_receive=lambda: server_received.qsize() >= 2,
            stop_send=lambda: server_to_send.empty()
        )
        server.to_send.put("Hello from server")
        server.to_send.put("World from server")

        with server:
            server.start()
            with client:
                client.connect(timeout=2)
                client.start()
                client.join()
            server.join()

        assert server.to_send.empty()
        assert client.to_send.empty()

        assert not server.received.empty()
        assert server.received.get() == b"Hello from client"
        assert server.received.get() == b"World from client"

        assert not client.received.empty()
        assert client.received.get() == b"Hello from server"
        assert client.received.get() == b"World from server"
