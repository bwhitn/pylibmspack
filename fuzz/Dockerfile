FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /src

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential clang libclang-rt-19-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . /src

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[dev,fuzz]"

RUN python scripts/run_atheris.py --exercise-disk --runs 128

RUN python scripts/build_libfuzzer.py --out-dir /tmp/pylibmspack-libfuzzer \
    && python scripts/run_libfuzzer.py --fuzzers-dir /tmp/pylibmspack-libfuzzer --runs 128
