{
  lib,
  buildPythonApplication,
  hatchling,
  proto,
  asyncssh,
  anyio,
  pytestCheckHook,
}:
buildPythonApplication {
  pname = "grpclab";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ./.;

  build-system = [ hatchling ];

  dependencies = [
    proto
    asyncssh
    anyio
  ];

  nativeCheckInputs = [
    pytestCheckHook
  ];

  meta = {
    mainProgram = "grpclab";
  };
}
