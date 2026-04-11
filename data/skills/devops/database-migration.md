---
name: Database Migration
description: Schema versioning, migration tools, rollback strategies, and zero-downtime changes
version: "1.0.0"
author: ROOT
tags: [devops, database, migration, schema, versioning, rollback]
platforms: [all]
---

# Database Migration

Manage database schema changes safely with versioning, testing, and rollback capability.

## Migration Strategy

### Tools by Database
| Database | Tool | Key Feature |
|----------|------|-------------|
| PostgreSQL/MySQL | Alembic (Python) | Auto-generates from SQLAlchemy models |
| PostgreSQL/MySQL | Flyway | SQL-based, language-agnostic |
| Any SQL | Liquibase | XML/YAML/SQL, enterprise features |
| SQLite | Manual SQL scripts | Simple versioned scripts |
| MongoDB | mongomigrate | Document schema evolution |

### Migration File Structure
```
migrations/
  001_create_users_table.sql
  002_add_email_index.sql
  003_create_orders_table.sql
  004_add_user_status_column.sql
```
- Sequential numbering or timestamps for ordering
- Each file contains both `up` (apply) and `down` (rollback) SQL
- Never modify a migration that has been applied to any environment

## Safe Migration Patterns

### Adding a Column
1. Add column with `DEFAULT NULL` (no table lock on most databases)
2. Backfill data in batches (not one massive UPDATE)
3. Add NOT NULL constraint after backfill (if needed)
4. Update application code to use the new column

### Removing a Column
1. Stop reading the column in application code (deploy first)
2. Stop writing to the column (second deploy)
3. Drop the column in migration (final deploy)
4. Three-phase approach prevents errors during rolling deploys

### Renaming a Column
1. Add new column
2. Write to both old and new columns (dual-write)
3. Backfill new column from old column
4. Switch reads to new column
5. Stop writing to old column
6. Drop old column

## Zero-Downtime Requirements

### Rules for Online Migrations
- Never lock tables for more than a few seconds
- Never drop columns or tables that running application code reads
- Use `CREATE INDEX CONCURRENTLY` (PostgreSQL) for index creation
- Batch large data migrations: process 1,000-10,000 rows per batch with sleep between

### Expand-Contract Pattern
1. **Expand**: Add new schema alongside old (both work)
2. **Migrate**: Move application to use new schema
3. **Contract**: Remove old schema after all instances use new

## Rollback Strategy

### Reversible Migrations
- Every migration must have a tested rollback script
- Test rollback in staging before applying to production
- Some operations are not easily reversible (data deletion, lossy transformations)
- For irreversible changes: take database snapshot before applying

### Rollback Decision Criteria
- If migration fails mid-execution: rollback immediately
- If migration succeeds but causes errors: assess severity, rollback if > 1% error rate
- If migration succeeds and is stable for 1 hour: consider it committed

## Checklist

- [ ] Migration tested in staging environment with production-like data volume
- [ ] Rollback script tested
- [ ] No table locks longer than 5 seconds
- [ ] Large data backfills batched and monitored
- [ ] Application code compatible with both old and new schema during deploy
- [ ] Database backup taken before production migration
- [ ] Migration timing: run during low-traffic period
