"""Explicit server administration; no public upload, arbitrary fetch or backfill."""

import argparse
import json
import logging
import os
from pathlib import Path

from . import configured_service, create_vault_app


def main(argv=None):
    parser = argparse.ArgumentParser(description="PolitiTrack private Filing Vault runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create additive vault tables in the configured application database")
    ingest = commands.add_parser("import-catalog", help="Import a trusted generated catalog; never retrieves documents")
    ingest.add_argument("path", type=Path)
    reconcile = commands.add_parser("reconcile", help="Daily cache cleanup and due source metadata revalidation")
    reconcile.add_argument("--no-revalidate", action="store_true")
    reconcile.add_argument("--limit", type=int, default=10000)
    reconcile.add_argument("--catalog", type=Path, help="Trusted latest catalog, also configurable with VAULT_CATALOG_PATH")
    serve = commands.add_parser("serve", help="Local development only; use a WSGI server in production")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    config = {key: value for key, value in os.environ.items() if key.startswith("VAULT_")}
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.command == "serve":
        if config.get("VAULT_ENV") != "development":
            parser.error("serve requires VAULT_ENV=development; production needs an HTTPS WSGI deployment")
        create_vault_app(config).run(host=args.host, port=args.port, debug=False)
        return 0
    service = configured_service(config)
    def import_catalog(path):
        if path.stat().st_size > 64 * 1024 * 1024:
            parser.error("catalog exceeds the 64 MiB safety limit")
        return service.import_catalog(json.loads(path.read_text(encoding="utf-8")))

    if args.command == "init-db":
        service.init_schema()
        print(json.dumps({"result": "vault_schema_created", "tracker_state_changed": False}))
    elif args.command == "import-catalog":
        print(json.dumps({"result": "catalog_imported", **import_catalog(args.path)}))
    else:
        if not 1 <= args.limit <= 100000:
            parser.error("--limit must be between 1 and 100000")
        path = args.catalog or config.get("VAULT_CATALOG_PATH")
        if path:
            import_catalog(Path(path))
        report = service.reconcile(revalidate=not args.no_revalidate, limit=args.limit)
        print(json.dumps(report, sort_keys=True))
        return 1 if report["storage_failures"] or report["validation_failed"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
