# Changelog

Notable changes to S3 Viewer. The newest version is at the top.
Changes sit under **Unreleased** until a version is declared.

## [Unreleased]

### Added

### Changed

### Fixed

## [0.2.4] - 2026-11-26

### Added

- File list columns can be sorted up or down by name, size, or date. The parent folder stays at the top.

### Changed

- The README links to the changelog and describes saved connections as S3 connections.

## [0.2.3] - 2026-11-26

### Added

- Several selected files download together, with one progress bar for the whole batch.
- Save and download dialogs reopen in the folder used last time.

### Fixed

- Line numbers no longer cover the first characters of a preview.

## [0.2.2] - 2026-11-23

### Changed

- The README now lists GeoTIFF and Cloud Optimized GeoTIFF preview, including metadata, band choice, and color scales, plus preview for standard images such as JPEG and PNG.
- README screenshots are anonymized. The land-cover preview and the light and dark mode comparison no longer show a real endpoint or connection name.

## [0.2.0] - 2026-11-23

### Added

- Cloud Optimized GeoTIFF preview from a coarser overview, including files larger than 500 MB, without downloading the full raster.
- TIFF metadata in the preview: size, bands, data type, compression, tile or strip layout, overviews, the overview in use, and NoData.
- Adjustable color scales for data without an RGB style: Viridis, green-yellow-red, YlGnBu, RdYlBu, Spectral, and a random palette.
- Multi-band TIFF display as RGB with selectable bands, or as one band on a color scale.
- A copy icon on each bucket name, and a copy button for the endpoint address.
- Preview for JPEG, PNG, GIF, WebP, BMP and icons.

### Changed

- TIFF preview now loads files up to 500 MB. Larger files that are not Cloud Optimized GeoTIFFs can still be downloaded.

### Fixed

- The application no longer closes immediately when opened from the desktop icon.

## [0.1.0] - 2026-11-13

### Added

- Desktop browser for OpenStack and other S3 buckets, with saved connections and German and English.
- Folder navigation, name filters, upload, download, and delete for files and folders, including new folders.
- Preview and editing for text, YAML, XML, JSON, and CSV, plus a coarse TIFF preview.
- Light and dark mode, a transfer progress bar, and cancel for downloads.
- Right-click menu to copy a path or file name, copy and paste objects inside the bucket, and download or delete.
- Launchers for Linux, macOS, and Windows. Connections are stored in the usual per-system config folder, outside the repository.
