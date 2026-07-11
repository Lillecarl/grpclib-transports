{ mkShell
, python
, pytest
, pyinstrument
, grpclib-transports
, pyright
, ruff
, sphinx
, myst-parser
, furo
, # formatters
  treefmt
, nixpkgs-fmt
, taplo
,
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
    nixpkgs-fmt
    taplo
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclib-transports/src:$PYTHONPATH"
  '';
}
