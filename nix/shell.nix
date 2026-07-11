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
  pre-commit, # overridden pre-commit script
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
    pre-commit
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
