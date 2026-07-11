{
  pkgs ? import <nixpkgs> { },
}:
let
  self = rec {
    inherit pkgs;
    proto = pkgs.python3Packages.callPackage ./proto { };
    asyncssh = pkgs.python3Packages.callPackage ./nix/asyncssh.nix { };
    grpclib-transports = pkgs.python3Packages.callPackage ./grpclib-transports { inherit proto asyncssh; };
    shell = pkgs.callPackage ./nix/shell.nix {
      inherit proto asyncssh;
      inherit (self) grpclib-transports;
      pytest = pkgs.python3Packages.pytest;
      pyinstrument = pkgs.python3Packages.pyinstrument;
      anyio = pkgs.python3Packages.anyio;
    };
  };
in
self
