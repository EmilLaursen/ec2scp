
import boto3
from botocore.exceptions import ClientError
import click

import os
import re

# Learn about the amazing query language for json structures.
# http://jmespath.org/tutorial.html
import jmespath
from pathlib import Path

# Instance ID's are either 8 or 17 characters long, after the i- part.
INST_ID_REGEX = r'(^i-(\w{17}|\w{8}))\W(.+)'

APP_NAME = 'ec2scp'


def get_instance_info(instance_id):
    jmes_query = 'Reservations[0].Instances[0].[InstanceId, ImageId, Placement.AvailabilityZone, PublicIpAddress]'
    try:
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances(InstanceIds=[instance_id])

        result = jmespath.search(jmes_query, response)

        d = {key: val for key, val in zip(['id', 'ami', 'avz', 'ip'], result)}

        # Find OS user. ubuntu or ec2-user
        response2 = ec2.describe_images(ImageIds=[d['ami']])

        image_desc = jmespath.search('Images[*].Description', response2)[0]

        if 'Windows' in image_desc:
            clich.echo('EC2 Instance is running windows.')
            click.Abort()

        os_user = 'ubuntu' if 'Ubuntu' in image_desc else 'ec2-user'
    except ClientError as e:
        click.echo(f'AWS client failed: {e}')
        click.Abort()

    d.update({'user': os_user})
    return d


def push_ssh_key(instance_info, public_key):
    return boto3.client('ec2-instance-connect').send_ssh_public_key(
        InstanceId=instance_info['id'],
        InstanceOSUser=instance_info['user'],
        SSHPublicKey=public_key,
        AvailabilityZone=instance_info['avz'],
    )


def resolve_instance_info_and_paths(src, dst):
    m1 = re.match(INST_ID_REGEX, src)
    m2 = re.match(INST_ID_REGEX, dst)

    if m1 is None and m2 is None:
        click.echo('No EC2 instance-id detected in src or dst. Write correct paths.')
        click.Abort()

    src_is_remote = m1 is not None

    if src_is_remote:
        inst_id, remote_path = m1.group(1), m1.group(3)
    else:
        inst_id, remote_path = m2.group(1), m2.group(3)

    instance_info = get_instance_info(inst_id)

    # If remote path is relative, fix it to remote's home folder.
    if not Path(remote_path).is_absolute():
        remote_path = str(Path('/home/') / instance_info['user'] / remote_path)

    remotehost_prefix = f'{ instance_info["user"] }@{ instance_info["ip"] }:'

    if src_is_remote:
        src_path = remotehost_prefix + remote_path
        dst_path = dst
    else:
        src_path = src
        dst_path = remotehost_prefix + remote_path

    return instance_info, src_path, dst_path


@app.command()
@click.argument('src', type=click.STRING)
@click.argument('dst', type=click.STRING)
def scp(src, dst):
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
    public_key = Path.home() / '.ssh/id_rsa.pub'

    if not public_key.exists():
        click.echo('Rsa key not found. Please generate one with: ssh-keygen -t rsa -f id_rsa.')
        click.Abort()

    public_key = public_key.read_text()

    instance_info, src_path, dst_path = resolve_instance_info_and_paths(src, dst)

    # Push public key for 60 seconds.
    _ = push_ssh_key(instance_info, public_key)

    args = f'scp -i ~/.ssh/id_rsa {src_path} {dst_path}'

    os.system(args)


@app.command()
def create_mssh_config(perm):
    ''' For each availble EC2 instance, export enviroment variables
        $INSTANCE_NAME=INSTANCE_ID
        to enable referencing instances via their name in all commands,
        and not their instance id. Aliases are added to a configfile, which
        is sourced in your shell profile.
    '''
    config_dir = Path(click.get_app_dir(APP_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / 'config'

    try:
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances()
        query = jmespath.search("Reservations[].Instances[].{name: Tags[?Key=='Name'].Value | [0], id: InstanceId}", response)
    except ClientError as e:
        click.echo(f'AWS client failed: {e}')
        click.Abort()

    with config_file.open('a') as writer:
        for name_id_dict in query:
            name = name_id_dict['name']
            inst_id = name_id_dict['id']
            if ' ' not in name:
                line = f'export {name}={inst_id} \n'
                os.environ[name]=inst_id
                writer.write(line)
            else:
                click.echo(f'Found instance name containing whitespace: {name}. Shame on you!')
    click.echo(f'Wrote instance aliases to {config_file}. Change the aliases as you please.')

    shell = os.environ.get('SHELL')

    if 'bash' in shell:
        profile = '.bash_profile'
    elif 'zsh' in shell:
        profile = '.zshrc'
    else:
        click.input()
        profile = click.prompt('Please enter name of shell config', type=str)
    shell_config = Path.home() / profile

    # Source the config file in the shell profile.
    source_line = f'. {str(config_file)}/n'

    if shell_config.exists():
        if source_line in shell_config.read_text():
            return

        with shell_config.open(mode='a') as writer:
            writer.write(source_line)
    else:
        click.echo(f'Shell config {shell_config} not found.')


@app.command()
def push_and_sshconfig():
    pass


@click.group()
def app():
    # Entry point for CLI.
    # TODO: Conform AWS permissions here?
    pass


if __name__ == '__main__':
    app()
