{
  inputs = {
    flake-compatish.url = "github:lillecarl/flake-compatish";
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
  };
  outputs =
    inputs:
    let
      lib = inputs.nixpkgs.lib;
      forEachSystem = lib.genAttrs lib.systems.flakeExposed;
    in
    {
      packages = forEachSystem (
        system:
        import ./. {
          inherit system;
          pkgs = inputs.self.legacyPackages.${system};
        }
      );
      legacyPackages = forEachSystem (system: inputs.nixpkgs.legacyPackages.${system});
    };
}
