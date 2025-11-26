# Changelog

## [0.5.0](https://github.com/albertomh/DODO/compare/v0.4.0...v0.5.0) (2025-11-26)


### Features

* Filter droplets by tag in list_droplet_IPs ([#36](https://github.com/albertomh/DODO/issues/36)) ([8911f87](https://github.com/albertomh/DODO/commit/8911f87157e4ef0e5e2d5a83c1b46e1a7921da8e))

## [0.4.0](https://github.com/albertomh/DODO/compare/v0.3.1...v0.4.0) (2025-11-24)


### Features

* Add Cloudflare-related headers to nginx conf ([#26](https://github.com/albertomh/DODO/issues/26)) ([25771ee](https://github.com/albertomh/DODO/commit/25771ee4fd74942237bbf7fc6639880d98d3c52b))
* Allow additional types of DNS record in blueprints ([#28](https://github.com/albertomh/DODO/issues/28)) ([d8dfeb8](https://github.com/albertomh/DODO/commit/d8dfeb8671e9c969a59e9e0c188f258cc81479c9))
* Cache DNS records per-Zone in Cloudflare management code ([#34](https://github.com/albertomh/DODO/issues/34)) ([2ccfb3e](https://github.com/albertomh/DODO/commit/2ccfb3e6ace71303e206faf1c1497228203c1b47))
* Cache Zone lookup in Cloudflare management code ([#31](https://github.com/albertomh/DODO/issues/31)) ([3633496](https://github.com/albertomh/DODO/commit/3633496ed54d1affdfa0b0a9e9d13eca8e5e92cd))
* Manage Cloudflare DNS records via infra.apply module ([#23](https://github.com/albertomh/DODO/issues/23)) ([65bfe74](https://github.com/albertomh/DODO/commit/65bfe749615a7c4b7583650c34fa7096820403b8))
* Set DNS record types via env. blueprints ([#27](https://github.com/albertomh/DODO/issues/27)) ([4fffb1e](https://github.com/albertomh/DODO/commit/4fffb1eaa7e4c5e30113e66071bde447b691d1c2))


### Dependencies

* Add 'cloudflare' package ([#22](https://github.com/albertomh/DODO/issues/22)) ([fe9f05f](https://github.com/albertomh/DODO/commit/fe9f05f9476f6382c1e77e9150e91742ac964a02))
* Upgrade to pydo&gt;=0.21.0 ([#25](https://github.com/albertomh/DODO/issues/25)) ([3b18a5c](https://github.com/albertomh/DODO/commit/3b18a5c791eb1b6f89629bbcb72fc94b4b7befac))
* Upgrade to pytest&gt;=9.0.0 ([#24](https://github.com/albertomh/DODO/issues/24)) ([5f84f80](https://github.com/albertomh/DODO/commit/5f84f80cf97fdb7c51c929e3b08d47bdc49befe7))


### Documentation

* Add cloud-config template samples for app, postgres servers ([#17](https://github.com/albertomh/DODO/issues/17)) ([dee8084](https://github.com/albertomh/DODO/commit/dee80849a40d8cd558c6e42368e77508fb000639))
* Add env. blueprint sample with app + db droplets ([#19](https://github.com/albertomh/DODO/issues/19)) ([a64322a](https://github.com/albertomh/DODO/commit/a64322afce8eb0e3dfb358a1f355f47bcdc55e90))
* Update README intro + quickstart steps ([#30](https://github.com/albertomh/DODO/issues/30)) ([50ede87](https://github.com/albertomh/DODO/commit/50ede87454104cbb653507857f0b6772d4fec4c6))

## [0.3.1](https://github.com/albertomh/DODO/compare/v0.3.0...v0.3.1) (2025-11-09)


### Bug Fixes

* Path for deploy package when looking for nginx conf template ([#13](https://github.com/albertomh/DODO/issues/13)) ([e87ca46](https://github.com/albertomh/DODO/commit/e87ca460ff7b90646d366dfdfb0c3d4e87b47f49))

## [0.3.0](https://github.com/albertomh/DODO/compare/v0.2.0...v0.3.0) (2025-11-07)


### Features

* Add module to check service health via HTTP requests ([#11](https://github.com/albertomh/DODO/issues/11)) ([05f47a1](https://github.com/albertomh/DODO/commit/05f47a14d261f68da0f837b9b5410c2cc13033c4))
* Add module to perform blue/green deployment ([#12](https://github.com/albertomh/DODO/issues/12)) ([7227b7d](https://github.com/albertomh/DODO/commit/7227b7de6574a45ceb68337441541ae28aac00cb))
* Add utility to list Droplet IPs by environment ([#9](https://github.com/albertomh/DODO/issues/9)) ([cb2271b](https://github.com/albertomh/DODO/commit/cb2271bc198c99e8a92cfde82239e839417d6ba1))

## [0.2.0](https://github.com/albertomh/DODO/compare/v0.1.0...v0.2.0) (2025-11-05)


### Features

* Add utils common across infra & deploy packages ([#7](https://github.com/albertomh/DODO/issues/7)) ([ee3c69b](https://github.com/albertomh/DODO/commit/ee3c69bfd924228bdf6d08222ce51267ef5911c8))
* Define types - both internal and specific to Digital Ocean APIs ([#3](https://github.com/albertomh/DODO/issues/3)) ([3cbd768](https://github.com/albertomh/DODO/commit/3cbd768770f624e682e44d8f57972c81aaf4661c))
* Infra.apply module to plan & effect changes to resources ([#8](https://github.com/albertomh/DODO/issues/8)) ([84f3599](https://github.com/albertomh/DODO/commit/84f359929fd75fb6f1d19f187a9ebb5ac2307532))


### Bug Fixes

* **ci:** Call the right _checks job in the 'ci' workflow ([#6](https://github.com/albertomh/DODO/issues/6)) ([8b3eb2c](https://github.com/albertomh/DODO/commit/8b3eb2c99cbec4ee8e66ea4005d1b5e51c7c210b))

## 0.1.0 (2025-11-03)


### Dependencies

* Add jinja2, pydo as dependencies ([dbb84f4](https://github.com/albertomh/DODO/commit/dbb84f446f4695db4e35aebee5ecc1df38bb5f90))
* **ci:** Bump setup-python, setup-uv steps ([d3e9d05](https://github.com/albertomh/DODO/commit/d3e9d05286e6b7d4db6ad559f7f69f0e473af053))
* **test:** Add 'pytest-cov' for coverage reporting with xdist ([141102e](https://github.com/albertomh/DODO/commit/141102e0d6c720678723d86effc3361956a254f1))


### Documentation

* Add section on building and packaging as a wheel to README ([70b27c3](https://github.com/albertomh/DODO/commit/70b27c3b004b2bff8718b735f66853f1308f94b2))
* Update README with acronym ([8fddba2](https://github.com/albertomh/DODO/commit/8fddba2cdd2684c9dac2702658956c9bee4b5029))

## Changelog

Notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file is automatically updated by Release Please.
