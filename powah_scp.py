import boto3
from botocore.exceptions import ClientError
import click

from common.aws import (
    get_instance_info,
    resolve_instance_info_and_paths,
    valid_available_instances,
    retrieve_os_users,
)

from common.config import update_config, load_config

import os
import json

# Learn about the amazing query language for json structures.
# http://jmespath.org/tutorial.html
from pathlib import Path


APP_NAME = "ec2"


class EmptyObj:
    pass


@click.group()
@click.pass_context
def app(ctx):
    """
        Use the EC-instance connect tools, mssh and msftp, with instance names instead of
        instance ids with the commands ec2 ssh and ec2 sftp.
        Boto3 is used to retrieve instance ids and correct os user given instance names.
        This only works if your instances have unique names, not containing whitespace.
    """
    # Entry point for CLI.
    # We just want some object for the context, to carry variables.
    ctx.obj = EmptyObj()
    public_key = Path.home() / ".ssh/id_rsa.pub"

    if not public_key.exists():
        public_key = None
        click.echo(
            "Rsa key not found. Please generate one with: ssh-keygen -t rsa -f ~/.ssh/id_rsa. Some commands will be unavailable."
        )
    else:
        public_key = public_key.read_text()

    ctx.obj.public_key = public_key

    # Load custom config.
    try:
        ctx.obj.cfg, ctx.obj.config_file = load_config(Path(click.get_app_dir(APP_NAME)))
    except json.decoder.JSONDecodeError:
        raise click.ClickException(
            f"Your configuration file is invalid JSON. Please fix: {ctx.obj.config_file}"
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


def push_ssh_key(instance_info, public_key, client=None):
    client = client if client is not None else boto3.client("ec2-instance-connect")
    try:
        resp = client.send_ssh_public_key(
            InstanceId=instance_info["id"],
            InstanceOSUser=instance_info["user"],
            SSHPublicKey=public_key,
            AvailabilityZone=instance_info["avz"],
        )
    except ClientError as e:
        raise click.ClickException(f"{e}")
    return resp


def lookup_instance_name(obj, name):
    instance_info = obj.cfg.get(name)

    if instance_info is None:

        click.echo("Not found in config. Consider running make-config.")

        instance_info = get_instance_info(name=name, inst_id=None)

        update_config(obj.cfg, instance_info)

        if instance_info is None:
            raise click.ClickException("Instance not found")
    return instance_info


@app.command()
@click.argument("src", type=click.STRING)
@click.argument("dst", type=click.STRING)
@click.pass_obj
def scp(obj, src, dst):
    """
        \b
        Use SCP to upload files to EC2 instances using aws IAM credentials instead of ssh keys.
        Usage:
            upload:       ec2 scp source_file INSTANCE-ID:dest_file
            download:     ec2 scp INSTANCE-NAME:source_file dest_file

        Instances can be referenced by instance id or Name. Setup a configuration file and edit it, to give custom aliases to your instances.

        \b
        You can use relative paths on the remote. Thus
            ec2 scp t.txt NAME:file.txt
        is equivalent to
            ec2 scp t.txt NAME:/home/ubuntu/file.txt
        if instance is running ubuntu. 
    """
    instance_info, src_path, dst_path = resolve_instance_info_and_paths(src, dst, obj)

    # Push public key for 60 seconds.
    _ = push_ssh_key(instance_info, obj.public_key, client=obj.ec2ic)

    args = f"scp -i ~/.ssh/id_rsa {src_path} {dst_path}"

    os.system(args)


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def iid(obj: EmptyObj, name: str):
    """ Usage: ec2 iid INSTANCE_NAME. Outputs os_user@instance id, given instance name."""
    # Is name from config, or actual instance name?
    if obj.cfg is not None:
        # name found in config
        if obj.cfg.get(name) is not None:
            instance = obj.cfg.get(name)
            output = f'{instance["os_user"]}@{instance["id"]}'
        else:
            instance_info = get_instance_info(name=name, inst_id=None)
            output = f'{instance_info["os_user"]}@{instance_info["id"]}'

    click.echo(output)


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def ssh(obj: EmptyObj, name: str):
    """ Usage: ec2 ssh INSTANCE-NAME to use EC2 instance connect to ssh to instance."""
    instance_info = lookup_instance_name(obj, name)

    # Call mssh with correct os_user and instance id.
    os.system(f'mssh {instance_info["os_user"]}@{instance_info["id"]}')


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def sftp(obj: EmptyObj, name: str):
    """ Usage: ec2 sftp INSTANCE-NAME to use EC2 instance connect to sftp to instance."""
    instance_info = lookup_instance_name(obj, name)

    # Call msftp with correct os_user and instance id.
    os.system(f'msftp {instance_info["os_user"]}@{instance_info["id"]}')


@app.command()
@click.argument("name", type=click.STRING)
@click.pass_obj
def setup_remote_dev(obj, name):
    if not obj.public_key:
        click.ClickException(
            "Rsa key not found. Please generate one with: ssh-keygen -t rsa -f ~/.ssh/id_rsa. Must be PEM format."
        )

    instance_info = lookup_instance_name(obj, name)

    ssh_config = Path.home() / ".ssh/config"

    entry_exists = any(
        instance_info["id"] in line for line in ssh_config.read_text().split("\n")
    )

    if entry_exists:
        return

    remote_auth_file = f"/home/{instance_info['os_user']}/.ssh/authorized_keys"

    args = f"echo 'echo {obj.public_key} >> {remote_auth_file}' | mssh {instance_info['os_user']}@{instance_info['id']}"

    ec2_entry = f"""Host {instance_info['id']}
    HostName {instance_info['ip']}
    User {instance_info['os_user']}
    Port 22
    IdentityFile {Path.home() / '.ssh/id_rsa'}
    """

    with ssh_config.open(mode="a") as file:
        file.write(f"\n{ec2_entry}\n")


@app.command()
@click.option("--edit", "-e", is_flag=True, help="Launch config file in editor.")
@click.pass_obj
def make_config(obj: EmptyObj, edit: bool):
    """ Usage: ec2 make_config --edit """
    ec2 = obj.ec2

    try:
        valid_instances, invalid_instances = valid_available_instances(ec2)

    except ClientError as e:
        raise click.ClickException(f"AWS client failed: {e}")

    if invalid_instances:
        click.echo(
            "Warning: Unamed instances, and instances with whitespace in their names, are ignored."
        )

    try:
        instance_dics = retrieve_os_users(ec2, valid_instances)

    except ClientError as e:
        raise click.ClickException(f"AWS client failed: {e}")

    update_config(obj, instance_dics)

    if obj.cfg is None:
        obj.cfg = {}

    obj.cfg.update(
        {instance_dic["name"]: instance_dic for instance_dic in instance_dics}
    )

    json.dump(obj.cfg, obj.config_file.open("w"), indent=4)

    if edit:
        click.launch(str(obj.config_file))
    else:
        click.echo(
            f"Wrote instance aliases to {obj.config_file}. Change the aliases as you please."
        )


if __name__ == "__main__":
    app()
