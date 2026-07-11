{
  pkgs ? import <nixpkgs> { },
}:
let
  self = rec {
    inherit pkgs;
    greeter-proto = pkgs.python3Packages.callPackage ./greeter-proto { };
    grpclib-transports = pkgs.python3Packages.callPackage ./grpclib-transports {
      inherit greeter-proto;
    };
    pre-commit = pkgs.callPackage ./nix/pkgs/pre-commit { };
    shell = pkgs.python3Packages.callPackage ./nix/shell.nix {
      inherit grpclib-transports pre-commit;
    };
  };
in
self
