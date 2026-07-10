{
  pkgs ? import <nixpkgs> { },
}:
rec {
  inherit pkgs;
  proto = pkgs.python3Packages.callPackage ./proto { };
  asyncssh = pkgs.python3Packages.callPackage ./nix/asyncssh.nix { };
  grpclab = pkgs.python3Packages.callPackage ./grpclab { inherit proto asyncssh; };
  shell = pkgs.callPackage ./nix/shell.nix {
    inherit grpclab proto asyncssh;
    pytest = pkgs.python3Packages.pytest;
    pyinstrument = pkgs.python3Packages.pyinstrument;
  };
}
