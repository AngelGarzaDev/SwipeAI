{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python3
    pkgs.python3Packages.opencv4
    pkgs.python3Packages.numpy
    (pkgs.tesseract.override { enableLanguages = [ "eng" ]; })
  ];
}
