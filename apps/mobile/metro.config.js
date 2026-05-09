const { getDefaultConfig } = require("expo/metro-config");

const projectRoot = __dirname;
const config = getDefaultConfig(projectRoot);

// Duplicate-safe: Metro occasionally fails SHA-1 for sources if the tree was not
// fully crawled (new files while bundling, Watchman hiccups). Keeping an explicit
// watch folder on the app root avoids missing entries under src/.
config.watchFolders = [...new Set([...(config.watchFolders ?? []), projectRoot])];

module.exports = config;
