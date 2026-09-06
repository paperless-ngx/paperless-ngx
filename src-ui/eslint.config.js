const angularEslintPlugin = require('@angular-eslint/eslint-plugin')
const angularTemplatePlugin = require('@angular-eslint/eslint-plugin-template')
const angularTemplateParser = require('@angular-eslint/template-parser')
const tsParser = require('@typescript-eslint/parser')

const angularTsRecommendedRules = {
  '@angular-eslint/contextual-lifecycle': 'error',
  '@angular-eslint/no-empty-lifecycle-method': 'error',
  '@angular-eslint/no-input-rename': 'error',
  '@angular-eslint/no-inputs-metadata-property': 'error',
  '@angular-eslint/no-output-native': 'error',
  '@angular-eslint/no-output-on-prefix': 'error',
  '@angular-eslint/no-output-rename': 'error',
  '@angular-eslint/no-outputs-metadata-property': 'error',
  '@angular-eslint/prefer-inject': 'error',
  '@angular-eslint/prefer-standalone': 'error',
  '@angular-eslint/use-pipe-transform-interface': 'error',
  '@angular-eslint/use-lifecycle-interface': 'warn',
}
const angularTemplateRecommendedRules = {
  '@angular-eslint/template/banana-in-box': 'error',
  '@angular-eslint/template/eqeqeq': 'error',
  '@angular-eslint/template/no-negated-async': 'error',
  '@angular-eslint/template/prefer-control-flow': 'error',
}

module.exports = [
  {
    ignores: ['projects/**/*', 'src/app/components/common/pdf-viewer/**'],
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
      },
    },
    plugins: {
      '@angular-eslint': angularEslintPlugin,
      '@angular-eslint/template': angularTemplatePlugin,
    },
    processor: angularTemplatePlugin.processors['extract-inline-html'],
    rules: {
      ...angularTsRecommendedRules,
      '@angular-eslint/directive-selector': [
        'error',
        {
          type: 'attribute',
          prefix: 'pngx',
          style: 'camelCase',
        },
      ],
      '@angular-eslint/component-selector': [
        'error',
        {
          type: 'element',
          prefix: 'pngx',
          style: 'kebab-case',
        },
      ],
    },
  },
  {
    files: ['**/*.html'],
    languageOptions: {
      parser: angularTemplateParser,
    },
    plugins: {
      '@angular-eslint/template': angularTemplatePlugin,
    },
    rules: {
      ...angularTemplateRecommendedRules,
    },
  },
]
