import os
import json
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import click


from common.aws import (
    query_aws_for_instance_info,
    InvalidEc2Instances,
)
from common.ssh import SshPublicKey, PublicKeyNotFound
from common.config import Ec2Config


APP_NAME = "ec2"
CONFIG_DIR = Path(click.get_app_dir(APP_NAME))


@click.group()
@click.pass_context
def app(ctx):
    """
        Use the EC-instance connect tools, mssh and msftp, with instance names instead of
        instance ids with the commands ec2 ssh and ec2 sftp.
        Boto3 is used to retrieve instance ids and correct os user given instance names.
        This only works if your instances have unique names, not containing whitespace.
    """
    # Entry point for CLI. Load custom config.
    ctx.obj = Ec2Config(config_dir=CONFIG_DIR)
    try:
        ctx.obj.load()
    except json.decoder.JSONDecodeError as e:
        raise click.ClickException(
            f"Your configuration file is invalid JSON. Please fix: {ctx.obj.config_dir}"
        )

    try:
        ctx.obj.public_key = ctx.obj.lookup_publickey()
    except PublicKeyNotFound as e:
        click.echo(
            "Rsa key not found. Please generate one with: ssh-keygen -t rsa -f ~/.ssh/id_rsa. Some commands will be unavailable."
        )

    # Confirm AWS credentials.
    ctx.obj.ec2 = boto3.client("ec2")
    ctx.obj.ec2ic = boto3.client("ec2-instance-connect")

    try:
        _ = ctx.obj.ec2.describe_instances(DryRun=True)
    except ClientError as e:
        if "DryRunOperation" not in str(e):
            raise click.ClickException(
                "Failure. Your AWS credentials do not authorize: describe_instances"
            )
    try:
        _ = ctx.obj.ec2.describe_images(DryRun=True)
    except ClientError as e:
        if "DryRunOperation" not in str(e):
            raise click.ClickException(
                "Failure. Your AWS credentials do not authorize: describe_images"
            )


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def iid(obj: Ec2Config, name: str) -> None:
    """ Usage: ec2 iid INSTANCE_NAME. Outputs os_user@instance id, given instance name."""
    answer = lookup_instance_name(obj=obj, name=name)
    output = f"{answer['OsUser']}@{answer['InstanceId']}"
    click.echo(output)


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def ssh(obj: Ec2Config, name: str) -> None:
    """ Usage: ec2 ssh INSTANCE-NAME to use EC2 instance connect to ssh to instance."""
    instance_info = lookup_instance_name(obj=obj, name=name)
    # Call mssh with correct os_user and instance id.
    os.system(f"mssh {instance_info['OsUser']}@{instance_info['InstanceId']}")


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def sftp(obj: Ec2Config, name: str) -> None:
    """ Usage: ec2 sftp INSTANCE-NAME to use EC2 instance connect to sftp to instance."""
    instance_info = lookup_instance_name(obj=obj, name=name)
    # Call msftp with correct OsUser and instance id.
    os.system(f"msftp {instance_info['OsUser']}@{instance_info['InstanceId']}")


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def setup_remote_dev(obj: Ec2Config, name: str) -> None:
    if not obj.public_key:
        click.ClickException(
            "Rsa key not found. Please generate one with: ssh-keygen -t rsa -f ~/.ssh/id_rsa. Must be PEM format."
        )

    instance_info = lookup_instance_name(obj, name)
    ssh_config = Path.home() / ".ssh/config"
    if ssh_config.exists():

        entry_exists = any(name in line for line in ssh_config.read_text().split("\n"))

        if entry_exists:
            return

    remote_auth_file = f"/home/{instance_info['OsUser']}/.ssh/authorized_keys"

    args = f'echo "echo \'{obj.public_key}\' >> \'{remote_auth_file}\'" | mssh {instance_info["OsUser"]}@{instance_info["id"]}'

    click.echo(args)

    os.system(args)

    ec2_entry = f"""Host {name}
    HostName {instance_info['ip']}
    User {instance_info['OsUser']}
    Port 22
    IdentityFile {Path.home() / '.ssh/id_rsa'}"""

    with ssh_config.open(mode="a") as file:
        file.write(f"{ec2_entry}\n")


@app.command()
@click.pass_obj
def config(obj: Ec2Config) -> None:
    """ Open config file in editor. """
    click.launch(str(obj.config_file))


def lookup_instance_name(obj, name):
    answer = obj.lookup_instance(name=name)
    if answer is None:

        instance_dics, invalids, answer = query_aws_for_instance_info(name=name)

        if invalids:
            click.echo(
                "Warning: Some EC2 instances have names containing whitespace or are empty."
            )

        obj.update(instance_dics)
        if answer is None:
            raise click.ClickException("Instance not found")
    return answer
