from __future__ import annotations

import argparse
import sys

from database.connection import session_scope
from database.migrations import init_db
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import seed_sources
from services.camara import CamaraService
from services.ibge import IBGEService
from services.senado import SenadoService
from services.sinesp import SinespService
from services.tse import TSEService
from utils.requests import ExternalServiceError


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Sincroniza recortes oficiais do Raio-X Municipal")
    command.add_argument(
        "--dataset",
        required=True,
        choices=["municipalities", "ibge", "sinesp", "tse", "camara", "senado", "all"],
    )
    command.add_argument("--uf", type=str.upper)
    command.add_argument("--municipio", help="Código IBGE de 7 dígitos")
    command.add_argument("--year", type=int)
    command.add_argument("--force", action="store_true")
    return command


def require(value, flag: str):
    if value is None:
        raise ValueError(f"{flag} é obrigatório para este dataset")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    init_db()
    try:
        with session_scope() as session:
            seed_sources(session)
            session.commit()
            ibge = IBGEService(session)
            if args.dataset in {"municipalities", "all"}:
                print(f"Municípios sincronizados: {ibge.sync_municipalities(force=args.force)}")
            if args.dataset in {"ibge", "all"} and args.municipio and args.year:
                result = ibge.sync_core(args.municipio, args.year, force=args.force)
                print(f"IBGE: população={bool(result['population'])} pib={bool(result['gdp'])}")
                for error in result["errors"]:
                    print(f"Aviso: {error}", file=sys.stderr)
            elif args.dataset == "ibge":
                require(args.municipio, "--municipio")
                require(args.year, "--year")
            if args.dataset in {"sinesp", "all"} and args.municipio and args.year:
                print(f"Sinesp: {SinespService(session).sync_municipality(args.municipio, args.year)}")
            elif args.dataset == "sinesp":
                require(args.municipio, "--municipio")
                require(args.year, "--year")
            if args.dataset in {"tse", "all"} and args.municipio and args.uf and args.year:
                print(f"TSE: {TSEService(session).sync_election(args.municipio, args.uf, args.year)}")
            elif args.dataset == "tse":
                require(args.municipio, "--municipio")
                require(args.uf, "--uf")
                require(args.year, "--year")
            if args.dataset in {"camara", "all"} and args.uf and args.year:
                print(f"Câmara: {CamaraService(session).sync_deputies(args.uf, args.year)}")
            elif args.dataset == "camara":
                require(args.uf, "--uf")
                require(args.year, "--year")
            if args.dataset in {"senado", "all"} and args.uf and args.year:
                print(f"Senado: {SenadoService(session).sync_senators(args.uf, args.year)}")
            elif args.dataset == "senado":
                require(args.uf, "--uf")
                require(args.year, "--year")
        return 0
    except (ExternalServiceError, ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

