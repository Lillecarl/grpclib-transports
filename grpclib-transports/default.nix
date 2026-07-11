{
  lib,
  # build
  buildPythonPackage,
  hatchling,
  # deps
  grpclib,
  h2,
  asyncssh ? null,
  # test inputs
  pytestCheckHook,
  greeter-proto,
  anyio,
  rich,
}:
buildPythonPackage {
  pname = "grpclib-transports";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];

  dependencies = [
    grpclib
    h2
  ]
  ++ lib.optional (asyncssh != null) asyncssh;

  nativeCheckInputs = [
    pytestCheckHook
    greeter-proto
    anyio
    rich
  ];

  meta = {
    mainProgram = "grpclib-transports";
  };
}
