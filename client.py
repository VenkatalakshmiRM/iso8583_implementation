"""Simulated POS/ATM client: PIN purchase, optional reversal, and echo test."""
import argparse
import logging
import random
import socket
import struct
from datetime import datetime

from iso8583_lib import hexdump, pack_message, unpack_message

HOST, PORT = "127.0.0.1", 8583
PURCHASE_TIMEOUT_SECONDS = 5


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


def receive_response(sock):
    response_length = struct.unpack(">H", receive_exactly(sock, 2))[0]
    return unpack_message(receive_exactly(sock, response_length))


def send_and_receive(mti, fields, scenario, timeout=10):
    raw = pack_message(mti, fields)
    logging.info("%s: sending MTI %s; fields: %s", scenario, mti, fields)
    logging.info("%s request hex dump:\n%s", scenario, hexdump(raw))
    with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(struct.pack(">H", len(raw)) + raw)
        response_mti, response_fields = receive_response(sock)
    logging.info("%s: received MTI %s; decoded fields: %s", scenario, response_mti, response_fields)
    logging.info("%s verdict: %s (DE39=%s)", scenario,
                 "APPROVED" if response_fields.get(39) == "00" else "DECLINED", response_fields.get(39, "missing"))
    return response_fields


def send_purchase(purchase):
    raw = pack_message("0200", purchase)
    logging.info("PURCHASE: sending MTI 0200; fields: %s", purchase)
    try:
        with socket.create_connection((HOST, PORT), timeout=PURCHASE_TIMEOUT_SECONDS) as sock:
            sock.settimeout(PURCHASE_TIMEOUT_SECONDS)
            sock.sendall(struct.pack(">H", len(raw)) + raw)
            response_mti, response_fields = receive_response(sock)
        logging.info("PURCHASE: received MTI %s; DE39=%s", response_mti, response_fields.get(39))
        return response_fields
    except (socket.timeout, TimeoutError):
        logging.warning("Purchase timed out after %d seconds; sending reversal for STAN %s",
                        PURCHASE_TIMEOUT_SECONDS, purchase[11])
        reversal_fields = {key: purchase[key] for key in (2, 3, 4, 7, 11, 12, 13, 32, 37, 41, 42, 49, 62) if key in purchase}
        return send_and_receive("0400", reversal_fields, "REVERSAL", timeout=10)


def main():
    parser = argparse.ArgumentParser(description="Run a demo ISO 8583 purchase and echo exchange")
    parser.add_argument("--pin", choices=("correct", "wrong"), default="correct",
                        help="choose the PIN test case (correct PIN is 1234)")
    parser.add_argument("--no-echo", action="store_true", help="skip 0800 echo after purchase")
    args = parser.parse_args()
    configure_logging()
    now = datetime.now()
    stan = f"{random.randint(0, 999999):06d}"
    rrn = stan + now.strftime("%H%M%S")
    purchase = {
        2: "4242424242424242", 3: "000000", 4: "000000001250",
        7: now.strftime("%m%d%H%M%S"), 11: stan, 12: now.strftime("%H%M%S"),
        13: now.strftime("%m%d"), 32: "123456", 37: rrn,
        41: "POS12345", 42: "DEMO MERCHANT  ", 49: "356",
        52: "1234" if args.pin == "correct" else "9999", 62: "DEMO-PURCHASE",
    }
    purchase_response = send_purchase(purchase)
    if purchase_response.get(39) != "00":
        logging.info("Purchase declined/reversed (DE39=%s)", purchase_response.get(39))
        return
    if not args.no_echo:
        echo = {7: datetime.now().strftime("%m%d%H%M%S"), 11: f"{random.randint(0, 999999):06d}", 62: "ECHO-TEST"}
        echo_response = send_and_receive("0800", echo, "NETWORK ECHO")
        if echo_response.get(39) != "00":
            raise SystemExit("Network echo was not approved")
    logging.info("Scenarios completed successfully.")


if __name__ == "__main__":
    main()
