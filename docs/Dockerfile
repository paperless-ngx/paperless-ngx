FROM python:3.5.1

# Install Sphinx and Pygments
RUN pip install --no-cache-dir Sphinx Pygments \
  # Setup directories, copy data
  && mkdir /build

COPY . /build
WORKDIR /build/docs

# Build documentation
RUN make html

# Start webserver
WORKDIR /build/docs/_build/html
EXPOSE 8000/tcp
CMD ["python3", "-m", "http.server"]
