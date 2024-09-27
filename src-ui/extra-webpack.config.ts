import * as webpack from 'webpack'
import {
  CustomWebpackBrowserSchema,
  TargetOptions,
} from '@angular-builders/custom-webpack'
const { codecovWebpackPlugin } = require('@codecov/webpack-plugin')

export default (
  config: webpack.Configuration,
  options: CustomWebpackBrowserSchema,
  targetOptions: TargetOptions
) => {
  if (config.plugins) {
    config.plugins.push(
      codecovWebpackPlugin({
        enableBundleAnalysis: process.env.CODECOV_TOKEN !== undefined,
        bundleName: 'paperless-ngx',
        uploadToken: process.env.CODECOV_TOKEN,
      })
    )
  }

  return config
}
