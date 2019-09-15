
import boto3
from botocore.exceptions import ClientError
import click

import os
import re
import jmespath
from pathlib import Path

INST_ID_REGEX = r'(^i-(\w{17}|\w{8}))\W(.+)'


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
            click.Abort('EC2 Instance is running windows.')

        os_user = 'ubuntu' if 'Ubuntu' in image_desc else 'ec2-user'
    except (ClientError) as e:
        raise e

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


@click.command()
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
        click.echo('Public rsa key not found. Please generate one with ssh-keygen XXX.')
        click.Abort()

    public_key = public_key.read_text()

    instance_info, src_path, dst_path = resolve_instance_info_and_paths(src, dst)

    # Push public key for 60 seconds.
    _ = push_ssh_key(instance_info, public_key)

    args = f'scp -i ~/.ssh/id_rsa {src_path} {dst_path}'

    os.system(args)


if __name__ == '__main__':
    scp()
