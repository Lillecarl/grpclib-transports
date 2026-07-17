{
  lib,
  stdenvNoCC,
  python,
  grpclib-transports,
  sphinx,
  myst-parser,
  furo,
}:
let
  pythonEnv = python.withPackages (
    _: grpclib-transports.dependencies ++ grpclib-transports.nativeBuildInputs ++ [
      grpclib-transports
      sphinx
      myst-parser
      furo
    ]
  );
in
stdenvNoCC.mkDerivation {
  pname = "grpclib-transports-docs";
  version = "0";

  src = lib.cleanSource ../.;

  nativeBuildInputs = [ pythonEnv ];

  buildPhase = ''
    runHook preBuild
    GRPCLIB_TRANSPORTS_DOCS_OFFLINE=1 sphinx-build -b html docs "$out" -W
    runHook postBuild
  '';

  dontInstall = true;
}
