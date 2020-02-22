# AWS EC2 scp CLI

The AWS CLI, [EC2 Instance connect](https://github.com/aws/aws-ec2-instance-connect-cli), is a convenient tool for managing access to EC2 instances without any SSH keys, but through IAM credentials instead. However, a major nuisance is the fact that you have to use the instance ID to connect to an instance.

This tool makes it possible for you to use the instance Name tag, which you choose yourself.
E.g. with an instance named 'api' with instance id 'i-jadksafkj4rk3desf' you can execute
 ``` ec2 ssh api```
 instead of mssh ubuntu@i-jadksafkj4rk3desf or mssh ec2-user@i-jadksafkj4rk3desf, and likewise for msftp. The tool will figure out the correct instance-id from the given name, and also the 
 correct OS-user (say ubuntu or ec2-user for Amazon Linux 2).


# Remote VScode development on EC2 instances.
 Unfortunately, the SSH Remote Development feature of VScode does not work with EC2 Instance Connect. Therefore, there is an subcommand to upload your SSH key to the server and setup your SSH config with instance information.
 ``` ec2 setup-remote api```
 Then simply launch SSH Remote from VScode and choose your instance.

## Installation.

Clone repo and run make build in your favourite environment.

# TODO:

- [ ] handle instance reboots (possible new ip!) for ssh config
- [ ] add entrypoint to wipe vscode server on remote host (vscode updates sometimes makes host server version incompatible).
- [ ] interface should be somewhat stable, implement unit tests.
- [ ] Handle different aws profiles more gracefully.
- [x] fix issue with non unique names.
- [x] mssh also has msftp, making the scp subcommand somewhat obsolete. Rewrite whole app to be a wrapper around mssh and msftp calls enabling name aliases in a config, instead of just instance-ids.
- [x] Handle errors and exceptions!
- [x] Dry runs to check credentials.
- [x] implement rudimentary parser for ssh configs.