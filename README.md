# log-extractor
When running lots of tests, it is easy for logs to get huge and trying to
search through them to find the data that is relevant to the portion of time
a specific test was running for is tedious, even with time stamping.
log-extractor rei-structures the logs, creating per testcase log files.

# Install
`sudo pip install . -U`

# Usage:
Source can be either:

Jenkins build URL:
```bash
$ log-extractor \
    --source https://jenkins.example.com/job/rhv-master-ge-runner-network/275 \
    --team networking \
    --logs engine.log,vdsm.log
```

Locally downladed logs in zip format from Jenkins job artifacts:
```bash
$ log_extractor \
    --source /home/kkoukiou/Downloads/archive.zip \
    --team networking \
    --logs engine.log,vdsm.log
```

Local folder containing the logs:
```bash
$ log_extractor \
    --source /home/kkoukiou/Downloads/archive \
    --team networking \
    --logs engine.log,vdsm.log
```
