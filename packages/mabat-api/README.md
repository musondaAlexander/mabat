# mabat-api

A FastAPI service exposing [mabat](https://github.com/musondaAlexander/mabat) over HTTP.

```console
pip install mabat-api            # pulls in mabat, fastapi, uvicorn
mabat-api                        # http://127.0.0.1:8000 - docs at /docs
mabat-api --host 0.0.0.0 --port 9000
```

| Endpoint | Returns |
|---|---|
| `GET /health` | which data sources work on the host (use as the service health check) |
| `GET /sections` | the section names and the options each accepts |
| `GET /sections/{name}?redact=true` | one section |
| `GET /snapshot?only=cpu,memory&skip=sensors&connections=true&top=0&redact=true` | everything |
| `GET /connections?kind=tcp` | open sockets with owning processes |
| `GET /problems` | a flat list of what the host cannot report |

Every response is `mabat.to_dict(...)` - identical to `mabat ... --json`.
Collectors run in FastAPI's thread pool, so the event loop stays free while a
section samples.
