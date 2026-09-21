"""Baixa os arquivos brutos dos dois conectomas (total ~700 MB) para data/raw/.

Nenhum arquivo passa de 1 GB. Os arquivos de sinapses (6-13 GB) nao sao usados.
Confere tamanho esperado; refaz so o que falta.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

RAW = Path("data/raw")
FILES = [
    # (url, destino, bytes esperados)
    ("https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Completeness_783.csv",
     "flywire/Completeness_783.csv", 3327347),
    ("https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Connectivity_783.parquet",
     "flywire/Connectivity_783.parquet", 100804642),
    ("https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv",
     "flywire/neuron_annotations_v3.1.0.tsv", 31718505),
    ("https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather",
     "malecns/body-annotations-male-cns-v1.0-minconf-0.5.feather", 14483314),
    ("https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-neurotransmitters-male-cns-v1.0.feather",
     "malecns/body-neurotransmitters-male-cns-v1.0.feather", 43282834),
    ("https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather",
     "malecns/connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather", 508025642),
]


def main() -> int:
    for url, rel, size in FILES:
        dst = RAW / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == size:
            print(f"[ok] {rel} ({size/2**20:.1f} MB)")
            continue
        print(f"[..] {rel} ({size/2**20:.1f} MB) <- {url}")
        urllib.request.urlretrieve(url, dst)
        got = dst.stat().st_size
        if got != size:
            print(f"[!!] tamanho inesperado: {got} != {size} (as anotacoes do flyconnectome mudam com a versao; confira)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
