{ pkgs ? import <nixpkgs> { }
,
}:
let
  self = rec {
    inherit pkgs;
    proto = pkgs.python3Packages.callPackage ./proto { };
    grpclib-transports = pkgs.python3Packages.callPackage ./grpclib-transports {
      inherit proto;
    };
    shell = pkgs.python3Packages.callPackage ./nix/shell.nix {
      inherit grpclib-transports;
    };
  };
in
self
