{
  mkShell,
  python3,
  proto,
  asyncssh,
  pytest,
}:
let
  python = python3.withPackages (pp: [ proto asyncssh pytest ]);
in
mkShell {
  packages = [
    python
  ];
  shellHook = ''
    export PYTHONPATH="$PWD/grpclab/src:$PYTHONPATH"
  '';
}
