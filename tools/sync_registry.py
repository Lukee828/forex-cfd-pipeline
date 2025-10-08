from src.alpha_factory import registry
from src.alpha_factory.registry_db import (
    get_connection,
    init_db,
    sync_from_registry,
    list_factors,
)


def main():
    conn = get_connection()
    init_db(conn)
    n = sync_from_registry(registry, conn)
    rows = list_factors(conn)
    print(f"Synced {n} factor specs into DB. Now have {len(rows)} rows.")
    for name, params in rows:
        print(
            f"- {name}: {params.get('__classname__')} -> { {k:v for k,v in params.items() if k!='__classname__'} }"
        )


if __name__ == "__main__":
    main()
