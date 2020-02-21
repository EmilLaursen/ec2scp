from pathlib import Path
from typing import List, Tuple, Iterator
from more_itertools import split_before, partition


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


def first(key: str, iterator: Iterator[str]) -> str:
    ok = next((x for x in iterator if normalize_entry(x).startswith(key)), None)
    return ok


def normalize_entry(entry: str) -> str:
    return entry.strip().lower()


class SshSimpleParser:
    def __init__(self):
        pass

    def write_entries(self) -> None:
        pass

    def _serialize_entry(entry: dict) -> str:
        pass

    def parse(self, path: Path):
        config_text = path.read_text()
        stanzas = self._get_stanzas(config_text)
        entries = [self._parse_stanza(stanza) for stanza in stanzas]
        return entries

    def _get_stanzas(self, config_text: str):
        lines = [line.strip() for line in config_text.split("\n") if line and not line.strip().startswith("#")]
        stanzas = split_before(
            lines, lambda line: line.lower().startswith("host ")
        )
        return stanzas

    def _parse_stanza(self, stanza: List[str]) -> dict:
        keys = ["host ", "hostname ", "user "]

        rest, key_lines = partition(
            lambda line: any(normalize_entry(line).startswith(key) for key in keys),
            stanza
        )
        key_lines = list(key_lines)

        entry_dict = {}
        for key in keys:
            ok = first(key, key_lines[:])
            if ok:
                k, *values = tuple(ok.split(" "))
            entry_dict[k] = " ".join(values)
        entry_dict["rest"] = list(rest)

        return entry_dict
