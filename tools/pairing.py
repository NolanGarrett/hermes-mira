"""Local operator pairing/revocation client. Do not redirect its pairing output to disk."""
import argparse
import json
import socket

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("socket", help="mira-operator.sock in the isolated profile home")
parser.add_argument("action", choices=["pair", "revoke"])
parser.add_argument("principal", help="Must already be authorized by native gateway config")
args = parser.parse_args()
with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(3)
    connection.connect(args.socket)
    connection.sendall(json.dumps({"action": args.action, "principal": args.principal}).encode()+b"\n")
    response = json.loads(connection.makefile("rb").readline(2048))
if "code" in response:
    print("Foreground pairing code (60 seconds, single use; do not save):", response["code"])
    print("Open:", response["origin"])
else:
    print(json.dumps(response))
