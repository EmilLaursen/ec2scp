from pathlib import Path
import json

from collections import Iterable


def load_config(config_dir: Path):
    # Load custom config.

    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config"

    cfg = {}

    if config_file.exists():
        cfg = json.loads(config_file.read_text())
    else:
        config_file.write_text('{}')

    return cfg, config_file


def update_config(obj, instance_dics=None):
    if instance_dics is not None:
        if isinstance(instance_dics, Iterable):
            obj.cfg.update(
                {instance_dic["name"]: instance_dic for instance_dic in instance_dics}
            )
        else:
            obj.cfg.update(instance_dics)

    json.dump(obj.cfg, obj.config_file.open("w"), indent=4)
