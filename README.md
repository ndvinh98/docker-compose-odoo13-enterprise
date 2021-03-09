# Installing Odoo 13 Enterprise with one click

Install [docker](https://docs.docker.com/get-docker/) and [docker-compose](https://docs.docker.com/compose/install/) yourself, then run:
```
$ docker-compose up -d
```

# Usage

Change the folder permission to make sure that the container is able to access the directories:

```
$ mkdir -p postgresql
$ mkdir -p pgadmin4
$ sudo chmod -R 777 addons
$ sudo chmod -R 777 etc
$ sudo chmod -R 777 enterprise
$ sudo chmod -R 777 pgadmin4
$ sudo chmod -R 777 postgresql
```

Run Odoo container in detached mode (be able to close terminal without stopping Odoo):

```
$ docker-compose up -d
```

Then open `localhost:8069` to access Odoo 13.0. If you want to start the server with a different port, change **8069** to another value in **docker-compose.yml**:

```
ports:
 - "8069:8069"
```

If you want to use pgadmin4 to connect postgres database:
open `localhost:1234` to access to pgAdmin4 (username=admin password=admin)

create sever with:
`hostname = pgsql-server`
`port=5432`
`postgres_user = odoo`
`postgres_pasword = odoo`

change to another value in **docker-compose.yml**


# Custom addons

The **addons/** folder contains custom addons. Just put your custom addons if you have any.

# Enterprise addons

The **enterprise/** folder contains enterprise addons.

# Odoo configuration & log

* To change Odoo configuration, edit file: **etc/odoo.conf**
* Log file: **etc/odoo-server.log**

# Odoo container management

**Restart Odoo**:

``` bash
$ docker-compose restart
```

**Kill Odoo**:

``` bash
$ docker-compose down
```

# Remove Odoo & data

Completely remove Odoo and all databases!

``` sh
$ sh remove_odoo.sh
```

# docker-compose.yml

* odoo:13.0
* postgres:11
* pgadmin:latest
