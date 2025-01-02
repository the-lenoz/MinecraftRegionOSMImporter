FROM ubuntu:24.04
LABEL authors="the_lenoz"

RUN apt update && apt install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa && apt update &&\
     apt install -y python3.10 openjdk-17-jre zip unzip python3-pip git


COPY osm2world /osm2world
ADD https://osm2world.org/download/files/latest/OSM2World-latest-bin.zip /tmp
RUN ["unzip", "/tmp/OSM2World-latest-bin.zip", "-d", "osm2world"]


RUN ["/usr/bin/python3.10", "-m", "pip", "install", "-U", "setuptools"]
COPY requirements.txt /
RUN ["/usr/bin/python3.10", "-m", "pip", "install", "-r", "requirements.txt", "--break-system-packages"]


COPY ObjFileSplitter /ObjFileSplitter
WORKDIR ObjFileSplitter
RUN ["/bin/sh", "gradlew"]

WORKDIR /

COPY config.json /

COPY src /src


ENTRYPOINT ["/usr/bin/python3.10", "/src/main.py"]