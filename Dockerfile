# Dockerfile for Wiremaps.
FROM python:2.7

# Install dependencies
RUN apt-get update && apt-get install -qy python-psycopg2 \
                                          python-twisted-core \
                                          python-twisted-names \
                                          python-nevow \
                                          python-ipy \
                                          python-yaml \
                                          python-dev \
                                          libsnmp-dev

# Build wiremaps
ADD . /wiremaps
WORKDIR /wiremaps
RUN python setup.py build_ext --inplace

# Run
EXPOSE 8087
RUN PGHOST=$DB_PORT_5432_TCP_ADDR \
    PGPORT=$DB_PORT_5432_TCP_PORT \
    twistd -no wiremaps
