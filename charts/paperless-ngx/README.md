# paperless

![Version: 10.0.0](https://img.shields.io/badge/Version-10.0.0-informational?style=flat-square) ![AppVersion: 1.9.2](https://img.shields.io/badge/AppVersion-1.9.2-informational?style=flat-square)

Paperless-ngx - Index and archive all of your scanned paper documents

**Homepage:** <https://github.com/paperless-ngx/paperless-ngx/tree/main/charts/paperless-ngx>

## Maintainers

| Name | Email | Url |
| ---- | ------ | --- |
| Paperless-ngx maintainers |  |  |

## Source Code

* <https://github.com/paperless-ngx/paperless-ngx>

## Requirements

Kubernetes: `>=1.16.0-0`

| Repository | Name | Version |
|------------|------|---------|
| https://charts.bitnami.com/bitnami | postgresql | 11.6.12 |
| https://charts.bitnami.com/bitnami | redis | 16.13.1 |
| https://library-charts.k8s-at-home.com | common | 4.5.2 |

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| env | object | See below | See the following files for additional environment variables: https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose/ https://github.com/paperless-ngx/paperless-ngx/blob/main/paperless.conf.example |
| env.COMPOSE_PROJECT_NAME | string | `"paperless"` | Project name |
| env.PAPERLESS_DBHOST | string | `nil` | Database host to use |
| env.PAPERLESS_OCR_LANGUAGE | string | `"eng"` | OCR languages to install |
| env.PAPERLESS_PORT | int | `8000` | Port to use |
| env.PAPERLESS_REDIS | string | `nil` | Redis to use |
| image.pullPolicy | string | `"IfNotPresent"` | image pull policy |
| image.repository | string | `"ghcr.io/paperless-ngx/paperless-ngx"` | image repository |
| image.tag | string | chart.appVersion | image tag |
| ingress.main | object | See values.yaml | Enable and configure ingress settings for the chart under this key. |
| persistence.consume | object | See values.yaml | Configure volume to monitor for new documents. |
| persistence.data | object | See values.yaml | Configure persistence for data. |
| persistence.export | object | See values.yaml | Configure export volume. |
| persistence.media | object | See values.yaml | Configure persistence for media. |
| postgresql | object | See values.yaml | Enable and configure postgresql database subchart under this key.    For more options see [postgresql chart documentation](https://github.com/bitnami/charts/tree/master/bitnami/postgresql) |
| redis | object | See values.yaml | Enable and configure redis subchart under this key.    For more options see [redis chart documentation](https://github.com/bitnami/charts/tree/master/bitnami/redis) |
| service | object | See values.yaml | Configures service settings for the chart. |

