{ lib
, buildPythonPackage
, hatchling
, grpcio-tools
, grpclib
, mypy-protobuf
,
}:
buildPythonPackage {
  pname = "demo-proto";
  version = "0.1.0";

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
    mkdir -p src/demo
    touch src/demo/py.typed
    touch src/demo/__init__.py
    protoc \
      --proto_path=. \
      --python_out="src/demo" \
      --grpclib_python_out="src/demo" \
      --mypy_out="src/demo" \
      demo.proto

    substituteInPlace src/demo/demo_grpc.py \
      --replace-fail "import demo_pb2" "from . import demo_pb2"
  '';

  meta = with lib; {
    description = "Demo gRPC protobuf library";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
