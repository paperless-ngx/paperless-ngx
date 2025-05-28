export default {
    root: true,
    ignorePatterns: ['**/dist/**'],
    plugins: ['prettier'],
    extends: ['prettier'],
    rules: {
        'padding-line-between-statements': [
            'error',
            { blankLine: 'always', prev: ['const', 'let', 'var'], next: '*' },
            { blankLine: 'any', prev: ['const', 'let', 'var'], next: ['const', 'let', 'var'] },
            { blankLine: 'any', prev: ['case', 'default'], next: 'break' },
            { blankLine: 'any', prev: 'case', next: 'case' },
            { blankLine: 'always', prev: '*', next: 'return' },
            { blankLine: 'always', prev: 'block', next: '*' },
            { blankLine: 'always', prev: '*', next: 'block' },
            { blankLine: 'always', prev: 'block-like', next: '*' },
            { blankLine: 'always', prev: '*', next: 'block-like' },
            { blankLine: 'always', prev: ['import'], next: ['const', 'let', 'var'] },
        ],
    },
    overrides: [
        {
            files: ['*.ts'],
            parserOptions: {
                project: ['tsconfig.json', 'e2e/tsconfig.json'],
                createDefaultProgram: true,
            },
            extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended', 'plugin:@angular-eslint/recommended', 'plugin:@angular-eslint/template/process-inline-templates', 'prettier'],
            rules: {
                '@angular-eslint/component-selector': [
                    'error',
                    {
                        type: 'element',
                        prefix: 'p',
                        style: 'kebab-case',
                    },
                ],
                '@angular-eslint/directive-selector': [
                    'error',
                    {
                        type: 'attribute',
                        prefix: 'p',
                        style: 'camelCase',
                    },
                ],
                '@angular-eslint/component-class-suffix': [
                    'error',
                    {
                        suffixes: [''],
                    },
                ],
                '@angular-eslint/template/eqeqeq': [
                    'error',
                    {
                        allowNullOrUndefined: true,
                    },
                ],
                '@angular-eslint/no-host-metadata-property': 'off',
                '@angular-eslint/no-output-on-prefix': 'off',
                '@typescript-eslint/ban-types': 'off',
                '@typescript-eslint/no-explicit-any': 'off',
                '@typescript-eslint/no-inferrable-types': 'off',
                'arrow-body-style': ['error', 'as-needed'],
                curly: 0,
                '@typescript-eslint/member-ordering': [
                    'error',
                    {
                        default: ['public-static-field', 'static-field', 'instance-field', 'public-instance-method', 'public-static-field'],
                    },
                ],
                'no-console': 0,
                'prefer-const': 0,
            },
        },
        {
            files: ['*.html'],
            extends: ['plugin:@angular-eslint/template/recommended', 'prettier'],
            rules: {},
        },
        {
            files: ['*.js'],
            rules: {
                parserOptions: {
                    allowImportExportEverywhere: true,
                },
            },
        },
    ],
}
