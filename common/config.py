from pathlib import Path
import json

from collections import Iterable

from common.ssh import SshPublicKey, PublicKeyNotFound

from typing import List, Union


class Ec2Config:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_dir / "config"
        self.cfg = {}

    def load(self) -> None:
        if self.config_file.exists():
            self.cfg = json.loads(self.config_file.read_text())
        else:
            self.config_file.write_text("{}")

    def save(self) -> None:
        self.config_file.write_text(json.dumps(self.cfg, indent=3))

    def lookup_instance(self, name: str = None, *args) -> Union[dict, None]:
        return self.cfg.get(name)

    def update(self, instance_dicts: Union[dict, List[dict]]) -> None:
        if isinstance(instance_dicts, dict):
            instance_dicts = [instance_dicts]

        self.cfg.update(
            {
                instance_dic.get("Tags", {}).get("Name"): instance_dic
                for instance_dic in instance_dicts
            }
        )
        self.save()


class InstanceInfo:
    pass
