
import boto3
from botocore.exceptions import ClientError
import click

import os
import json
import re

# Learn about the amazing query language for json structures.
# http://jmespath.org/tutorial.html
import jmespath
from pathlib import Path

# Instance ID's are either 8 or 17 characters long, after the i- part.
INST_ID_REGEX = r'(^i-(\w{17}|\w{8}))\W(.+)'

APP_NAME = 'ec2scp'

class EmptyObj():
    pass

@click.group()
@click.pass_context
def app(ctx):
    # Entry point for CLI.
    # We just want some object for the context, to carry variables.
    ctx.obj = EmptyObj()
    public_key = Path.home() / '.ssh/id_rsa.pub'

    if not public_key.exists():
        click.ClickException('Rsa key not found. Please generate one with: ssh-keygen -t rsa -f id_rsa.')

    public_key = public_key.read_text()
    ctx.obj.public_key = public_key

    # Load custom config.
    config_dir = Path(click.get_app_dir(APP_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    
    ctx.obj.config_file = config_dir / 'config'
    ctx.obj.cfg = None
    if ctx.obj.config_file.exists():
        try:
            cfg = json.loads(ctx.obj.config_file.read_text())
            ctx.obj.cfg = cfg
        except json.decoder.JSONDecodeError as e:
            ctx.obj.config_file.unlink()

    # Confirm AWS credentials.
    ec2 = boto3.client('ec2')
    ctx.obj.ec2 = ec2
    ec2ic = boto3.client('ec2-instance-connect')
    ctx.obj.ec2ic = ec2ic

    try:
        response = ec2.describe_instances(DryRun=True)
    except ClientError as e:
        if not 'DryRunOperation' in str(e):
            click.ClickException('Failure. Your AWS credentials do not authorize: describe_instances')
    try:
        response = ec2.describe_images(DryRun=True)
    except ClientError as e:
        if not 'DryRunOperation' in str(e):
            click.ClickException('Failure. Your AWS credentials do not authorize: describe_images')

def get_instance_info(name=None, inst_id=None, client=None):

    if name is None and inst_id is None:
        raise TypeError('Both name and inst_id can not be None.')

    try:
        ec2 = client if client is not None else boto3.client('ec2')

        kwargs = {'Filters':[{'Name': 'tag:Name', 'Values': [name]}]} if inst_id is None else {'InstanceIds': [inst_id]}
        response = ec2.describe_instances(**kwargs)
        
        if response is None:
            click.ClickException(f'Failure. No instance with Name: {name}')

        # JMESpath query to extract relevant information.
        query_exp = 'Reservations[0].Instances[0].[InstanceId, ImageId, Placement.AvailabilityZone, PublicIpAddress]'
        result = jmespath.search(query_exp, response)

        d = {key: val for key, val in zip(['id', 'ami', 'avz', 'ip'], result)}

        # Find OS user. ubuntu or ec2-user
        response2 = ec2.describe_images(ImageIds=[d['ami']])

        image_desc = jmespath.search('Images[*].Description', response2)[0]

        if 'Windows' in image_desc:
            click.ClickException('EC2 instance is running windows.')

        os_user = 'ubuntu' if 'Ubuntu' in image_desc else 'ec2-user'
    except ClientError as e:
        click.ClickException(f'AWS client failed: {e}')

    d.update({'user': os_user})
    return d


def push_ssh_key(instance_info, public_key, client=None):
    client = client if client is not None else boto3.client('ec2-instance-connect')
    return client.send_ssh_public_key(
        InstanceId=instance_info['id'],
        InstanceOSUser=instance_info['user'],
        SSHPublicKey=public_key,
        AvailabilityZone=instance_info['avz'],
    )


def resolve_instance_info_and_paths(src, dst, obj):
    client = obj.ec2

    # Figure out which one refers to the remote server.
    src_is_remote = ':' in src
    remote_path = src if src_is_remote else dst

    match = re.match(INST_ID_REGEX, remote_path)
    # Did caller use an instance-id or instance name to refer to remote?
    name_used = match is None

    identifier, path = tuple(remote_path.split(sep=':'))

    # Is name from config, or actual instance name?
    if obj.cfg is not None:
        instance_id = obj.cfg.get(identifier)

        # name found in config - overwrite identifier with associated instance_id.
        if instance_id is not None:
            identifier = instance_id
            name_used = False
        else:
            click.ClickException('name not found in cfg.')

    # Retrieve all instance information based on name or instance-id.
    kwargs = {'name' if name_used else 'inst_id': identifier, 'client': client}
    inst_info = get_instance_info(**kwargs)
    
    # If remote path is relative, fix it to remote's home folder.
    if not Path(path).is_absolute():
        path = str(Path('/home/') / inst_info['user'] / path)
    # Actual remote address used in scp call.
    remotehost_prefix = f'{ inst_info["user"] }@{ inst_info["ip"] }:'

    if src_is_remote:
        src_path = remotehost_prefix + path
        dst_path = dst
    else:
        src_path = src
        dst_path = remotehost_prefix + path

    return inst_info, src_path, dst_path


@app.command()
@click.argument('src', type=click.STRING)
@click.argument('dst', type=click.STRING)
@click.pass_obj
def scp(obj, src, dst):
    ''' \b
        Use SCP to upload files to EC2 instances using aws IAM credentials.
        Usage:
            upload:       ec2scp source_file INSTANCE-ID:dest_file
            download:     ec2scp INSTANCE-ID:source_file dest_file
        Unlike normal scp calls, you do not reference the remote via USER@IP-ADDESSS:PATH.
        Instead you use the EC2 instance id. A sample call could be:
            ec2scp t.txt i-09056998a62502002:/home/ubuntu/file.txt
        You can use relative paths on the remote. So the above call is equivalent to
            ec2_scp t.txt INSTANCE-ID:file.txt
        The Os-User is automatically resolved as ubuntu or ec2-user, from the instance-id.
    '''
    instance_info, src_path, dst_path = resolve_instance_info_and_paths(src, dst, obj)

    # Push public key for 60 seconds.
    _ = push_ssh_key(instance_info, obj.public_key, client=obj.ec2ic)
    
    args = f'scp -i ~/.ssh/id_rsa {src_path} {dst_path}'

    os.system(args)


@app.command()
@click.pass_obj
def make_config(obj):
    ''' For each availble EC2 instance, export enviroment variables
        $INSTANCE_NAME=INSTANCE_ID
        to enable referencing instances via their name in all commands,
        and not their instance id. Aliases are added to a configfile, which
        is sourced in your shell profile.
    '''
    ec2 = obj.ec2
    try:
        response = ec2.describe_instances()
        query = jmespath.search("Reservations[].Instances[].{name: Tags[?Key=='Name'].Value | [0], id: InstanceId}", response)
    except ClientError as e:
        click.ClickException(f'AWS client failed: {e}')

    if obj.cfg is None:
        obj.cfg = {}

    obj.cfg.update({
        name_id_dict['name']: name_id_dict['id']
        for name_id_dict in query
        if ' ' not in name_id_dict['name']
    })

    json.dump(obj.cfg, obj.config_file.open('w'), indent=4)
    click.echo(f'Wrote instance aliases to {obj.config_file}. Change the aliases as you please.')


@app.command()
@click.argument('identifier', type=click.STRING)
@click.pass_obj
def push(obj, identifier):
    match = re.match(INST_ID_REGEX, identifier)
    
    # Did caller use an instance-id or instance name?
    name_used = match is None

    # Is name from config, or actual instance name?
    if obj.cfg is not None:
        instance_id = obj.cfg.get(identifier)

        # name found in config - overwrite identifier with associated instance_id.
        if instance_id is not None:
            identifier = instance_id
            name_used = False
        else:
            click.ClickException('name not found in cfg.')
    
    # Retrieve all instance information based on name or instance-id.
    inst_info = get_instance_info(name=identifier) if name_used else get_instance_info(inst_id=identifier)
    
    _ = push_ssh_key(inst_info, obj.public_key)


if __name__ == '__main__':
    app()
