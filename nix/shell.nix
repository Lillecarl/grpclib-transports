{
  mkShell,
  python3,
  proto,
  asyncssh,
  pytest,
  pyinstrument,
  grpclab,
  pyright,
  ruff,
}:
let
  python = python3.withPackages (
    pp:
    grpclab.dependencies
    ++ [
      proto
      asyncssh
      pytest
      pyinstrument
    ]
  );
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
