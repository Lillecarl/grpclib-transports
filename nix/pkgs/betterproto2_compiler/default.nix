{
  lib,
  buildPythonPackage,
  fetchFromGitHub,
  uv-build,
  betterproto2,
  jinja2,
  ruff,
  typing-extensions,
}:

buildPythonPackage rec {
  pname = "betterproto2_compiler";
  version = "0.10.1";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "betterproto";
    repo = "python-betterproto2";
    rev = "25e2893cf83e160b19389af2f469341ff864ea18";
    hash = "sha256-Xv8xdSh0C95xMqOF8mR7wuKe/mcbo5IDExEZsCcn9fo=";
  };

  sourceRoot = "source/betterproto2_compiler";

  nativeBuildInputs = [ uv-build ];

  propagatedBuildInputs = [
    betterproto2
    jinja2
    ruff
    typing-extensions
  ];

  pythonImportsCheck = [ "betterproto2_compiler" ];

  pythonRelaxDeps = [ "ruff" ];

  meta = {
    maintainers = with lib.maintainers; [ lillecarl ];
  };
}
