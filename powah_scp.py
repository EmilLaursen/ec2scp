import os
import json
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import click
from common.aws import query_aws_for_instance_info
from common.ssh import SshPublicKey, PublicKeyNotFound, SshSimpleParser
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
@click.option("--public_key", "--pk", type=click.STRING, default="id_rsa.pub")
@click.option("--port", "--p", type=click.INT, default=22)
@click.pass_obj
def setup_remote_dev(obj: Ec2Config, name, public_key, port) -> None:
    """ Upload host publickey to remote EC2 instance's authorized keys
        and update local ssh config with instance information.
        ssh INSTANCE_NAME
        and therefore SSH Remote development through Vscode.
    """
    key_path = Path.home() / ".ssh" / public_key
    try:
        key_text = SshPublicKey(path=key_path).as_text()
    except PublicKeyNotFound as e:
        raise click.ClickException(str(e))

    instance_info = lookup_instance_name(obj, name)

    ssh_config = SshSimpleParser(Path.home() / ".ssh/config")
    ssh_config.update_entry(
        instance_id=instance_info["InstanceId"],
        launch_date=instance_info["LaunchTime"],
        host=instance_info["Tags"]["Name"],
        hostname=instance_info["PublicIpAddress"],
        user=instance_info["OsUser"],
        port=str(port),
        public_key_path=key_path,
    )

    remote_auth_file = f"/home/{instance_info['OsUser']}/.ssh/authorized_keys"

    args = f'echo "echo \'{key_text}\' >> \'{remote_auth_file}\'" | mssh {instance_info["OsUser"]}@{instance_info["InstanceId"]}'
    click.echo(args)
    os.system(args)


@app.command()
@click.pass_obj
def config(obj: Ec2Config) -> None:
    """ Open config in editor. """
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
