"""Threaded simulated ISO 8583 issuer/switch listening on localhost:8583."""
import logging
import os
import socket
import sqlite3
import struct
import threading
import time
from datetime import datetime

from iso8583_lib import hexdump, pack_message, unpack_message

HOST, PORT = "127.0.0.1", 8583
RESPONSE_MTIS = {"0200": "0210", "0100": "0110", "0800": "0810", "0400": "0420"}
# Demo-only PIN database. DE52 carries four ASCII digits in this teaching protocol.
PIN_DATABASE = {"4242424242424242": "1234"}
STATE_LOCK = threading.Lock()
TRANSACTIONS = {}  # keyed by STAN; protects the in-memory reversed flag.
DB_PATH = os.path.join(os.path.dirname(__file__), "transactions.db")


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
                        handlers=[logging.FileHandler("server.log", encoding="utf-8"), logging.StreamHandler()])


def init_database():
    """Create the small transaction history table if needed."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, mti TEXT NOT NULL,
            stan TEXT, card_number TEXT, amount TEXT, response_code TEXT, status TEXT NOT NULL
        )""")
        db.commit()


def record_transaction(mti, fields, response_code, status):
    """Save each request/response event; each thread owns its SQLite connection."""
    pan = fields.get(2, "")
    masked_pan = ("*" * max(0, len(pan) - 4) + pan[-4:]) if pan else None
    with sqlite3.connect(DB_PATH, timeout=10) as db:
        db.execute("INSERT INTO transactions(timestamp,mti,stan,card_number,amount,response_code,status) VALUES(?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(timespec="seconds"), mti, fields.get(11), masked_pan,
                    fields.get(4), response_code, status))
        db.commit()


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

        stan = fields.get(11)
        if mti == "0400":
            with STATE_LOCK:
                original = TRANSACTIONS.get(stan)
                if original:
                    original["reversed"] = True
            status = "reversed" if original else "reversal requested (original not found)"
            fields[39] = "00" if original else "25"
            record_transaction(mti, fields, fields[39], status)
            logging.info("Reversal for STAN %s: %s", stan, status)
        elif mti == "0200":
            correct_pin = PIN_DATABASE.get(fields.get(2, ""))
            approved = correct_pin is not None and fields.get(52) == correct_pin
            fields[39] = "00" if approved else "55"
            status = "approved" if approved else "declined"
            record_transaction(mti, fields, fields[39], status)
            with STATE_LOCK:
                TRANSACTIONS[stan] = {"fields": dict(fields), "reversed": False}
        else:
            fields[39] = "00"
            status = "approved" if mti in ("0100", "0800") else "received"
            record_transaction(mti, fields, fields[39], status)

        # Set SIMULATE_TIMEOUT=1 to drop the next/all response after handling the request.
        # Alternatively, RESPONSE_DELAY_SECONDS can delay replies to trigger client timeout.
        delay = float(os.getenv("RESPONSE_DELAY_SECONDS", "0")) if mti == "0200" else 0
        if delay > 0:
            time.sleep(delay)
        if os.getenv("SIMULATE_TIMEOUT", "0").lower() in ("1", "true", "yes"):
            logging.warning("SIMULATE_TIMEOUT enabled: dropping response for MTI %s", mti)
            return
        response = pack_message(RESPONSE_MTIS[mti], fields)
        conn.sendall(struct.pack(">H", len(response)) + response)
        logging.info("Sent MTI %s; decoded fields: %s", RESPONSE_MTIS[mti], fields)
        logging.info("Outgoing ISO 8583 hex dump:\n%s", hexdump(response))
    except (ConnectionError, ValueError, UnicodeError, OSError) as exc:
        logging.exception("Message handling failed: %s", exc)
    finally:
        conn.close()
        logging.info("Disconnected: %s:%s", *address)


def main():
    configure_logging()
    # Show exactly which codec module and DE52 definition this process loaded.
    logging.info("Codec module: %s; DE52 definition: %r",
                 unpack_message.__code__.co_filename,
                 unpack_message.__globals__["FIELD_DICTIONARY"].get(52))
    init_database()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        # On Windows, exclusive binding prevents two server copies from sharing
        # port 8583 and receiving connections unpredictably.
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        logging.info("ISO 8583 issuer/switch listening on %s:%d", HOST, PORT)
        while True:
            conn, address = server.accept()
            threading.Thread(target=handle_client, args=(conn, address), daemon=True).start()


if __name__ == "__main__":
    main()
