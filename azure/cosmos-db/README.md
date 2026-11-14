# Azure Cosmos DB design (DP-900)

Cosmos DB is an optional fit for high-volume notification/event documents with flexible JSON fields and user-partitioned reads. Candidate partition key: `/userId` for inbox reads. Apply TTL only when retention policy permits. Academic entities, enrollment integrity and grades remain in Azure SQL. Avoid dual writes without an outbox or idempotent event pipeline. No Cosmos account is provisioned.
