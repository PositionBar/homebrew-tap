"""One-time CI encryption for PositionBar/releases; emits ciphertext only."""
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

SIGNING = ("DEVELOPER_ID_CERTIFICATE_P12_BASE64", "DEVELOPER_ID_CERTIFICATE_PASSWORD",
           "APP_STORE_API_PRIVATE_KEY", "SPARKLE_PRIVATE_KEY")


def probe(path, token):
    request = urllib.request.Request("https://api.github.com/" + path,
                                     headers={"Authorization": "Bearer " + token,
                                              "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        return None


def credentials(environment, check=probe):
    missing = [name for name in SIGNING if not environment.get(name)]
    if missing:
        raise ValueError("Missing existing signing credentials: " + ", ".join(missing))
    values = {name: environment[name] for name in SIGNING}
    token = environment.get("LEGACY_GH_PAT", "")
    if token and hashlib.sha256(token.encode()).hexdigest() != environment["BLOCKED_TOKEN_SHA256"]:
        source = check("repos/sorcererxw/positionbar/commits/main", token)
        if source and len(source.get("sha", "")) == 40:
            values["GH_PAT"] = token
            tap = check("repos/PositionBar/homebrew-tap", token)
            if tap and tap.get("permissions", {}).get("push"):
                values["TAP_WRITE_TOKEN"] = token
    return values


def main():
    from nacl.public import PrivateKey, PublicKey, SealedBox
    # Validate the crypto dependency with an ephemeral fixture, without writing keys.
    fixture = PrivateKey.generate()
    assert SealedBox(fixture).decrypt(SealedBox(fixture.public_key).encrypt(b"fixture")) == b"fixture"
    recipient = PublicKey(base64.b64decode(os.environ["DESTINATION_PUBLIC_KEY"], validate=True))
    values = credentials(os.environ)
    encrypted = {name: base64.b64encode(SealedBox(recipient).encrypt(value.encode())).decode()
                 for name, value in values.items()}
    omitted = sorted({"GH_PAT", "TAP_WRITE_TOKEN"} - set(values))
    payload = {"repository": "PositionBar/releases", "key_id": os.environ["DESTINATION_KEY_ID"],
               "secrets": encrypted, "omitted": omitted}
    output = Path(os.environ["RUNNER_TEMP"]) / "positionbar-encrypted-secrets.json"
    output.write_text(json.dumps(payload))
    print("Encrypted existing credentials: " + ", ".join(sorted(values)))
    if omitted:
        print("Existing token unusable or insufficient; omitted: " + ", ".join(omitted))


if __name__ == "__main__":
    main()
