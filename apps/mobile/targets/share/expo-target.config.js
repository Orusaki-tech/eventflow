/** @type {import("@bacons/apple-targets/app.plugin").ConfigFunction} */
module.exports = (config) => ({
  type: "share",
  name: "EventFlowShare",
  displayName: "EventFlow",
  deploymentTarget: "15.1",
  entitlements: {
    "com.apple.security.application-groups":
      config.ios?.entitlements?.["com.apple.security.application-groups"] ?? [],
  },
});
