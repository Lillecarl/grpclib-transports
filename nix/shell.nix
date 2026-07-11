{
  mkShell,
  python,
  pytest,
  pyinstrument,
  grpclib-transports,
  pyright,
  ruff,
  sphinx,
  myst-parser,
  furo,
  # formatters
  treefmt,
  nixfmt,
  taplo,
}:
let
  pythonEnv = python.withPackages (
    pp:
    grpclib-transports.dependencies
    ++ grpclib-transports.nativeBuildInputs
    ++ [
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
    treefmt
    nixfmt
    taplo
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclib-transports/src:$PYTHONPATH"
  '';
}
