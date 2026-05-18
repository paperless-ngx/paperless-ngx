const angularEslintPlugin = require('@angular-eslint/eslint-plugin')
const angularTemplatePlugin = require('@angular-eslint/eslint-plugin-template')
const angularTemplateParser = require('@angular-eslint/template-parser')
const tsParser = require('@typescript-eslint/parser')

module.exports = [
  {
    ignores: ['projects/**/*', 'src/app/components/common/pdf-viewer/**'],
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: ['tsconfig.json'],
        createDefaultProgram: true,
        ecmaVersion: 2020,
        sourceType: 'module',
      },
    },
    plugins: {
      '@angular-eslint': angularEslintPlugin,
      '@angular-eslint/template': angularTemplatePlugin,
    },
    processor: '@angular-eslint/template/extract-inline-html',
    rules: {
      ...angularEslintPlugin.configs.recommended.rules,
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
      ...angularTemplatePlugin.configs.recommended.rules,
    },
  },
]
