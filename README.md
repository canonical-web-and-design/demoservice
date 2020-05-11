# Demo service asdadsasdads

Spin up ./run demos!

This service starts demos automatically from GitHub webhooks, as well as manually. For a full overview of this application, view [OVERVIEW.md](OVERVIEW.md).

Information about our deployments can be found on our [Google Drive document](https://docs.google.com/document/d/1Yw0uU9zp1Tc2l01loDSTdhc72LibSHYytWRLTVhCB58/edit)

## Quickstart development

### The demoservice app

#### Docker Compose

A close version to the production set up can be started using docker compose. All services are defined under docker-compose.yml in the project root.

``` bash
docker-compose up
```

(or if you want to run it in the background, use `docker-compose up -d`)

This runs on the web app on http://0.0.0.0:8099. It should work well for simple development.

Check the instructions below for running fake demos if you want to quickly update templates.

*Dependencies require a rebuild:*

Every time dependencies change, you'll need to recreate the images before running the app again:

``` bash
docker-compose build
docker-compose up
```

#### The hard way (Python virtual env)

The current recommended method for starting the server is to set up a Python 3 virtual env and run:

``` bash
DJANGO_DEBUG=True CELERY_TASK_ALWAYS_EAGER=True python3 ./app/manage.py runserver
```

Running the service with `DJANGO_DEBUG=True` will run the database as sqlite and run the message queue tasks immediately without using a message queue.

The official Python documentation has a page on [virtual environments](https://docs.python.org/3/tutorial/venv.html). Another great option is [pyenv](https://github.com/pyenv/pyenv) with [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).

### Running fake demos

The UI isn't useful without running demos. If you want to run a demo, there is a helper script for a lightweight demo:

``` bash
# ./bin/create_fake_demo [repo_name] [pull_request_id]
./bin/create_fake_demo www.ubuntu.com 123
```

They will run in the background. Delete all the demos with:

``` bash
./bin/delete_fake_demos
```

### Sending fake webhooks in development

If you need to test the webhook views or simply need to fake a webhook, you can use the scripts provided in bin/. 
You will find sample payloads to use with the scripts in bin/data. Webhook signature validation should be disabled in DEBUG mode.
It's highly likely that you will need to customize this sample payloads to use them.

``` bash
./bin/send_fake_github_webhook bin/data/github.json
./bin/send_fake_launchpad_webhook bin/data/launchpad.json
```
