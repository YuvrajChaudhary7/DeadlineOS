# Architecture

```mermaid
flowchart LR
  Browser[Student / Staff browser<br/>HTML CSS JavaScript] -->|HTTPS JSON + JWT| API[Flask API<br/>validation and authorization]
  API --> ORM[SQLAlchemy transaction layer]
  ORM --> SQL[(SQLite local / PostgreSQL or Azure SQL deployed)]
  API -. future private file upload .-> Blob[Azure Blob Storage]
  SQL -. curated read model .-> BI[Power BI]
  API -. optional notification documents .-> Cosmos[Azure Cosmos DB]
  Scheduler[15 minute reminder job] --> SQL
```

The browser never connects directly to the database. Identity is authenticated at the API; authorization is checked per route and for resource ownership. Relational DB is the system of record. The reminder worker writes deduplicated in-app notifications; the API exposes them to the user's inbox. Optional Azure services extend the design; local execution does not provision them.

## Deployment boundary
Local demo: browser and Flask on the developer machine, SQLite file. Docker: Flask and PostgreSQL containers on a private Compose network. Cloud target: TLS ingress, private app subnet, managed relational DB with private access, secret store, private Blob container, monitoring/audit sink and least-privilege managed identities. Disable public DB access; restrict ingress to app tier; use backups and key rotation.
