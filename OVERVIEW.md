# Demo service overview

## Architecture

This service is a Django based service, running with a Celery message queue system. The compiled Docker image has two entry points to run; as either the Django based web frontend, or the Celery worker. The web service runs the web interface and webhook endpoints, and the Celery worker will perform any background tasks that have been added to the message queue.

This service is usable in a variety of environments but it has been configured to run in a Rancher system. The rancher configuration is a [docker-compose.yml](./templates/demoservice/0/docker-compose.yml) file at its core, with some configuration options for Rancher. The service starts with these components:

- `demoservice-lb`: Load balancer to route traffic to web services
- App runs as two services
  - `demoservice-web`: Django frontend service
  - `demoservice-worker`: Celery worker
- `demoservice-db`: Postgres database
- `demoservice-rabbit`: RabbitMQ database

Separately to this, a [Traefik](https://traefik.io/) instance runs to route traffic. This will be explained a little more clearly later in the document.

### App structure

A simple overview of the folder structure:

```sh
├── app
│   └── demoservice
│       ├── libs
│       │   └── [DJANGO/PYTHON HELPER FILES]
│       ├── migrations
│       │   └── [DJANGO DATABASE MIGRATION SCRIPTS]
│       ├── templates
│       │   └── [DJANGO HTML TEMPLATES]
│       ├── tasks.py
│       └── views.py
├── bin
│   └── [HELPER SCRIPTS]
└── templates
    └── [RANCHER DEPLOYMENT TEMPLATE]
```

Inside the demoservice folder there are a couple of base files:

- `tasks.py`
  - Celery tasks and configuration
- `views.py`
  - webhook endpoint
  - frontend management pages

## Flow

### Webhooks

_**When receiving webhooks, it is important to always check the secret hash. ALWAYS. This is detailed in the following section.**_

#### Github webhooks

Github webhooks are pushed to the `/webhook/github` path. When the app receives a payload from GitHub it will check the signature against a hash made from our secret. We must check this to ensure that only webhooks from verified sources are started.

Github can send a variety of event types. The type is checked against the header `HTTP_X_GITHUB_EVENT`. This then checks the type of event in the payload content. We primarily listen for `opened`, `closed`, and `synchronized`. Synchronized is triggered when a branch has been updated; often by rebasing or pushing new commits.

When the webhook has been understood, it queues up a relevant task in the message queue. It will either start/update a demo, or delete one. The task to start a demo should stop any previous running demos for that branch. This logic is used for both starting and restarting demos.

### Frontend management

The demo service has a simple admin/management interface for viewing demos, as well as starting and stopping them. This interface requires an openid login and this should be enforced to prevent unauthorised users creating demos on the system.

Demo containers are created with a Docker label of `run.demo=true`. Using this label, the app filters and displays running containers from Docker which match this label. This is done with the Python Docker library. An example of this would be:

```python3
import docker

docker_client = docker.from_env()
running_containers = docker_client.containers.list(
    filters={
        'status': 'running',
        'label': 'run.demo',
    }
)
```

Here is an example to do the same with the Docker shell command:

```sh
docker ps -f "label=run.demo"
```

### Running tasks

- Task chain
- Retries a few times with some back off
- When worker has space, runs next task in queue
- Set labels

Tasks are created as a [Celery chain](http://docs.celeryproject.org/en/latest/userguide/canvas.html#chains). This allows multiple smaller tasks to run in sequence and act independantly. For example, the step to notify GitHub is run as a seperate task which can retry without the overhead of restarting the whole demo. This is particularly beneficial for steps involving network requests as they can fail because of short lived network errors.

The tasks are added to the RabbitMQ service through Celery. When a Celery worker is free it will pick up the latest task of the top of the queue. If a task fails, they are configured to retry multiple times with an exponential back off. The first failure will wait 2 seconds, the seconds attempt will wait 4 seconds, then 8 seconds, then 16 seconds and so on.

New demos are run by downloading the source code to a `/srv/demos` subfolder and running `./run serve --detached` in this folder. Docker labels are used to add metadata and manage the demos. It is beneficial to add more data than you need as it is harder to add later without restarting demos.

These are a list of labels which are added for the demo system:

- `run.demo=true` - Flag this is a demo container
- `run.demo.url` - Base hostame of demo
- `run.demo.url_full` - Full URL for links
- `run.demo.github_user` - GitHub owner user/organisation of repository
- `run.demo.github_repo` - GitHub repository name
- `run.demo.github_pr` - GitHub pull request ID

Here is an example of a full command that the demo service runs:

```sh
CANONICAL_WEBTEAM_RUN_SERVE_DOCKER_OPTS="\
  -l run.demo=True \
  -l run.demo.github_user=canonical-websites \
  -l run.demo.github_repo=snapcraft.io \
  -l run.demo.github_pr=954 \
  -l run.demo.url=snapcraft.io-pr-954.run.demo.haus \
  -l run.demo.url_full=http://snapcraft.io-pr-954.run.demo.haus/ \
  -l traefik.enable=true \
  -l traefik.frontend.rule=Host:snapcraft.io-pr-954.run.demo.haus \
  -l traefik.port=59906 \
  " ./run serve --detached --port 5990
```

## Demo domain routing

For Traefik, we add configuration labels which are used to route traffic:

- `traefik.enable=true` - Flag this container as managed by Traefik
- `traefik.frontend.rule` - Add Traefik routing rule
- `traefik.port` - Tell Traefik which port to connect to

Traefik will poll the current running Docker containers and find any services with these labels. The [Traefik Docker documentation](https://docs.traefik.io/configuration/backends/docker/#labels-overriding-default-behavior) contains full details about these labels.

## Quirks

This service connects to GitHub as the [webteam-app](https://github.com/webteam-app) user. It needs to be added as a contributor to a repo to view other contributors and verify they have permissions. This could be fixed by converting the demoservice to a full GitHub app.

The app require running as a privileged Docker container to start new Docker containers on the host machine. Finding an alternative API to start containers would be very beneficial.

The demo system assumes that it all runs on a single host. The management view shows Docker containers on the same machine, and the stop demo job assumes it is running on that machine in `/srv/demos`. This could be mitigated by abstracting the demo logic into dedicated images and keeping the cloned repository off the file system, as mentioned in [issue 21](https://github.com/canonical-webteam/demoservice/issues/21).
