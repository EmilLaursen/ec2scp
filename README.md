# AWS EC2 scp CLI


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

## Installation.

Clone repo and run make build in your favourite environment.


- [x] Handle errors and exceptions!
- [x] Dry runs to check credentials.