{
  pkgs ? import <nixpkgs> { },
}:
let
  self = rec {
    inherit pkgs;
    betterproto2 = pkgs.python3Packages.callPackage ./nix/pkgs/betterproto2 { };
    betterproto2-compiler = pkgs.python3Packages.callPackage ./nix/pkgs/betterproto2_compiler {
      inherit betterproto2;
    };
    greeter-proto = pkgs.python3Packages.callPackage ./greeter-proto {
      inherit betterproto2 betterproto2-compiler;
    };
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
