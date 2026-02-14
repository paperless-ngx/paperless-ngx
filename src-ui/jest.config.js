const { createEsmPreset } = require('jest-preset-angular/presets')

const esmPreset = createEsmPreset({
  tsconfig: '<rootDir>/tsconfig.spec.json',
  stringifyContentPathRegex: '\\.(html|svg)$',
})

module.exports = {
  ...esmPreset,
  transform: {
    ...esmPreset.transform,
    '^.+\\.(ts|js|mjs|html|svg)$': [
      'jest-preset-angular',
      {
        tsconfig: '<rootDir>/tsconfig.spec.json',
        stringifyContentPathRegex: '\\.(html|svg)$',
        useESM: true,
      },
    ],
  },
  setupFilesAfterEnv: ['<rootDir>/setup-jest.ts'],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/e2e/',
    'abstract-name-filter-service',
    'abstract-paperless-service',
  ],
  transformIgnorePatterns: [
    'node_modules/(?!.*(\\.mjs$|tslib|lodash-es|@angular/common/locales/.*\\.js$))',
  ],
  moduleNameMapper: {
    ...esmPreset.moduleNameMapper,
    '^src/(.*)': '<rootDir>/src/$1',
    '^pdfjs-dist/legacy/build/pdf\\.mjs$':
      '<rootDir>/src/test/mocks/pdfjs-legacy-build-pdf.ts',
    '^pdfjs-dist/web/pdf_viewer\\.mjs$':
      '<rootDir>/src/test/mocks/pdfjs-web-pdf_viewer.ts',
  },
  workerIdleMemoryLimit: '512MB',
  reporters: [
    'default',
    [
      'jest-junit',
      {
        classNameTemplate: '{filepath}/{classname}: {title}',
      },
    ],
  ],
}
