# ISO 8583 Python demo

This is a from-scratch, teaching-oriented implementation of an ASCII ISO 8583-style financial message exchange. It contains no ISO 8583 dependency. The client sends a purchase request (`0200`) and a network echo (`0800`) to a local simulated issuer; the issuer replies with `0210` / `0810` and response code `00`.

## Message structure

Each unframed message is `MTI (4 ASCII bytes) + primary bitmap (8 binary bytes) + data elements`. The TCP layer prepends a separate two-byte big-endian length. The bitmap has one bit per DE: field 2 is bit 2, field 64 is bit 64. Fields occur in numerical order. `LLVAR` fields have a two-ASCII-digit length prefix and `LLLVAR` fields have a three-digit prefix.

The field dictionary supports DE2, 3, 4, 7, 11, 12, 13, 32, 37, 39, 41, 42, 49, and 62. Fixed fields have their specified width; DE2 and DE32 are LLVAR; DE62 is LLLVAR.

Example first bytes from a `0200` purchase (the exact bitmap and values vary with timestamp/STAN):

| Offset | Hex bytes | Meaning |
|---:|---|---|
| `0000` | `30 32 30 30` | ASCII `0200` MTI: financial transaction request |
| `0004` | `72 38 00 01 08 C0 80 04` | 64-bit primary bitmap; marks the included DEs |
| `000C` | `31 36` | DE2 LLVAR length, ASCII `16` |
| `000E` | `34 32 34 32 34 32 34 32 34 32 34 32 34 32 34 32` | DE2 test PAN `4242424242424242` |
| `001E` | `30 30 30 30 30 30` | DE3 processing code `000000` |
| `0024` | `30 30 30 30 30 30 30 30 31 32 35 30` | DE4 amount `000000001250` (= 12.50 in implied cents) |
| `0030` | `30 39 31 38 32 32 32 38 30 39` | DE7 transmission date/time `0918222809` |
| `003A` | `35 30 35 38 32 33` | DE11 STAN `505823` |
| `0040` / `0046` | `32 32 32 38 30 39` / `30 39 31 38` | DE12 local time / DE13 local date |
| `004A` | `30 36 31 32 33 34 35 36` | DE32: LLVAR length `06`, then acquiring ID `123456` |
| `0052` | `35 30 35 38 32 33 32 32 32 38 30 39` | DE37 RRN `505823222809` |
| `005E` / `0066` | `50 4F 53 31 32 33 34 35` / `44 ... 20 20` | DE41 terminal `POS12345` / 15-byte DE42 merchant ID |
| `0075` / `0078` | `33 35 36` / `30 31 33 44 45 4D 4F 2D 50 55 52 43 48 41 53 45` | DE49 currency `356`; DE62 LLLVAR length `013` and `DEMO-PURCHASE` |

Use the real `client.log` dump for an exact report figure. The `hexdump()` helper prints offset, hexadecimal bytes, and printable ASCII side-by-side.

## Run

From this folder, first validate the source:

```powershell
python3 -m py_compile iso8583_lib.py server.py client.py
```

In terminal 1:

```powershell
python3 server.py
```

In terminal 2:

```powershell
python3 client.py
```

Then watch logs live in separate terminals:

```powershell
Get-Content .\server.log -Wait
Get-Content .\client.log -Wait
```

The client exits successfully only if both replies contain `DE39=00`. Stop the server with `Ctrl+C`.

## Networking report evidence

1. Screenshot the two terminals: server decoding and client approval.
2. Include short timestamped excerpts from `server.log` and `client.log` showing the MTIs, decoded fields, and `DE39=00`.
3. Copy one logged hex dump and annotate it using the table above: MTI, bitmap, each LLVAR prefix/value, and fixed values.
4. Optionally capture localhost TCP traffic on port 8583 in Wireshark with `tcp.port == 8583` (or use an administrator-enabled loopback capture adapter). Note that the two-byte length prefix is TCP framing, not part of the ISO payload.

## Enhancement idea: TLS transport

To demonstrate a development comparison, wrap the listening and client sockets with Python's `ssl.SSLContext`, using a local test certificate. Run the current version and retain its readable Wireshark/hex-dump evidence, then run the TLS version on a second port (for example 8584). The application logs will still show decoded ISO fields, but a packet capture will show TLS records rather than readable MTI/PAN data. This demonstrates why financial traffic needs transport protection. A simpler extension is adding an entry to `FIELD_DICTIONARY`, then including it in the client request and verifying that the server echoes it.
