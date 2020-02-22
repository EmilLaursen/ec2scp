import pytest

from common.ssh import *

from hypothesis import given, example
import hypothesis.strategies as st

ssh_config = """
Host jetson
  HostName 192.168.0.13
  User nano1
Host 192.168.0.10
  HostName 192.168.0.10
  User pi
Host server1
     HostName server1.cyberciti.biz
     User nixcraft
     Port 4242
     IdentityFile /nfs/shared/users/nixcraft/keys/server1/id_rsa
Host nas01
     HostName 192.168.1.100
     User root
     IdentityFile ~/.ssh/nas01.key
### default for all ##
Host *
     ForwardAgent no
     ForwardX11 no
     ForwardX11Trusted yes
     User nixcraft
     Port 22
     Protocol 2
     ServerAliveInterval 60
     ServerAliveCountMax 30
 
## override as per host ##
Host server1
     HostName server1.cyberciti.biz
     User nixcraft
     Port 4242
     IdentityFile /nfs/shared/users/nixcraft/keys/server1/id_rsa
 
## Home nas server ##
Host nas01
     HostName 192.168.1.100
     User root
     IdentityFile ~/.ssh/nas01.key
 
## Login AWS Cloud ##
Host aws.apache
     HostName 1.2.3.4
     User wwwdata
     IdentityFile ~/.ssh/aws.apache.key
 
## Login to internal lan server at 192.168.0.251 via our public uk office ssh based gateway using ##
## $ ssh uk.gw.lan ##
Host uk.gw.lan uk.lan
     HostName 192.168.0.251
     User nixcraft
     ProxyCommand  ssh nixcraft@gateway.uk.cyberciti.biz nc %h %p 2> /dev/null
 
## Our Us Proxy Server ##
## Forward all local port 3128 traffic to port 3128 on the remote vps1.cyberciti.biz server ## 
## $ ssh -f -N  proxyus ##
Host proxyus
    HostName vps1.cyberciti.biz
    User breakfree
    IdentityFile ~/.ssh/vps1.cyberciti.biz.key
    LocalForward 3128 127.0.0.1:3128
"""

cfg = Path("/home/emilime/.ssh/config")


@pytest.fixture
def sshsimpleparser():
    simple = SshSimpleParser()
    return simple


@given(st.text())
@example(ssh_config)
def test_get_stanzas(sshsimpleparser, s):
    stanzas = sshsimpleparser._get_stanzas(s)

    assert all([len(line) > 0 for stanza in stanzas for line in stanza]) and all(
        [stanza[0].strip().startswith("host ") for stanza in stanzas]
    )
