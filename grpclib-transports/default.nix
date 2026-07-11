{
  lib,
  # build
  buildPythonPackage,
  hatchling,
  # deps
  proto,
  grpclib,
  h2,
  asyncssh ? null,
  # test inputs
  rich,
  anyio,
  pytestCheckHook,
}:
buildPythonPackage {
  pname = "grpclib-transports";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];

  dependencies = [
    proto
    grpclib
    h2
  ]
  ++ lib.optional (asyncssh != null) asyncssh;

  nativeCheckInputs = [
    pytestCheckHook
    anyio
    rich
  ];

  meta = {
    mainProgram = "grpclib-transports";
  };
}
