"""One-time CI encryption for PositionBar/releases; emits ciphertext only."""
import base64
import json
import os
from pathlib import Path

SIGNING = ("DEVELOPER_ID_CERTIFICATE_P12_BASE64", "DEVELOPER_ID_CERTIFICATE_PASSWORD",
           "APP_STORE_API_PRIVATE_KEY", "SPARKLE_PRIVATE_KEY")


def credentials(environment):
    missing = [name for name in SIGNING if not environment.get(name)]
    if missing:
        raise ValueError("Missing existing signing credentials: " + ", ".join(missing))
    return {name: environment[name] for name in SIGNING}


def main():
    from nacl.public import PrivateKey, PublicKey, SealedBox
    # Validate the crypto dependency with an ephemeral fixture, without writing keys.
    fixture = PrivateKey.generate()
    assert SealedBox(fixture).decrypt(SealedBox(fixture.public_key).encrypt(b"fixture")) == b"fixture"
    recipient = PublicKey(base64.b64decode(os.environ["DESTINATION_PUBLIC_KEY"], validate=True))
    values = credentials(os.environ)
    encrypted = {name: base64.b64encode(SealedBox(recipient).encrypt(value.encode())).decode()
                 for name, value in values.items()}
    payload = {"repository": "PositionBar/releases", "key_id": os.environ["DESTINATION_KEY_ID"],
               "secrets": encrypted}
    output = Path(os.environ["RUNNER_TEMP"]) / "positionbar-encrypted-secrets.json"
    output.write_text(json.dumps(payload))
    print("Encrypted existing credentials: " + ", ".join(sorted(values)))


if __name__ == "__main__":
    main()
