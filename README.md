# log-extractor
ART log extractor, download a job artifacts, unpack all archives and parse relevant logs.

# Install
sudo pip install . -U

# Usage:
log-extractor --job rhv-master-ge-runner-network --build 275 --team networking --logs engine.log,vdsm.log
