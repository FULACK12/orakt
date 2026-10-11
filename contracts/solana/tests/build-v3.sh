#!/usr/bin/env bash
set -euo pipefail
# Invoked inside the pinned official Anchor image; /work is selected source.
rustup toolchain install 1.95.0 --profile minimal
rustup default 1.95.0
if [ ! -x /cache/bin/cargo-build-sbf ]; then cargo install cargo-build-sbf --version 4.4.0 --locked --root /cache; fi
/cache/bin/cargo-build-sbf --manifest-path programs/orakt-protocol/Cargo.toml --tools-version v1.57 --arch v3 -- --locked
readelf -h target/deploy/orakt_protocol.so
readelf -h target/deploy/orakt_protocol.so | grep -Eq 'Flags:.*0x3'
mkdir -p target/idl
anchor idl build --out target/idl/orakt_protocol.json
cargo test --workspace --locked
if [ ! -x /cache/agave/solana-release/bin/solana ]; then
  mkdir -p /cache/agave
  curl -fL --retry 3 https://github.com/anza-xyz/agave/releases/download/v4.3.0/solana-release-x86_64-unknown-linux-gnu.tar.bz2 -o /cache/agave/release.tar.bz2
  printf '%s  %s\n' c97289a8abb1d0efb497d8b5cb285baabd9b7f8ea6647f5d145c5dc8ff3611e8 /cache/agave/release.tar.bz2 | sha256sum --check
  tar -xjf /cache/agave/release.tar.bz2 -C /cache/agave
fi
/cache/agave/solana-release/bin/solana --version
if [ -f /cache/devnet-source/Cargo.toml ]; then
  cd /cache/devnet-source
  /cache/bin/cargo-build-sbf --manifest-path programs/orakt-protocol/Cargo.toml --tools-version v1.57 --arch v3 -- --locked
  readelf -h target/deploy/orakt_protocol.so | grep -Eq 'Flags:.*0x3'
  mkdir -p target/idl
  anchor idl build --out target/idl/orakt_protocol.json
fi
