const fs = require("fs");
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

// Resolve symlinks / macOS /private/var vs /var so Metro's TreeFS paths match the resolver.
const projectRoot = fs.realpathSync(path.resolve(__dirname));
const config = getDefaultConfig(projectRoot);

// Duplicate-safe: Metro occasionally fails SHA-1 for sources if the tree was not
// fully crawled (new files while bundling, Watchman hiccups). Keeping an explicit
// watch folder on the app root avoids missing entries under src/.
const extraWatch = (config.watchFolders ?? []).map((folder) =>
  fs.existsSync(folder) ? fs.realpathSync(path.resolve(folder)) : folder
);
config.watchFolders = [...new Set([...extraWatch, projectRoot])];

module.exports = config;
