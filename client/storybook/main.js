import { mergeRsbuildConfig } from '@rsbuild/core';
import { pluginSass } from '@rsbuild/plugin-sass';

const storybook = {
  stories: [
    '../../client/**/*.mdx',
    '../../client/**/*.stories.@(js|tsx)',
    '../../wagtail/**/*.@(mdx|stories.*)',
  ],

  addons: ['@storybook/addon-docs'],
  framework: { name: 'storybook-react-rsbuild', options: {} },

  rsbuildFinal: (config) =>
    mergeRsbuildConfig(config, {
      plugins: [pluginSass()],
      tools: {
        cssLoader: { url: false },
        postcss: (opts) => {
          opts.postcssOptions = opts.postcssOptions || {};
          opts.postcssOptions.plugins = [
            ...(opts.postcssOptions.plugins || []),
            'tailwindcss',
            'autoprefixer',
            'cssnano',
          ];
        },
        rspack: (rspackConfig, { appendRules }) => {
          appendRules({ test: /\.(md|html)$/, type: 'asset/source' });
          // Allow using path magic variables to reduce boilerplate in stories.
          rspackConfig.node = {
            ...(rspackConfig.node || {}),
            __filename: true,
            __dirname: true,
          };
        },
      },
    }),

  typescript: {
    reactDocgen: 'react-docgen',
  },
};

export default storybook;
