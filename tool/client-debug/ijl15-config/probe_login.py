#!/usr/bin/env python3
"""Probe a v83 login endpoint with an intentionally invalid account."""

from __future__ import annotations

import argparse
import re
import socket
import struct
from pathlib import Path

from Crypto.Cipher import AES


ROOT = Path(__file__).resolve().parents[3]
AES_SOURCE = ROOT / "gms-server/src/main/java/org/gms/net/encryption/MapleAESOFB.java"
AES_KEY = bytes(
    (0x13, 0, 0, 0, 0x08, 0, 0, 0, 0x06, 0, 0, 0, 0xB4, 0, 0, 0,
     0x1B, 0, 0, 0, 0x0F, 0, 0, 0, 0x33, 0, 0, 0, 0x52, 0, 0, 0)
)


def funny_bytes() -> bytes:
    source = AES_SOURCE.read_text(encoding="utf-8")
    block = source.split("private static final byte[] funnyBytes", 1)[1].split("};", 1)[0]
    values = bytes(int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{1,2})", block))
    if len(values) != 256:
        raise RuntimeError(f"expected 256 Maple IV constants, found {len(values)}")
    return values


FUNNY_BYTES = funny_bytes()


def rol(value: int, count: int) -> int:
    count %= 8
    return ((value << count) | (value >> (8 - count))) & 0xFF


def ror(value: int, count: int) -> int:
    return rol(value, 8 - (count % 8))


def custom_encrypt(data: bytearray) -> None:
    for round_number in range(6):
        remember = 0
        length = len(data) & 0xFF
        indexes = range(len(data)) if round_number % 2 == 0 else range(len(data) - 1, -1, -1)
        for index in indexes:
            value = data[index]
            if round_number % 2 == 0:
                value = rol(value, 3)
                value = (value + length) & 0xFF
                value ^= remember
                remember = value
                value = ror(value, length)
                value = ((~value) + 0x48) & 0xFF
            else:
                value = rol(value, 4)
                value = (value + length) & 0xFF
                value ^= remember
                remember = value
                value ^= 0x13
                value = ror(value, 3)
            data[index] = value
            length = (length - 1) & 0xFF


def custom_decrypt(data: bytearray) -> None:
    for round_number in range(1, 7):
        remember = 0
        length = len(data) & 0xFF
        indexes = range(len(data)) if round_number % 2 == 0 else range(len(data) - 1, -1, -1)
        for index in indexes:
            value = data[index]
            if round_number % 2 == 0:
                value = (value - 0x48) & 0xFF
                value = (~value) & 0xFF
                value = rol(value, length)
                next_remember = value
                value ^= remember
                remember = next_remember
                value = (value - length) & 0xFF
                value = ror(value, 3)
            else:
                value = rol(value, 3)
                value ^= 0x13
                next_remember = value
                value ^= remember
                remember = next_remember
                value = (value - length) & 0xFF
                value = ror(value, 4)
            data[index] = value
            length = (length - 1) & 0xFF


def update_iv(old_iv: bytes) -> bytes:
    current = bytearray((0xF2, 0x53, 0x50, 0xC6))
    for input_byte in old_iv:
        elina = current[1]
        moritz = (FUNNY_BYTES[elina] - input_byte) & 0xFF
        current[0] = (current[0] + moritz) & 0xFF
        moritz = current[2] ^ FUNNY_BYTES[input_byte]
        current[1] = (elina - moritz) & 0xFF
        elina = current[3]
        moritz = (FUNNY_BYTES[elina] + input_byte) & 0xFF
        current[2] = moritz ^ current[2]
        current[3] = (elina - current[0] + FUNNY_BYTES[input_byte]) & 0xFF
        value = int.from_bytes(current, "little")
        rotated = ((value << 3) | (value >> 29)) & 0xFFFFFFFF
        current[:] = rotated.to_bytes(4, "little")
    return bytes(current)


def aes_crypt(data: bytearray, iv: bytes) -> bytes:
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    offset = 0
    block_length = 0x5B0
    while offset < len(data):
        count = min(block_length, len(data) - offset)
        stream = iv * 4
        for index in range(count):
            if index % 16 == 0:
                stream = cipher.encrypt(stream)
            data[offset + index] ^= stream[index % 16]
        offset += count
        block_length = 0x5B4
    return update_iv(iv)


def packet_header(iv: bytes, version: int, length: int) -> bytes:
    swapped_version = ((version << 8) & 0xFF00) | (version >> 8)
    iv_value = ((iv[2] << 8) | iv[3]) ^ swapped_version
    swapped_length = ((length << 8) & 0xFF00) | (length >> 8)
    return struct.pack(">HH", iv_value, iv_value ^ swapped_length)


def read_exact(connection: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError(f"connection closed after {len(data)} of {size} bytes")
        data.extend(chunk)
    return bytes(data)


def maple_string(value: str) -> bytes:
    encoded = value.encode("ascii")
    return struct.pack("<H", len(encoded)) + encoded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=args.timeout) as connection:
        connection.settimeout(args.timeout)
        hello_length = struct.unpack("<H", read_exact(connection, 2))[0]
        hello = read_exact(connection, hello_length)
        version = struct.unpack_from("<H", hello)[0]
        recv_iv = hello[5:9]
        send_iv = hello[9:13]
        print(f"hello version={version} recv_iv={recv_iv.hex()} send_iv={send_iv.hex()}")

        username = "__beidou_probe_missing__"
        plain = bytearray(b"\x01\x00" + maple_string(username) + maple_string("invalid") + b"\0" * 10)
        encrypted = bytearray(plain)
        custom_encrypt(encrypted)
        aes_crypt(encrypted, recv_iv)
        connection.sendall(packet_header(recv_iv, version, len(encrypted)) + encrypted)
        print(f"sent login opcode=0x0001 bytes={len(plain)} account={username}")

        try:
            header = read_exact(connection, 4)
        except TimeoutError as error:
            raise SystemExit(
                f"login response timed out after {args.timeout:g}s; "
                "the endpoint completed the handshake but did not process the login request"
            ) from error
        first, second = struct.unpack(">HH", header)
        response_length = ((first ^ second) >> 8) | (((first ^ second) & 0xFF) << 8)
        response = bytearray(read_exact(connection, response_length))
        aes_crypt(response, send_iv)
        custom_decrypt(response)
        opcode = struct.unpack_from("<H", response)[0]
        reason = response[2] if len(response) > 2 else None
        print(f"received opcode=0x{opcode:04x} bytes={len(response)} reason={reason} data={response.hex()}")


if __name__ == "__main__":
    main()
