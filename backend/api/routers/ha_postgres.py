"""PostgreSQL High Availability endpoints for replication monitoring."""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/redundancy", tags=["Redundancy"])


@router.get("/pg-lag")
async def get_postgresql_replication_lag():
    """Get PostgreSQL replication lag from WAL metrics."""
    try:
        import psycopg2
        from os import getenv

        db_host = getenv("DB_HOST", "localhost")
        db_port = getenv("DB_PORT", "5432")
        db_name = getenv("DB_NAME", "crypto_db")
        db_user = getenv("DB_USER", "postgres")
        db_password = getenv("DB_PASSWORD", "")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password if db_password else None,
            connect_timeout=5,
        )

        cursor = conn.cursor()

        # Get replication status
        cursor.execute(
            """
            SELECT
                client_addr,
                state,
                replay_lag,
                EXTRACT(EPOCH FROM replay_lag) as replay_lag_seconds
            FROM pg_stat_replication;
        """
        )

        replication_data = cursor.fetchall()
        cursor.close()
        conn.close()

        if not replication_data:
            return JSONResponse(
                {
                    "status": "no_replication",
                    "message": "No active replication connections",
                    "lag_seconds": None,
                }
            )

        # Get lag from first replication connection (usually backup)
        client_addr, state, replay_lag, lag_seconds = replication_data[0]
        lag_seconds = float(lag_seconds) if lag_seconds else 0.0

        status = (
            "healthy"
            if lag_seconds < 2
            else "warning"
            if lag_seconds < 5
            else "critical"
        )

        return JSONResponse(
            {
                "status": status,
                "replica": str(client_addr),
                "state": state,
                "lag_seconds": round(lag_seconds, 2),
                "lag_display": f"{lag_seconds:.2f}s",
                "warning_threshold": 2,
                "critical_threshold": 5,
            }
        )

    except ImportError:
        return JSONResponse(
            {
                "status": "unavailable",
                "message": "psycopg2 not installed",
                "lag_seconds": None,
            },
            status_code=503,
        )

    except Exception as e:
        logger.error(f"Error checking PostgreSQL replication lag: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e), "lag_seconds": None}, status_code=500
        )


@router.get("/pg-status")
async def get_postgresql_status():
    """Get detailed PostgreSQL status and replication metrics."""
    try:
        import psycopg2

        from os import getenv

        db_host = getenv("DB_HOST", "localhost")
        db_port = getenv("DB_PORT", "5432")
        db_name = getenv("DB_NAME", "crypto_db")
        db_user = getenv("DB_USER", "postgres")
        db_password = getenv("DB_PASSWORD", "")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password if db_password else None,
            connect_timeout=5,
        )

        cursor = conn.cursor()

        # Get database size
        cursor.execute(
            """
            SELECT pg_database_size(current_database()) / 1024.0 / 1024.0 as size_mb;
        """
        )
        db_size_mb = cursor.fetchone()[0]

        # Get number of connections
        cursor.execute(
            """
            SELECT count(*) FROM pg_stat_activity;
        """
        )
        connection_count = cursor.fetchone()[0]

        # Get WAL activity
        cursor.execute(
            """
            SELECT pg_current_wal_lsn();
        """
        )
        wal_lsn = cursor.fetchone()[0]

        # Get replication lag
        cursor.execute(
            """
            SELECT
                count(*) as replica_count,
                max(EXTRACT(EPOCH FROM replay_lag)) as max_lag_seconds
            FROM pg_stat_replication;
        """
        )
        replica_count, max_lag = cursor.fetchone()
        max_lag = float(max_lag) if max_lag else 0.0

        cursor.close()
        conn.close()

        return JSONResponse(
            {
                "database": {
                    "name": db_name,
                    "host": db_host,
                    "size_mb": round(db_size_mb, 2),
                    "connections": connection_count,
                },
                "wal": {"current_lsn": str(wal_lsn)},
                "replication": {
                    "replica_count": int(replica_count) if replica_count else 0,
                    "max_lag_seconds": round(max_lag, 2),
                    "status": "healthy"
                    if max_lag < 2
                    else "warning"
                    if max_lag < 5
                    else "critical",
                },
            }
        )

    except ImportError:
        return JSONResponse(
            {"status": "unavailable", "message": "psycopg2 not installed"},
            status_code=503,
        )

    except Exception as e:
        logger.error(f"Error checking PostgreSQL status: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
