import contextlib
import logging
import multiprocessing
import select
import socket
import threading
import typing

import time

NONBLOCKING = 0


class MyServer(contextlib.AbstractContextManager):
    """
    TCP Server. Binds to a socket using the specified host and port.
    Handles client connections within a multiprocessing.Process to allow
    the server to run in the background of other scripts.
    """
    def __init__(self, host: str, port: int, log: logging.Logger):
        self._host = host
        self._port = port
        self._log = log

        self._soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_enabled = multiprocessing.Event()
        self._server_proc = multiprocessing.Process(target=self._server_loop, args=(self._server_enabled,))
        self._active_clients: typing.List[ClientHandler] = []

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_alive(self) -> bool:
        return self._server_proc.is_alive()

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end()
        return

    def setup(self) -> None:
        assert not(self._server_enabled.is_set()), "Failed setup. Server is currently running."
        self._log.info(f"Setting up server at ({self.host}, {self.port})...")
        self._soc.bind((self.host, self.port))
        self._soc.listen()
        self._server_proc.start()

    def end(self) -> None:
        self._log.info("Closing server...")
        self._server_enabled.clear()
        self._server_proc.join()
        self._server_proc.close()
        self._soc.close()
        self._log.info("Server closed...")

    def _server_loop(self, status: threading.Event) -> None:
        status.set()
        while status.is_set():
            readable, _, _ = select.select([self._soc],
                                           [self._soc],
                                           [self._soc],
                                           NONBLOCKING)
            for soc in readable:
                assert isinstance(soc, socket.socket)
                self._active_clients.append(ClientHandler(*soc.accept(), self._log.getChild('ClientHandler')))

            for handler in self._active_clients:
                if not(handler.is_alive):
                    handler.cleanup()
                    self._active_clients.remove(handler)
        # Cleanup all threads spawned by this process before exiting
        for handler in self._active_clients:
            self._log.info(f"Cleaning up {handler._soc.getpeername()}")
            handler.cleanup()


class ClientHandler:
    """
    Object to represent a client actively connected to the server.
    Used to spawn a thread responisble for servicing the client.
    """
    def __init__(self,
                 soc: socket.socket,
                 ret_addr: typing.Tuple[str, int],
                 log: logging.Logger) -> None:
        self._soc = soc
        self._ret_addr = ret_addr
        self._log = log

        self._client_enabled = threading.Event()
        self._client_thread = threading.Thread(target=self._client_loop, args=(self._client_enabled,))
        self._client_thread.start()

    @property
    def name(self) -> str:
        return str(self._soc.getpeername())

    @property
    def is_alive(self) -> bool:
        return self._client_thread.is_alive()

    def cleanup(self) -> None:
        self._client_enabled.clear()
        self._client_thread.join()
        self._soc.shutdown(socket.SHUT_RDWR)
        self._soc.close()

    def _client_loop(self, status: threading.Event) -> None:
        status.set()
        self._log.info(f"Beginning service for client at {self.name}...")
        while status.is_set():
            try:
                self._soc.send(bytes('Hello World', 'utf-8'))
                time.sleep(1)
            except (ConnectionResetError, ConnectionAbortedError):
                self._log.info("Client disconnected...")
                return
