module.exports = {
  preset: 'jest-preset-angular',
  setupFilesAfterEnv: ['<rootDir>/setup-jest.ts'],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/e2e/',
    'abstract-name-filter-service',
    'abstract-paperless-service',
  ],
  transformIgnorePatterns: [
    `<rootDir>/node_modules/.pnpm/(?!.*\\.mjs$|lodash-es|@angular\\+common.*locales)`,
  ],
  moduleNameMapper: {
    '^src/(.*)': '<rootDir>/src/$1',
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
