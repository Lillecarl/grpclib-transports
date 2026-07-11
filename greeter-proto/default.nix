{
  lib,
  buildPythonPackage,
  hatchling,
  grpcio-tools,
  grpclib,
  mypy-protobuf,
}:
buildPythonPackage {
  pname = "greeter-proto";
  version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];
  nativeBuildInputs = [
    grpclib
    mypy-protobuf
    grpcio-tools
  ];

  dependencies = [
    grpclib
    mypy-protobuf
  ];

  format = "pyproject";
  preBuild = ''
    mkdir -p src/greeter
    touch src/greeter/py.typed
    touch src/greeter/__init__.py
    protoc \
      --proto_path=. \
      --python_out="src/greeter" \
      --grpclib_python_out="src/greeter" \
      --mypy_out="src/greeter" \
      common.proto \
      server.proto \
      worker.proto

    for file in src/greeter/*_pb2.py src/greeter/*_pb2.pyi src/greeter/*_grpc.py; do
      substituteInPlace "$file" \
        --replace "import common_pb2" "from . import common_pb2" \
        --replace "import server_pb2" "from . import server_pb2" \
        --replace "import worker_pb2" "from . import worker_pb2"
    done
  '';

  meta = with lib; {
    description = "Demo gRPC protobuf library";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
