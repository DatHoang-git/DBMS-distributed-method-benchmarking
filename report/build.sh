#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v pdflatex >/dev/null 2>&1 && kpsewhich vietnam.sty >/dev/null 2>&1; then
  ENGINE="pdflatex"
  RUN_CMD=(pdflatex)
elif command -v xelatex >/dev/null 2>&1; then
  ENGINE="xelatex"
  if ! kpsewhich xelatex.fmt >/dev/null 2>&1; then
    FMT_DIR="/tmp/texmf-var/web2c/xetex"
    if [ ! -f "${FMT_DIR}/xelatex.fmt" ]; then
      echo "Generating local xelatex.fmt in ${FMT_DIR}..."
      mkdir -p "${FMT_DIR}"
      (cd "${FMT_DIR}" && xetex -ini -jobname=xelatex -progname=xelatex -etex xelatex.ini >/tmp/xelatex_ini.log)
    fi
    export TEXMFVAR="/tmp/texmf-var"
  fi
  RUN_CMD=(xelatex)
else
  echo "Error: neither pdflatex (with vietnam.sty) nor xelatex is installed." >&2
  exit 1
fi

echo "Compiling main.tex with ${ENGINE}..."
"${RUN_CMD[@]}" -interaction=nonstopmode -halt-on-error main.tex
"${RUN_CMD[@]}" -interaction=nonstopmode -halt-on-error main.tex
"${RUN_CMD[@]}" -interaction=nonstopmode -halt-on-error main.tex
echo "Build completed: $(pwd)/main.pdf"
