# Percona XtraDB Cluster 5.6
#
# VERSION 1.0
# DOCKER-VERSION 0.81
#
# tag: latest
FROM ubuntu:latest
MAINTAINER Yolanda Robla <info@ysoft.biz>

# update
ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL=C
RUN apt-get update

# percona
RUN apt-key adv --keyserver keys.gnupg.net --recv-keys 1C4CBDCDCD2EFD2A
RUN echo "deb http://repo.percona.com/apt trusty main" > /etc/apt/sources.list.d/percona.list
RUN apt-get update; apt-get -y install qpress percona-xtradb-cluster-56

# install python and deps
RUN apt-get install -y python python-dev python-pip
RUN pip install marathon
RUN rm -rf /var/lib/apt/lists/*

# Remove pre-installed database
RUN rm -rf /var/lib/mysql/*
RUN rm -rf /var/lib/mysql/* /var/run/mysqld/* /etc/my.cnf

# Add MySQL configuration
ADD my.cnf /etc/mysql/my.cnf
RUN chown mysql.mysql /etc/mysql/my.cnf

# Add MYSQL scripts
ADD run.py /run.py
RUN chown root.root /run.py

# Exposed ENV
ENV MYSQL_USER admin
ENV MYSQL_PASS **Random**
ENV REPLICA_MYSQL_USER replica
ENV REPLICA_MYSQL_PASS **Random**

# Add VOLUMEs to allow backup of config and databases
VOLUME ["/etc/mysql", "/var/lib/mysql"]
EXPOSE 3306 4444 4567 4568

CMD ["/run.py"]
