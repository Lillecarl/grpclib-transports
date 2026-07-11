{
  writeShellApplication,
  treefmt,
  pyright,
  ruff,
}:
writeShellApplication {
  name = "pre-commit";
  runtimeInputs = [
    treefmt
    pyright
    ruff
  ];
  text = builtins.readFile ./pre-commit;
}
