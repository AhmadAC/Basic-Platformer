# network_comms.py
# -*- coding: utf-8 -*-
# version 1.0000000.1
"""
Networking utilities for data encoding/decoding and IP retrieval.
"""
import socket
import json

def get_local_ip():
    """Gets the local IP address of the machine."""
    best_ip = '127.0.0.1'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) # Connect to a known external server (doesn't send data)
        best_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            best_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            best_ip = '127.0.0.1' # Fallback
    return best_ip

def encode_data(data):
    """Encodes Python dictionary to JSON bytes with a newline delimiter."""
    try:
        return json.dumps(data).encode('utf-8') + b'\n'
    except TypeError as e:
        print(f"Encoding Error: {e} Data: {str(data)[:100]}")
        return None
    except Exception as e:
        print(f"Unexpected Encoding Error: {e}")
        return None

def decode_data_stream(byte_buffer):
    """
    Decodes a stream of newline-delimited JSON byte data.
    Returns a list of decoded objects and the remaining unparsed buffer.
    """
    decoded_objects = []
    remaining_buffer = byte_buffer
    while b'\n' in remaining_buffer:
        message, remaining_buffer = remaining_buffer.split(b'\n', 1)
        if not message:  # Skip empty messages (e.g. if multiple newlines)
            continue
        try:
            decoded_objects.append(json.loads(message.decode('utf-8')))
        except json.JSONDecodeError as e:
            # print(f"JSON Decode Error: {e}. Malformed message: {message[:100]}") # Optional: log malformed
            continue # Skip malformed JSON
        except Exception as e:
            # print(f"Unexpected Decode Error: {e}. Message: {message[:100]}") # Optional: log other errors
            continue
    return decoded_objects, remaining_buffer