{
  pkgs ? import <nixpkgs> { },
}:
rec {
  inherit pkgs;
  proto = pkgs.python3Packages.callPackage ./proto { };
  asyncssh = pkgs.python3Packages.callPackage ./nix/asyncssh.nix { };
  grpclab = pkgs.python3Packages.callPackage ./grpclab { inherit proto asyncssh; };
  shell = pkgs.callPackage ./nix/shell.nix {
    inherit proto asyncssh;
    pytest = pkgs.python3Packages.pytest;
  };
}
