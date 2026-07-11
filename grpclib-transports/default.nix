{
  lib,
  buildPythonApplication,
  hatchling,
  proto,
  grpclib,
  h2,
  asyncssh ? null,
  pytestCheckHook,
}:
buildPythonApplication {
  pname = "grpclib-transports";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];

  dependencies = [
    proto
    grpclib
    h2
  ] ++ lib.optional (asyncssh != null) asyncssh;

  nativeCheckInputs = [
    pytestCheckHook
  ];

  meta = {
    mainProgram = "grpclib-transports";
  };
}
