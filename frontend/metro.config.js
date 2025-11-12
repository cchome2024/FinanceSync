// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// 确保正确处理 ES 模块
config.resolver.sourceExts = [...(config.resolver.sourceExts || []), 'mjs', 'cjs'];

// 使用自定义 transformer 来处理 import.meta
config.transformer = {
  ...config.transformer,
  babelTransformerPath: path.resolve(__dirname, 'metro-transformer.js'),
};

module.exports = config;

