// craco.config.js
const path = require("path");
require("dotenv").config();

/*
 * webpack-dev-server v5 removed the lifecycle hooks CRA 5 still passes
 * (onBeforeSetupMiddleware / onAfterSetupMiddleware / onListening) and replaced
 * `https` with `server`. This shim translates the old shape to the new one so
 * `craco start` works against the hoisted dev-server version.
 */
function makeDevServerV5Compatible(devServerConfig) {
  const {
    https,
    onAfterSetupMiddleware,
    onBeforeSetupMiddleware,
    onListening,
    setupMiddlewares,
    ...compatibleConfig
  } = devServerConfig;

  compatibleConfig.server =
    typeof https === "object" ? { type: "https", options: https } : https ? "https" : "http";

  compatibleConfig.headers = {
    ...compatibleConfig.headers,
    "Cross-Origin-Resource-Policy": "same-origin",
  };

  if (onBeforeSetupMiddleware || setupMiddlewares) {
    compatibleConfig.setupMiddlewares = (middlewares, devServer) => {
      if (onBeforeSetupMiddleware) onBeforeSetupMiddleware(devServer);
      return setupMiddlewares ? setupMiddlewares(middlewares, devServer) : middlewares;
    };
  }

  compatibleConfig.onListening = (devServer) => {
    devServer.close ??= (callback) => devServer.stopCallback(callback);
    if (onListening) onListening(devServer);
    if (onAfterSetupMiddleware) onAfterSetupMiddleware(devServer);
  };

  return compatibleConfig;
}

module.exports = {
  // Linting runs via `npm run lint` against eslint.config.js so a single config
  // governs the editor, the CLI, and CI. CRA's inline eslint-webpack-plugin used
  // the legacy config format, which ESLint 9 rejects.
  eslint: { enable: false },

  webpack: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    configure: (webpackConfig) => {
      // Trim the watch set so the dev server does not exhaust file handles.
      webpackConfig.watchOptions = {
        ...webpackConfig.watchOptions,
        ignored: [
          "**/node_modules/**",
          "**/.git/**",
          "**/build/**",
          "**/dist/**",
          "**/coverage/**",
          "**/public/**",
        ],
      };
      return webpackConfig;
    },
  },

  devServer: (devServerConfig) => makeDevServerV5Compatible(devServerConfig),
};
