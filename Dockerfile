FROM ubuntu:24.04

# Install packages
RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt install -y python3 python3-dev python3-pip git

# Copy data
WORKDIR /opt/finitecraft
COPY . /opt/finitecraft

# Install python requirements
RUN python3 -m pip install -r requirements.txt --break-system-packages

# Run finiteCraft :)
# CMD python3 crafter.py --uri mongodb://172.21.0.2
CMD sleep 1202390349402