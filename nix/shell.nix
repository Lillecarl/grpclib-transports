{
  mkShell,
  python3,
  proto,
  asyncssh,
  pytest,
  pyinstrument,
  pyright,
  ruff,
}:
let
  python = python3.withPackages (pp: [ proto asyncssh pytest pyinstrument ]);
in
mkShell {
  packages = [
    python
    pyright
    ruff
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclab/src:$PYTHONPATH"
  '';
}
