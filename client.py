"""Simulated POS/ATM client: purchase followed by network echo test."""
import logging
import random
import socket
import struct
from datetime import datetime

from iso8583_lib import hexdump, pack_message, unpack_message

HOST, PORT = "127.0.0.1", 8583


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler("client.log", encoding="utf-8"), logging.StreamHandler()])


def receive_exactly(sock, count):
    result = bytearray()
    while len(result) < count:
        chunk = sock.recv(count - len(result))
        if not chunk:
            raise ConnectionError("server closed the connection")
        result.extend(chunk)
    return bytes(result)


def send_and_receive(mti, fields, scenario):
    raw = pack_message(mti, fields)
    logging.info("%s: sending MTI %s; fields: %s", scenario, mti, fields)
    logging.info("%s request hex dump:\n%s", scenario, hexdump(raw))
    with socket.create_connection((HOST, PORT), timeout=10) as sock:
        sock.sendall(struct.pack(">H", len(raw)) + raw)
        response_length = struct.unpack(">H", receive_exactly(sock, 2))[0]
        response_raw = receive_exactly(sock, response_length)
    response_mti, response_fields = unpack_message(response_raw)
    logging.info("%s: received MTI %s; decoded fields: %s", scenario, response_mti, response_fields)
    logging.info("%s response hex dump:\n%s", scenario, hexdump(response_raw))
    verdict = "APPROVED" if response_fields.get(39) == "00" else "DECLINED"
    logging.info("%s verdict: %s (DE39=%s)", scenario, verdict, response_fields.get(39, "missing"))
    return response_fields


def main():
    configure_logging()
    now = datetime.now()
    stan = f"{random.randint(0, 999999):06d}"
    rrn = stan + now.strftime("%H%M%S")
    purchase = {
        2: "4242424242424242", 3: "000000", 4: "000000001250",
        7: now.strftime("%m%d%H%M%S"), 11: stan, 12: now.strftime("%H%M%S"),
        13: now.strftime("%m%d"), 32: "123456", 37: rrn,
        41: "POS12345", 42: "DEMO MERCHANT  ", 49: "356", 62: "DEMO-PURCHASE",
    }
    purchase_response = send_and_receive("0200", purchase, "PURCHASE")
    if purchase_response.get(39) != "00":
        raise SystemExit("Purchase was not approved")
    echo = {7: datetime.now().strftime("%m%d%H%M%S"), 11: f"{random.randint(0, 999999):06d}", 62: "ECHO-TEST"}
    echo_response = send_and_receive("0800", echo, "NETWORK ECHO")
    if echo_response.get(39) != "00":
        raise SystemExit("Network echo was not approved")
    logging.info("All scenarios completed successfully; transaction APPROVED (response code 00).")


if __name__ == "__main__":
    main()
