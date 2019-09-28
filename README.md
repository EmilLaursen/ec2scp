# AWS EC2 scp CLI

Wrapper around the EC2 instance connect CLI tools, mssh and msftp, which
 enables using instance names instead of instance ids. E.g. with an instance
 named 'api' with instance id 'i-jadksafkj4rk3desf' you can execute
 ``` ec2 ssh api```
 instead of mssh ubuntu@i-jadksafkj4rk3desf or mssh ec2-user@i-jadksafkj4rk3desf,
 and likewise for msftp.

 Additional subcommands are available. For instance it is possible to use scp,
 by pushing your local rsa key to the instance for 60 seconds, using boto3, and
 then executing the scp command. Again it is possible to use instance names or instance ids,
 istead of the public DNS/ip of the instance, as is usually required by scp.

Use SCP to upload files to EC2 instances using aws IAM credentials instead of ssh keys.
Upload sample:
``` ec2 scp source_file INSTANCE-ID:dest_file ```
Download sample:
``` ec2 scp INSTANCE-NAME:source_file dest_file```
 
Instances can be referenced by instance id or Name. Setup a configuration file and edit it, to give custom aliases to your instances.


You can use relative paths on the remote. Thus
```    ec2 scp t.txt NAME:file.txt```
is equivalent to
```    ec2 scp t.txt NAME:/home/ubuntu/file.txt```
if instance is running ubuntu. 

## Installation.

Clone repo and run make build in your favourite environment.

# TODO:

- [] fix issue with non unique names.
- [x] mssh also has msftp, making the scp subcommand somewhat obsolete. Rewrite whole app to be a wrapper around mssh and msftp calls enabling name aliases in a config, instead of just instance-ids.
- [x] Handle errors and exceptions!
- [x] Dry runs to check credentials.