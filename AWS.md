- [Damvad DS Introduction](#damvad-ds-introduction)
  - [Why use miniconda (also on EC2 instances)](#why-use-miniconda-also-on-ec2-instances)
    - [Linux miniconda installation](#linux-miniconda-installation)
    - [MacOS miniconda installation](#macos-miniconda-installation)
- [AWS general knowledge](#aws-general-knowledge)
  - [Connecting to EC2 instances.](#connecting-to-ec2-instances)
- [Amazing Tasks You Can Do:](#amazing-tasks-you-can-do)

# Damvad DS Introduction

## Why use miniconda (also on EC2 instances)

[conda](https://docs.conda.io/en/latest/miniconda.html) can manage your virtual environments, but it is also a package manager like pip. It hsa **advantages** over pip, for data scientists. Here is a single reason:

The scientific computing stack relies on scipy and numpy. It is possible for scipy and numpy to use computation backends written in C. In particular, you want to make sure BLAS and LAPACK are used. In fact, you want to make sure you are using a version of BLAS which is optimized for your particular CPU. The gains in speed can be anywhere from 2-30 times the default! In particular, fresh EC2 instances do _NOT_ have the optimized BLAS version, which is BLAS MLK, created by Intel for intel CPU's.

Ask yourself the following questions.

1. Do you know how to check which BLAS backend your numpy library currently uses?
2. Do you know how to change this backend?
3. Do you know how to install alternative versions of BLAS and LAPACK, and make numpy point to these new versions?
4. Do you know how to compile and build numpy from scratch on your machine?

Unless you can answer yes to all of the above, you should probably be using conda to install scipy (and thus numpy), as ``` conda install scipy ``` will automatically take care of _**EVERYTHING**_. Answer to Q1 is:
```python
import numpy
numpy.show_config()
```
the answer to the other 3 is [miniconda](https://docs.conda.io/en/latest/miniconda.html) (or lots of [google](https://www.google.com/)).
### Linux miniconda installation
```bash 
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash Miniconda3-latest-Linux-x86_64.sh
```
### MacOS miniconda installation
```bash 
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh && bash Miniconda3-latest-MacOSX-x86_64.sh
```

You can use the speed.py script to test the speed difference. Install scipy using pip in a new environment, and using conda in another - then run speed.py.


# AWS general knowledge

New instances should follow these guidelines:

1. RE tag/value pairs:
   1. Name:


## Connecting to EC2 instances.

We use [EC2 Instance Connect](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Connect-using-EC2-Instance-Connect.html) to manage SSH access to our EC2 instances. To use this you must:


1. Install the [AWS cli](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html), and [EC2 instance connect cli](https://github.com/awsdocs/amazon-ec2-user-guide/blob/master/doc_source/Connect-using-EC2-Instance-Connect.md) via
```pip install awscli ec2instanceconnectcli ```
2. (Optional) You installed the tools in some virtual environment, probably base. It could be convienient to have global access to the ``` aws ``` and ``` mssh ``` CLIs. To do this simply add the path to the binaries, in your environment, to your PATH:
``` export PATH=$PATH:${$(which mssh)%%mssh} ```. This could be added to your shell config, like .bashrc og .zshrc.
3. Configure aws cli using your IAM credetials. Run ``` aws configure --profile PROFILENAME ```.
and enter credentials. Our region is eu-central-1, and you can choose json as output.
4. Find the instance-id of the EC2 instance you wish to connect to, then run ``` mssh ubuntu@INSTANCE-ID ``` or simply ```msssh INSTANCE-ID ``` on Amazon Linux 2 instances. You will now ssh into the EC2 instance, if your IAM credentials allow it.

No manual transfer of SSH keys! How smart! But how do I [scp](https://linux.die.net/man/1/scp) files to my EC2 instance?
Fear not. You can [push SSH keys](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-methods.html#ec2-instance-connect-connecting-aws-cli) to the instance using the aws cli. These keys are live for 60 seconds, then deleted. As shown in previous link, just run (ubuntu swapped with ec2-user for Amazon Linux 2)
```
aws ec2-instance-connect send-ssh-public-key --region us-west-2 --instance-id i-001234a4bf70dec41EXAMPLE --availability-zone us-west-2b --instance-os-user ubuntu --ssh-public-key file://my_rsa_key.pub
```
and then ```scp -i my_rsa_key_pub SOURCE DEST ``` as usual. Note that you do not even need to generate an initial SSH key pair when launching a fresh EC2 instance running Amazon Linux 2.  Note you can change user in the aws cli, by ``` export AWS_DEFAULT_USER=otheruser```, which changes user for the duration of the shell session.




# Amazing Tasks You Can Do:

- [] Write a tiny CLI for easy scp'ing to EC2 instances, wrapping the 2 commands above. Use boto3 library, and possibly click. Using boto3 it is possible to extract region, availability zone, ip, and which OS the instance is running (to decide --instance-os-user. Assuming a users public key always has the default name ```id_rsa.pub``` a sample use could be:
```bash
POWAH_scp_tool INSTANCEID SOURCE_FILE DEST_FILE
```
- [] Write a Slack BOT serving this documentation on command.
- [] Implement AWS CloudWatch integrated logging to our flask API's hosted on AWS. Consider using [WatchTower](https://watchtower.readthedocs.io/en/latest/). 
