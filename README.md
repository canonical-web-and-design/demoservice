# Demo service

Spin up ./run demos!


## Dev

### The demoservice app

The current recommended method for starting the server is to set up a Python 3 virtual env and run:

``` bash
python3 ./app/manage.py runserver
```

Alternatively you can use Docker with a little helper script which *should* run.

``` bash
./bin/start_docker_dev
```

### (Optional) Running fake demos

The UI isn't useful without running demos. If you want to run a demo, there is a helper script for a lightweight demo:

``` bash
# ./bin/create_fake_demo [repo_name] [pull_request_id]
./bin/create_fake_demo www.ubuntu.com 123
```

They will run in the background. Delete the demos with:

``` bash
# ./bin/create_fake_demo [repo_name] [pull_request_id]
./bin/delete_fake_demos
```

### (Very optional) Spinning up workers in dev

This isn't needed except for in depth testing.

The app is set to run jobs synchronously in DEBUG mode. When you start a demo it will run the job in the Django server rather than running it in the background.
If you want to test, you can:

Run a RabbitMQ server with Docker:
```
docker run --rm -p 5672:5672 --hostname rabbitmq --name rabbitmq rabbitmq:3
```

Start Celery workers:
```
cd app
celery -A tasks worker --loglevel=info
```
