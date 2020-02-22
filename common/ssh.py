from pathlib import Path
from typing import List, Tuple, Iterator
from more_itertools import split_before, partition
from datetime import datetime
from pathlib import Path


class SshPublicKey:
    def __init__(self, path: Path = None):
        if not path:
            # Use default rsa key.
            path = Path.home() / ".ssh/id_rsa.pub"
        self.public_key = path
        if not self.public_key.exists():
            message = (
                "Rsa key not found. Please generate one with: ssh-keygen -t rsa"
                f" -f {self.public_key}. Must be PEM format."
            )
            raise PublicKeyNotFound(message)

    def as_text(self) -> str:
        return self.public_key.read_text()


class PublicKeyNotFound(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors


class SshSimpleParser:
    _header = """
    ###########################################################################
    ##########                                                       ##########
    ##########                  EC2 CLI CONFIG BLOCK                 ##########
    ##########             !! ALTER AT YOUR OWN PERRIL !!            ##########
    ##########                                                       ##########
    ###########################################################################
    """
    _footer = """
    ###########################################################################
    ##########                                                       ##########
    ##########                  EC2 CLI CONFIG BLOCK                 ##########
    ##########             ALL YOUR BASE ARE BELONG TO US            ##########
    ##########                                                       ##########
    ###########################################################################
    """

    def __init__(self, ssh_config_path: Path):
        self.entry_metakeys = ["InstanceID", "LastChange"]
        self.entry_subkeys = ["HostName", "User", "Port", "IdentityFile"]
        self.entry_keys = ["Host"] + self.entry_subkeys + self.entry_metakeys

        self.ssh_config_path = ssh_config_path
        self.head, self.ec2_config, self.tail = self._get_ssh_config_sections(
            self.ssh_config_path.read_text()
        )
        self.ssh_entries = self._parse(self.ec2_config)

    def _get_ssh_config_sections(self, config_text: str):
        head = config_text
        ec2_config = ""
        tail = ""

        ec2_config_start = config_text.find(SshSimpleParser._header)
        ec2_config_end = config_text.find(SshSimpleParser._footer)

        if ec2_config_start == -1:  # Not found
            return head, ec2_config, tail

        assert (
            ec2_config_start != -1
        ), "This should not happen. Have you edited for forbidden part?"

        header_offset = len(SshSimpleParser._header)
        footer_offset = len(SshSimpleParser._footer)

        head = config_text[:ec2_config_start]
        ec2_config = config_text[ec2_config_start + header_offset : ec2_config_end]
        tail = config_text[ec2_config_end + footer_offset :]

        return head, ec2_config, tail

    def save(self) -> None:
        self.ssh_config_path.write_text(
            self.head
            + SshSimpleParser._header
            + self._serialize_entries(self.ssh_entries)
            + SshSimpleParser._footer
            + self.tail
        )

    def _serialize_entries(self, entries: List[dict]) -> str:
        return "".join(self._serialize_entry(entry) for id, entry in entries.items())

    def _serialize_entry(self, entry: dict) -> str:
        sub_keys = "\n".join(f"   {key} {entry[key]}" for key in self.entry_subkeys)
        stanza = (
            f"\nHost {entry['Host']}"
            f"\n{sub_keys}"
            f"\n#InstanceID {entry['InstanceID']}"
            f"\n#LastChange {entry['LastChange']}"
            "\n"
        )
        return stanza

    def _parse(self, ssh_config_text: str) -> List[dict]:
        ssh_entries = {}
        for stanza in self._get_stanzas(ssh_config_text):
            ssh_entries.update(self._parse_stanza(stanza))
        return ssh_entries

    def _parse_stanza(self, stanza: List[str]) -> dict:
        print(f"parse_stanza: {stanza}")
        entry_dict = {}
        for line in stanza:
            key, *values = line.split()
            entry_dict[key] = " ".join(values)

        if not entry_dict:
            return entry_dict

        assert (
            list(entry_dict.keys()) == self.entry_keys
        ), f"Found unexpected keys: {entry_dict}"

        # parse LastChanged.
        entry_dict["LastChange"] = datetime.strptime(
            entry_dict["LastChange"], "%Y-%m-%d %H:%M:%S.%f"
        )
        # Lookup on instance ids.
        entry_dict = {entry_dict["InstanceID"]: entry_dict}
        return entry_dict

    def _get_stanzas(self, config_text: str):
        whitespace_comment = " #\n"
        lines = [
            line.strip(whitespace_comment)
            for line in config_text.split("\n")
            if line.strip(whitespace_comment)
        ]
        stanzas = list(
            split_before(lines, lambda line: line.lower().startswith("host "))
        )
        print(f"Stanzas: {stanzas}")
        return stanzas

    def update_entry(
        self,
        instance_id: str,
        launch_date: datetime,
        host: str,
        hostname: str,
        user: str,
        port: str = "22",
        public_key_path: Path = Path.home() / ".ssh/id_rsa.pub",
    ) -> None:

        priv_key_path = public_key_path.parent / public_key_path.stem
        entry = self.ssh_entries.get(instance_id, {})
        if not entry:
            entry = {
                instance_id: {  # dict(zip(self.entry_keys, *args))
                    "Host": host,
                    "HostName": hostname,
                    "User": user,
                    "Port": port,
                    "IdentityFile": priv_key_path,
                    "InstanceID": instance_id,
                    "LastChange": datetime.now(),
                }
            }
        else:
            entry["Host"] = host
            entry["HostName"] = hostname
            entry["User"] = user
            entry["Port"] = port
            entry["IdentityFile"] = priv_key_path
            entry["InstanceID"] = instance_id
            entry["LastChange"] = datetime.now()
            entry = {
                instance_id: entry
            }
        
        self.ssh_entries.update(entry)
        self.save()
        return entry
