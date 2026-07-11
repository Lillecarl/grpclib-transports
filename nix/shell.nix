{
  mkShell,
  python3,
  proto,
  asyncssh,
  pytest,
  pyinstrument,
  anyio,
  grpclib-transports,
  pyright,
  ruff,
}:
let
  python = python3.withPackages (
    pp:
    grpclib-transports.dependencies
    ++ [
      proto
      asyncssh
      anyio
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
    export PYTHONPATH="$PWD/grpclib-transports/src:$PYTHONPATH"
  '';
}
