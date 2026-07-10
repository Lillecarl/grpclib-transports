{
  lib,
  buildPythonPackage,
  setuptools,
  cryptography,
  typing-extensions,
}:
buildPythonPackage {
  pname = "asyncssh";
  version = "2.22.0";
  pyproject = true;
  src = lib.cleanSource ../../asyncssh;
  build-system = [ setuptools ];
  dependencies = [
    cryptography
    typing-extensions
  ];
  meta = with lib; {
    description = "AsyncSSH: Asynchronous SSHv2 client and server library";
    homepage = "http://asyncssh.timeheart.net";
    license = licenses.epl20;
  };
}
