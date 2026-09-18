"""Simulated ISO 8583 issuer/switch listening on localhost:8583."""
import logging
import socket
import struct

from iso8583_lib import hexdump, pack_message, unpack_message

HOST, PORT = "127.0.0.1", 8583
RESPONSE_MTIS = {"0200": "0210", "0100": "0110", "0800": "0810", "0400": "0410"}


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler("server.log", encoding="utf-8"), logging.StreamHandler()])


def receive_exactly(conn, count):
    result = bytearray()
    while len(result) < count:
        chunk = conn.recv(count - len(result))
        if not chunk:
            raise ConnectionError("peer closed the connection")
        result.extend(chunk)
    return bytes(result)


def handle_client(conn, address):
    logging.info("Connected: %s:%s", *address)
    try:
        length = struct.unpack(">H", receive_exactly(conn, 2))[0]
        raw = receive_exactly(conn, length)
        mti, fields = unpack_message(raw)
        logging.info("Received MTI %s; decoded fields: %s", mti, fields)
        logging.info("Incoming ISO 8583 hex dump:\n%s", hexdump(raw))
        if mti not in RESPONSE_MTIS:
            raise ValueError(f"unsupported request MTI {mti}")
        fields[39] = "00"
        response = pack_message(RESPONSE_MTIS[mti], fields)
        conn.sendall(struct.pack(">H", len(response)) + response)
        logging.info("Sent MTI %s; decoded fields: %s", RESPONSE_MTIS[mti], fields)
        logging.info("Outgoing ISO 8583 hex dump:\n%s", hexdump(response))
    except (ConnectionError, ValueError, UnicodeError) as exc:
        logging.exception("Message handling failed: %s", exc)
    finally:
        conn.close()
        logging.info("Disconnected: %s:%s", *address)


def main():
    configure_logging()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        logging.info("ISO 8583 issuer/switch listening on %s:%d", HOST, PORT)
        while True:
            conn, address = server.accept()
            handle_client(conn, address)


if __name__ == "__main__":
    main()
