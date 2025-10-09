
from sqlalchemy import create_engine, text
from ..config import settings

def get_engine():
    if not settings.pg_dsn:
        raise RuntimeError("PG_DSN not set")
    return create_engine(settings.pg_dsn, future=True)

def write_fill(fill: dict):
    eng = get_engine()
    with eng.begin() as cx:
        cx.execute(text("""
        create table if not exists fills (
            ts timestamptz,
            symbol text,
            side text,
            qty numeric,
            price numeric
        )
        """))
        cx.execute(text("""
        insert into fills (ts, symbol, side, qty, price) values (:ts,:symbol,:side,:qty,:price)
        """), fill)
