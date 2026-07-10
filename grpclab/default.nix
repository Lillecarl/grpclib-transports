{
  lib,
  buildPythonApplication,
  hatchling,
  proto,
  asyncssh,
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
  ];

  nativeCheckInputs = [
    pytestCheckHook
  ];

  meta = {
    mainProgram = "grpclab";
  };
}
