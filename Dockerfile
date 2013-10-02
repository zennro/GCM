# GCM.py is a very light Google Cloud Messaging testing server.

FROM ubuntu:12.10

MAINTAINER Victor Vieux <victorvieux@gmail.com>

RUN apt-get update 
RUN apt-get install python-bottle -y

ADD ./GCM.py /

ENTRYPOINT ["python", "GCM.py"]

EXPOSE 8080