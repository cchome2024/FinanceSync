const upstreamTransformer = require('@expo/metro-config/babel-transformer');

module.exports = {
  transform: function ({ src, filename, options }) {
    // 替换 import.meta 为兼容的代码
    if (src.includes('import.meta')) {
      src = src.replace(
        /import\.meta\.url/g,
        'typeof document !== "undefined" && document.currentScript ? document.currentScript.src : ""'
      );
      src = src.replace(
        /import\.meta/g,
        '{ url: typeof document !== "undefined" && document.currentScript ? document.currentScript.src : "" }'
      );
    }
    
    return upstreamTransformer.transform({ src, filename, options });
  }
};

