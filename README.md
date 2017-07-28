# Demo service

Spin up ./run demos!


### (Optional) Spinning up workers in dev

The app is set to run synchronously in DEBUG mode but to test, you can:

Run a RabbitMQ server with Docker:
```
docker run --rm -p 5672:5672 --hostname rabbitmq --name rabbitmq rabbitmq:3
```

Start Celery workers:
```
cd app
celery -A tasks worker --loglevel=info
```
