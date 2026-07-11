{
  lib,
  buildPythonPackage,
  fetchFromGitHub,
  uv-build,
  python-dateutil,
  typing-extensions,
  pydantic,
  grpclib,
}:

buildPythonPackage (finalAttrs: {
  pname = "betterproto2";
  version = "0.10.0";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "betterproto";
    repo = "python-betterproto2";
    rev = "25e2893cf83e160b19389af2f469341ff864ea18";
    hash = "sha256-Xv8xdSh0C95xMqOF8mR7wuKe/mcbo5IDExEZsCcn9fo=";
  };

  sourceRoot = "source/betterproto2";

  nativeBuildInputs = [ uv-build ];

  propagatedBuildInputs = [
    python-dateutil
    typing-extensions
    pydantic
    grpclib
  ];

  pythonImportsCheck = [ "betterproto2" ];

  meta = {
    maintainers = with lib.maintainers; [ lillecarl ];
  };
})
