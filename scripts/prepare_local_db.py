"""Gera credenciais locais sem imprimi-las ou substituir arquivos existentes."""

import os
import secrets
from pathlib import Path


def prepare(directory: Path) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name in ("admin_password", "app_password"):
        path = directory / name
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(secrets.token_hex(32))
        # O diretório 0700 protege no host; o processo postgres precisa ler o bind mount.
        path.chmod(0o644)
    passfile = directory / "pgpass"
    if not passfile.exists():
        password = (directory / "app_password").read_text().strip()
        descriptor = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(f"127.0.0.1:5433:incident_lab:incident_lab:{password}\n")


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parents[1] / ".local")
    print("Credenciais locais preparadas em .local/; nenhum segredo foi exibido.")
