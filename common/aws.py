import boto3
from botocore.exceptions import ClientError

import jmespath
import click
import re
from pathlib import Path

from itertools import tee, filterfalse


def partition(pred, iterable):
    "Use a predicate to partition entries into false entries and true entries"
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = tee(iterable)
    return filterfalse(pred, t1), filter(pred, t2)


# Instance ID's are either 8 or 17 characters long, after the i- part.
INST_ID_REGEX = r"(^i-(\w{17}|\w{8}))\W(.+)"


def get_instance_info(name=None, inst_id=None, client=None):

    ec2 = client if client is not None else boto3.client("ec2")

    if name is None and inst_id is None:
        raise TypeError("Both name and inst_id can not be None.")
    kwargs = (
        {"Filters": [{"Name": "tag:Name", "Values": [name]}]}
        if inst_id is None
        else {"InstanceIds": [inst_id]}
    )
    try:
        response = ec2.describe_instances(**kwargs)

        # JMESpath query to extract relevant information.
        result = jmespath.search(
            "Reservations[0].Instances[0].[InstanceId, ImageId, Placement.AvailabilityZone, PublicIpAddress]",
            response,
        )

        if result is None:
            raise click.ClickException(f"Failure. No instance with Name: {name}")
        instance_info = dict(zip(["id", "ami", "avz", "ip"], result))

        # Find OS user. ubuntu or ec2-user
        image_desc = jmespath.search(
            "Images[*].Description",
            ec2.describe_images(ImageIds=[instance_info["ami"]]),
        )[0]

        if "Windows" in image_desc:
            raise click.ClickException("EC2 instance is running windows.")
        os_user = "ubuntu" if "Ubuntu" in image_desc else "ec2-user"

    except ClientError as e:
        raise click.ClickException(f"AWS client failed: {e}")

    instance_info.update({"os_user": os_user})
    return instance_info


def resolve_instance_info_and_paths(src, dst, obj):
    client = obj.ec2

    # Figure out which one refers to the remote server.
    src_is_remote = ":" in src
    remote_path = src if src_is_remote else dst

    match = re.match(INST_ID_REGEX, remote_path)
    # Did caller use an instance-id or instance name to refer to remote?
    name_used = match is None

    identifier, path = tuple(remote_path.split(sep=":"))

    # Is name from config, or actual instance name?
    if obj.cfg is not None:
        instance = obj.cfg.get(identifier)

        # name found in config - overwrite identifier with associated instance_id.
        if instance is not None:
            identifier = instance["id"]
            name_used = False
        else:
            raise click.ClickException("given instance name not found in config.")

    # Retrieve all instance information based on name or instance-id.
    kwargs = {"name" if name_used else "inst_id": identifier, "client": client}
    inst_info = get_instance_info(**kwargs)

    # If remote path is relative, fix it to remote's home folder.
    if not Path(path).is_absolute():
        path = str(Path("/home/") / inst_info["user"] / path)
    # Actual remote address used in scp call.
    remotehost_prefix = f'{ inst_info["user"] }@{ inst_info["ip"] }:'

    if src_is_remote:
        src_path = remotehost_prefix + path
        dst_path = dst
    else:
        src_path = src
        dst_path = remotehost_prefix + path

    return inst_info, src_path, dst_path


def valid_available_instances(client):
    ec2 = client

    inst_dict = jmespath.search(
        "Reservations[].Instances[].{name: Tags[?Key=='Name'].Value | [0], id: InstanceId, avz: Placement.AvailabilityZone, ami: ImageId}",
        ec2.describe_instances(),
    )

    if inst_dict is None:
        return

    has_name, no_name = partition(
        lambda dic: dic.get("name") is None or dic.get("name") == "", inst_dict
    )

    no_whitespace, whitespace = partition(lambda dic: " " in dic.get("name"), has_name)

    valid_instances = list(no_whitespace)

    invalid_instances = set(whitespace) | set(no_name)

    return valid_instances, invalid_instances


def retrieve_os_users(client, instances):
    ec2 = client

    ami_query = jmespath.search(
        "Images[].{id: ImageId, name: Name, loc: ImageLocation}",
        ec2.describe_images(ImageIds=[instance.get("ami") for instance in instances]),
    )
    ami_query = {ami_dic["id"]: ami_dic for ami_dic in ami_query}

    instance_dics = []
    for instance in instances:

        ami = instance["ami"]

        ami_info = ami_query.get(ami)

        os_user = _osuser_from_ami(ami_info)

        instance["os_user"] = os_user
        instance_dics.append(instance)

    return instance_dics


def _osuser_from_ami(ami_info):
    if "ubuntu" in ami_info["name"].lower() or "ubuntu" in ami_info["loc"].lower():
        os_user = "ubuntu"
    elif "amzn2" in ami_info["name"].lower() or "amzn2" in ami_info["loc"].lower():
        os_user = "ec2-user"
    else:
        os_user = None
    return os_user
