from pathlib import Path


class SshPublicKey:
    def __init__(self, path: Path = None):
        if not path:
            # Use default rsa key.
            path = Path.home() / ".ssh/id_rsa.pub"

        self.public_key = path
        if not self.public_key.exists():
            raise PublicKeyNotFound

    def as_text(self) -> str:
        return self.public_key.read_text()


class PublicKeyNotFound(Exception):
    pass
