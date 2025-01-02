FROM ubuntu:24.04
LABEL authors="the_lenoz"

RUN apt update && apt install python3.11 openjdk-17-jre


COPY osm2world /
ADD https://osm2world.org/download/files/latest/OSM2World-latest-bin.zip /tmp
RUN ["unzip", "/tmp/OSM2World-latest-bin.zip", "-d", "osm2world"]

COPY requirements.txt /
RUN ["pip", "install", "-r", "requirements.txt"]


COPY ObjFileSplitter /
WORKDIR ObjFileSplitter
RUN ["/ObjFileSplitter/gradlew"]

WORKDIR /

COPY config.json /

COPY src /


ENTRYPOINT ["python", "src/main.py"]