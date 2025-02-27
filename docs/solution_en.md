### Solution notes

In my opinion, based on [restrictions and requirements]() the most suitable solution should include the following obvious points:

- business logic and event logging for a particular usecase should be interpreted as an all-or-nothing operation - they happen in a scope of one transaction.
- event publishing should be delegated to a separate service - no such a logic inside the usecase.
- events are published to a clikhouse(or any other olap database) asynchronously and in batches - clickhouse should not be stressed out by thousands single-insert requests
- events are collected in a durable buffer storage before being sent to clickhouse
- there will be a periodic task to start an events migration from the buffer storage to clickhouse
- the migration process should be atomic - it is executed in a transaction

So it seems the transactional outbox pattern fits well to implement the solution. 


### Solution details

The new event logging/publishing mechanism is implemented in a separate app `outbox`. The main app's components are:

- outbox services in `outbox/services.py`
- olap client wrappers in `outbox/clients.py`
- outbox models in `outbox/models.py`
- celery tasks in `outbox/tasks.py`

I decoupled services, client wrappers and usecases from each other to keep a machinary a bit more flexible.

a concrete implementation of the logging/publishing logic for a particular olap is defined in a subclass of `BaseOutboxService` class. For now it is `ClickHouseOutboxService`. The logic represented by two methods:

- `save_events` method inserts events in a buffer storage - Postgres table `EventLogOutbox` in our case.
- `migrate_events` method takes unprocessed events from the buffer storage, publishes them to the olap db and marks them as processed. 

A particular `BaseOutboxService` subclass relies on a client wrapper that should be a subclass of `EventLogClient` class. I moved an original client logic to `ClickHouseEventLogClient`. 

It takes 3 steps for any usecase to integrate with the event logging mechanism:

- let `__init__` method take any outbox service type or assign the default one
- implement its _log_event method in the way it calls the outbox service's save_event method 
- place _log_event call along with the core logic inside one transaction

communication between components diagram:

