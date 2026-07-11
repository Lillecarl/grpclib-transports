{
  lib,
  buildPythonPackage,
  hatchling,
  protobuf,
  betterproto2,
  betterproto2-compiler,
  grpclib,
  pydantic,
  grpcio-tools,
  mypy-protobuf,
}:
buildPythonPackage {
  pname = "greeter2";
  version = "0.1.0";

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];
  nativeBuildInputs = [
    protobuf
    betterproto2-compiler
    betterproto2
    grpclib
    pydantic
    mypy-protobuf
    grpcio-tools
  ];

  dependencies = [
    protobuf
    betterproto2
    pydantic
    grpclib
    mypy-protobuf
  ];

  format = "pyproject";
  preBuild = ''
    mkdir -p src/greeter2
    touch src/greeter2/py.typed
    protoc \
      --proto_path=. \
      --python_betterproto2_out=src/greeter2 \
      --python_betterproto2_opt=client_generation=async \
      --python_betterproto2_opt=server_generation=async \
      --python_betterproto2_opt=google_protobuf_descriptors \
      common.proto \
      server.proto \
      worker.proto
  '';

  meta = with lib; {
    description = "Demo gRPC protobuf library (betterproto2 compiled)";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
