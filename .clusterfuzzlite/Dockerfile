FROM gcr.io/oss-fuzz-base/base-builder:v1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 xz-utils zip \
    && rm -rf /var/lib/apt/lists/*

COPY . $SRC/pylibmspack
WORKDIR $SRC/pylibmspack
COPY .clusterfuzzlite/build.sh $SRC/
