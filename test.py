import my_server
import logging
import socket
import sys
import threading
import time


HOST = 'localhost'
PORT = 5001


class TestClient:
    """
    Client object used for testing the server. Connects to the
    server at the specified address and listens for incoming data.
    """
    def __init__(self, log: logging.Logger) -> None:
        self._log = log

        self._soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._client_enabled = threading.Event()
        self._client_thread = threading.Thread(target=self._client_loop)

    def start(self, host: int, port: str) -> None:
        self._soc.connect((host, port))
        self._client_thread.start()

    def cleanup(self) -> None:
        self._client_enabled.clear()
        self._client_thread.join()
        self._soc.shutdown(socket.SHUT_RDWR)
        self._soc.close()
        self._log.info("Closed connection...")

    def _client_loop(self) -> None:
        self._client_enabled.set()
        while self._client_enabled.is_set():
            rx_data = self._soc.recv(1024).decode('utf-8')
            if rx_data: self._log.info(rx_data)


if __name__ == "__main__":
    logger = logging.getLogger("test")
    logging.basicConfig(stream=sys.stdout,
                        format='%(levelname)s - %(name)s - %(message)s',
                        level=logging.INFO)

    client_group0 = [TestClient(logger.getChild(f'TestClient0_{i}')) for i in range(2)]
    client_group1 = [TestClient(logger.getChild(f'TestClient1_{i}')) for i in range(2)]

    # need to test a the client disconnecting first and server closing first
    with my_server.MyServer(HOST, PORT, logger.getChild('Server')) as server:
        assert server.is_alive
        for client in (client_group0 + client_group1):
            client.start(HOST, PORT)
        # close some clients while the server is still up
        for client in client_group0:
            client.cleanup()

    time.sleep(2)
    # close some clients after the server is closed
    for client in client_group1:
        client.cleanup()
