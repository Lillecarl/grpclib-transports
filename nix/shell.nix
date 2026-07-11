{
  mkShell,
  python,
  proto,
  asyncssh,
  pytest,
  pyinstrument,
  anyio,
  grpclib-transports,
  pyright,
  ruff,
  sphinx,
  myst-parser,
  furo,
}:
let
  pythonEnv = python.withPackages (
    pp:
    grpclib-transports.dependencies
    ++ [
      proto
      asyncssh
      anyio
      pytest
      pyinstrument
      sphinx
      myst-parser
      furo
    ]
  );
in
mkShell {
  packages = [
    pythonEnv
    pyright
    ruff
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclib-transports/src:$PYTHONPATH"
  '';
}
