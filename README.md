# log-extractor
ART log extractor, download a job artifacts, unpack all archives and parse relevant logs.

# Install
`sudo pip install . -U`

Jenkins config file `~/.jenkins.config` should be under user home directory and must include

```
[SETTING]
server=https://rhev-jenkins.rhev-ci-vms.eng.rdu2.redhat.com
```

# Usage:
`log-extractor --job rhv-master-ge-runner-network --build 275 --team networking --logs engine.log,vdsm.log`


