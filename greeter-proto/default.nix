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
      greeter.proto

    substituteInPlace src/greeter/greeter_grpc.py \
      --replace-fail "import greeter_pb2" "from . import greeter_pb2"
  '';

  meta = with lib; {
    description = "Demo gRPC protobuf library";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
