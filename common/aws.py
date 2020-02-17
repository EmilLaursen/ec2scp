from functools import reduce
import operator as op
import re
from pathlib import Path
from typing import Tuple, List
from datetime import datetime
import json

import boto3
from botocore.exceptions import ClientError
import click
from jq import jq


# Instance ID's are either 8 or 17 characters long, after the i- part.
INST_ID_REGEX = r"(^i-(\w{17}|\w{8}))\W(.+)"


def query_aws_for_instance_info(name=None, client=None):
    client = client if client else boto3.client("ec2")
    valid_instances, invalid_instances = filter_instances(client)

    instance_dics = retrieve_os_users(client, valid_instances)

    answer = [
        instance
        for instance in valid_instances
        if instance.get("Tags", {}).get("Name") == name
    ]
    answer = answer[0] if answer else None
    return instance_dics, invalid_instances, answer


def filter_instances(client) -> Tuple[List[dict], List[dict]]:
    response = client.describe_instances()
    return (
        filter_response(VALID_INSTANCES, response),
        filter_response(INVALID_INSTANCES, response),
    )


def aws_response_serializer(response: dict) -> str:
    return json.dumps(response, separators=(",", ":"), default=str)


def filter_response(jq_filter: str, response: dict) -> List[dict]:
    string = aws_response_serializer(response)
    return jq(jq_filter).transform(text=string, multiple_output=True)


def retrieve_os_users(client, instances):
    imageids = [
        instance.get("ImageId") for instance in instances if instance.get("ImageId")
    ]
    response = aws_response_serializer(client.describe_images(ImageIds=imageids))

    query = jq(
        """
        .Images?
            | map({ (.ImageId): {Name, ImageLocation, Description} })
            | add
    """
    ).transform(text=response)

    for instance in instances:
        ami_info = query.get(instance["ImageId"])
        instance["OsUser"] = _osuser_from_ami(ami_info)
    return instances


def _osuser_from_ami(ami_info: dict) -> str:
    keys_to_search = ["Name", "ImageLocation"]
    # Concatenation ami_info[key1] + ami_info[key2] + ... + ""
    lookup_string = reduce(
        op.concat, (ami_info[key] for key in keys_to_search), ""
    ).lower()

    if "ubuntu" in lookup_string:
        os_user = "ubuntu"
    elif "amzn2" in lookup_string:
        os_user = "ec2-user"
    else:
        # Default.
        os_user = "ec2-user"
    return os_user


def push_ssh_key(instance_info, public_key, client=None):
    client = client if client is not None else boto3.client("ec2-instance-connect")
    try:
        resp = client.send_ssh_public_key(
            InstanceId=instance_info["InstanceId"],
            InstanceOSUser=instance_info["OsUser"],
            SSHPublicKey=public_key,
            AvailabilityZone=instance_info["AvailabilityZone"],
        )
    except ClientError as e:
        raise click.ClickException(f"{e}")
    return resp


# JQ SCRIPTS
VALID_INSTANCES = """
        .Reservations[]?.Instances[]?
            |   {
                    Tags: ([(.Tags[]? | {(.Key): .Value})] | add),
                    AvailabilityZone: .Placement.AvailabilityZone,
                    ImageId,
                    InstanceId,
                    PublicIpAddress,
                    LaunchTime
                }
            | select(
                (.Tags | has("Name")) and
                (.Tags.Name | length > 0) and
                (.Tags.Name | contains(" ") | not)
                )
"""

INVALID_INSTANCES = """
        .Reservations[]?.Instances[]?
            |   {
                    Tags: ([(.Tags[]? | {(.Key): .Value})] | add),
                    AvailabilityZone: .Placement.AvailabilityZone,
                    ImageId,
                    InstanceId,
                    PublicIpAddress,
                    LaunchTime
                }
            | select(
                (
                    (.Tags | has("Name")) and
                    (.Tags.Name | length > 0) and
                    (.Tags.Name | contains(" ") | not)
                ) | not)
"""

HAS_NO_TAGS = """
        .Reservations[]?.Instances[]?
            | select(has("Tags") | not)   
            | {
                    AvailabilityZone: .Placement.AvailabilityZone,
                    ImageId,
                    InstanceId,
                    PublicIpAddress,
                    LaunchTime
                }
"""
