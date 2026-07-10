{
  mkShell,
  python3,
  proto,
  asyncssh,
  pytest,
  pyinstrument,
}:
let
  python = python3.withPackages (pp: [ proto asyncssh pytest pyinstrument ]);
in
mkShell {
  packages = [
    python
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclab/src:$PYTHONPATH"
  '';
}
