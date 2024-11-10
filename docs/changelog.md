# Changelog

## paperless-ngx 2.13.5

### Bug Fixes

-   Fix: handle page count exception for pw-protected files [@shamoon](https://github.com/shamoon) ([#8240](https://github.com/paperless-ngx/paperless-ngx/pull/8240))
-   Fix: correctly track task id in list for change detection [@shamoon](https://github.com/shamoon) ([#8230](https://github.com/paperless-ngx/paperless-ngx/pull/8230))
-   Fix: Admin pages should show trashed documents [@stumpylog](https://github.com/stumpylog) ([#8068](https://github.com/paperless-ngx/paperless-ngx/pull/8068))
-   Fix: tag colors shouldn't change when selected in list [@shamoon](https://github.com/shamoon) ([#8225](https://github.com/paperless-ngx/paperless-ngx/pull/8225))
-   Fix: fix re-activation of save button when changing array items [@shamoon](https://github.com/shamoon) ([#8208](https://github.com/paperless-ngx/paperless-ngx/pull/8208))
-   Fix: fix thumbnail clipping, select inverted color in safari dark mode not system [@shamoon](https://github.com/shamoon) ([#8193](https://github.com/paperless-ngx/paperless-ngx/pull/8193))
-   Fix: select checkbox should remain visible [@shamoon](https://github.com/shamoon) ([#8185](https://github.com/paperless-ngx/paperless-ngx/pull/8185))
-   Fix: warn with proper error on ASN exists in trash [@shamoon](https://github.com/shamoon) ([#8176](https://github.com/paperless-ngx/paperless-ngx/pull/8176))

### Maintenance

-   Chore: Updates all runner images to use Ubuntu Noble [@stumpylog](https://github.com/stumpylog) ([#8213](https://github.com/paperless-ngx/paperless-ngx/pull/8213))
-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.8.0 to 0.9.0 in the actions group [@dependabot](https://github.com/dependabot) ([#8142](https://github.com/paperless-ngx/paperless-ngx/pull/8142))

### Dependencies

-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.8.0 to 0.9.0 in the actions group [@dependabot](https://github.com/dependabot) ([#8142](https://github.com/paperless-ngx/paperless-ngx/pull/8142))

### All App Changes

<details>
<summary>7 changes</summary>

-   Fix: handle page count exception for pw-protected files [@shamoon](https://github.com/shamoon) ([#8240](https://github.com/paperless-ngx/paperless-ngx/pull/8240))
-   Fix: correctly track task id in list for change detection [@shamoon](https://github.com/shamoon) ([#8230](https://github.com/paperless-ngx/paperless-ngx/pull/8230))
-   Fix: Admin pages should show trashed documents [@stumpylog](https://github.com/stumpylog) ([#8068](https://github.com/paperless-ngx/paperless-ngx/pull/8068))
-   Fix: tag colors shouldn't change when selected in list [@shamoon](https://github.com/shamoon) ([#8225](https://github.com/paperless-ngx/paperless-ngx/pull/8225))
-   Fix: fix re-activation of save button when changing array items [@shamoon](https://github.com/shamoon) ([#8208](https://github.com/paperless-ngx/paperless-ngx/pull/8208))
-   Fix: fix thumbnail clipping, select inverted color in safari dark mode not system [@shamoon](https://github.com/shamoon) ([#8193](https://github.com/paperless-ngx/paperless-ngx/pull/8193))
-   Fix: select checkbox should remain visible [@shamoon](https://github.com/shamoon) ([#8185](https://github.com/paperless-ngx/paperless-ngx/pull/8185))
-   Fix: warn with proper error on ASN exists in trash [@shamoon](https://github.com/shamoon) ([#8176](https://github.com/paperless-ngx/paperless-ngx/pull/8176))
</details>

## paperless-ngx 2.13.4

### Bug Fixes

-   Fix: fix dark mode icon blend mode in 2.13.3 [@shamoon](https://github.com/shamoon) ([#8166](https://github.com/paperless-ngx/paperless-ngx/pull/8166))
-   Fix: fix clipped popup preview in 2.13.3 [@shamoon](https://github.com/shamoon) ([#8165](https://github.com/paperless-ngx/paperless-ngx/pull/8165))

### All App Changes

<details>
<summary>2 changes</summary>

-   Fix: fix dark mode icon blend mode in 2.13.3 [@shamoon](https://github.com/shamoon) ([#8166](https://github.com/paperless-ngx/paperless-ngx/pull/8166))
-   Fix: fix clipped popup preview in 2.13.3 [@shamoon](https://github.com/shamoon) ([#8165](https://github.com/paperless-ngx/paperless-ngx/pull/8165))
</details>

## paperless-ngx 2.13.3

### Bug Fixes

-   Fix: fix auto-clean PDFs, create parent dir for storing unmodified original [@shamoon](https://github.com/shamoon) ([#8157](https://github.com/paperless-ngx/paperless-ngx/pull/8157))
-   Fix: correctly handle exists, false in custom field query filter @yichi-yang ([#8158](https://github.com/paperless-ngx/paperless-ngx/pull/8158))
-   Fix: dont use filters for inverted thumbnails in Safari [@shamoon](https://github.com/shamoon) ([#8121](https://github.com/paperless-ngx/paperless-ngx/pull/8121))
-   Fix: use static object for activedisplayfields to prevent changes [@shamoon](https://github.com/shamoon) ([#8120](https://github.com/paperless-ngx/paperless-ngx/pull/8120))
-   Fix: dont invert pdf colors in FF [@shamoon](https://github.com/shamoon) ([#8110](https://github.com/paperless-ngx/paperless-ngx/pull/8110))
-   Fix: make mail account password and refresh token text fields [@shamoon](https://github.com/shamoon) ([#8107](https://github.com/paperless-ngx/paperless-ngx/pull/8107))

### Dependencies

<details>
<summary>8 changes</summary>

-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#8145](https://github.com/paperless-ngx/paperless-ngx/pull/8145))
-   Chore(deps-dev): Bump @types/node from 22.7.4 to 22.8.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#8148](https://github.com/paperless-ngx/paperless-ngx/pull/8148))
-   Chore(deps-dev): Bump @playwright/test from 1.47.2 to 1.48.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#8147](https://github.com/paperless-ngx/paperless-ngx/pull/8147))
-   Chore(deps): Bump uuid from 10.0.0 to 11.0.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#8146](https://github.com/paperless-ngx/paperless-ngx/pull/8146))
-   Chore(deps): Bump tslib from 2.7.0 to 2.8.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#8149](https://github.com/paperless-ngx/paperless-ngx/pull/8149))
-   Chore(deps-dev): Bump @codecov/webpack-plugin from 1.2.0 to 1.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#8150](https://github.com/paperless-ngx/paperless-ngx/pull/8150))
-   Chore(deps-dev): Bump @types/jest from 29.5.13 to 29.5.14 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#8144](https://github.com/paperless-ngx/paperless-ngx/pull/8144))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#8143](https://github.com/paperless-ngx/paperless-ngx/pull/8143))
</details>

### All App Changes

<details>
<summary>14 changes</summary>

-   Fix: fix auto-clean PDFs, create parent dir for storing unmodified original [@shamoon](https://github.com/shamoon) ([#8157](https://github.com/paperless-ngx/paperless-ngx/pull/8157))
-   Fix: correctly handle exists, false in custom field query filter @yichi-yang ([#8158](https://github.com/paperless-ngx/paperless-ngx/pull/8158))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#8145](https://github.com/paperless-ngx/paperless-ngx/pull/8145))
-   Chore(deps-dev): Bump @types/node from 22.7.4 to 22.8.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#8148](https://github.com/paperless-ngx/paperless-ngx/pull/8148))
-   Chore(deps-dev): Bump @playwright/test from 1.47.2 to 1.48.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#8147](https://github.com/paperless-ngx/paperless-ngx/pull/8147))
-   Chore(deps): Bump uuid from 10.0.0 to 11.0.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#8146](https://github.com/paperless-ngx/paperless-ngx/pull/8146))
-   Chore(deps): Bump tslib from 2.7.0 to 2.8.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#8149](https://github.com/paperless-ngx/paperless-ngx/pull/8149))
-   Chore(deps-dev): Bump @codecov/webpack-plugin from 1.2.0 to 1.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#8150](https://github.com/paperless-ngx/paperless-ngx/pull/8150))
-   Chore(deps-dev): Bump @types/jest from 29.5.13 to 29.5.14 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#8144](https://github.com/paperless-ngx/paperless-ngx/pull/8144))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#8143](https://github.com/paperless-ngx/paperless-ngx/pull/8143))
-   Fix: dont use filters for inverted thumbnails in Safari [@shamoon](https://github.com/shamoon) ([#8121](https://github.com/paperless-ngx/paperless-ngx/pull/8121))
-   Fix: use static object for activedisplayfields to prevent changes [@shamoon](https://github.com/shamoon) ([#8120](https://github.com/paperless-ngx/paperless-ngx/pull/8120))
-   Fix: dont invert pdf colors in FF [@shamoon](https://github.com/shamoon) ([#8110](https://github.com/paperless-ngx/paperless-ngx/pull/8110))
-   Fix: make mail account password and refresh token text fields [@shamoon](https://github.com/shamoon) ([#8107](https://github.com/paperless-ngx/paperless-ngx/pull/8107))
</details>

## paperless-ngx 2.13.2

### Bug Fixes

-   Fix: remove auth tokens from export [@shamoon](https://github.com/shamoon) ([#8100](https://github.com/paperless-ngx/paperless-ngx/pull/8100))
-   Fix: cf query dropdown styling affecting other components [@shamoon](https://github.com/shamoon) ([#8095](https://github.com/paperless-ngx/paperless-ngx/pull/8095))

### All App Changes

<details>
<summary>2 changes</summary>

-   Fix: remove auth tokens from export [@shamoon](https://github.com/shamoon) ([#8100](https://github.com/paperless-ngx/paperless-ngx/pull/8100))
-   Fix: cf query dropdown styling affecting other components [@shamoon](https://github.com/shamoon) ([#8095](https://github.com/paperless-ngx/paperless-ngx/pull/8095))
</details>

## paperless-ngx 2.13.1

### Bug Fixes

-   Fix: allow removing dead document links from UI, validate via API [@shamoon](https://github.com/shamoon) ([#8081](https://github.com/paperless-ngx/paperless-ngx/pull/8081))
-   Fix: Removes whitenoise patches and upgrades it to 6.8.1 [@stumpylog](https://github.com/stumpylog) ([#8079](https://github.com/paperless-ngx/paperless-ngx/pull/8079))
-   Fix: Make all document related objects soft delete, fix filepath when deleted [@shamoon](https://github.com/shamoon) ([#8067](https://github.com/paperless-ngx/paperless-ngx/pull/8067))
-   Fix: handle uuid fields created under mariadb and Django 4 [@shamoon](https://github.com/shamoon) ([#8034](https://github.com/paperless-ngx/paperless-ngx/pull/8034))
-   Fix: Update filename correctly if the document is in the trash [@stumpylog](https://github.com/stumpylog) ([#8066](https://github.com/paperless-ngx/paperless-ngx/pull/8066))
-   Fix: Handle a special case where removing none marker could result in an absolute path [@stumpylog](https://github.com/stumpylog) ([#8060](https://github.com/paperless-ngx/paperless-ngx/pull/8060))
-   Fix: disable custom field signals during import in 2.13.0 [@shamoon](https://github.com/shamoon) ([#8065](https://github.com/paperless-ngx/paperless-ngx/pull/8065))
-   Fix: doc link documents search should exclude null [@shamoon](https://github.com/shamoon) ([#8064](https://github.com/paperless-ngx/paperless-ngx/pull/8064))
-   Fix: fix custom field query empty element removal [@shamoon](https://github.com/shamoon) ([#8056](https://github.com/paperless-ngx/paperless-ngx/pull/8056))
-   Fix / Enhancement: auto-rename document files when select type custom fields are changed [@shamoon](https://github.com/shamoon) ([#8045](https://github.com/paperless-ngx/paperless-ngx/pull/8045))
-   Fix: dont try to load PAPERLESS_MODEL_FILE as env from file [@shamoon](https://github.com/shamoon) ([#8040](https://github.com/paperless-ngx/paperless-ngx/pull/8040))
-   Fix: dont include all allauth urls [@shamoon](https://github.com/shamoon) ([#8010](https://github.com/paperless-ngx/paperless-ngx/pull/8010))
-   Fix: oauth settings without base url [@shamoon](https://github.com/shamoon) ([#8020](https://github.com/paperless-ngx/paperless-ngx/pull/8020))
-   Fix / Enhancement: include social accounts and api tokens in export [@shamoon](https://github.com/shamoon) ([#8016](https://github.com/paperless-ngx/paperless-ngx/pull/8016))

### Maintenance

-   Fix: Removes whitenoise patches and upgrades it to 6.8.1 [@stumpylog](https://github.com/stumpylog) ([#8079](https://github.com/paperless-ngx/paperless-ngx/pull/8079))

### All App Changes

<details>
<summary>12 changes</summary>

-   Fix: allow removing dead document links from UI, validate via API [@shamoon](https://github.com/shamoon) ([#8081](https://github.com/paperless-ngx/paperless-ngx/pull/8081))
-   Fix: Make all document related objects soft delete, fix filepath when deleted [@shamoon](https://github.com/shamoon) ([#8067](https://github.com/paperless-ngx/paperless-ngx/pull/8067))
-   Fix: handle uuid fields created under mariadb and Django 4 [@shamoon](https://github.com/shamoon) ([#8034](https://github.com/paperless-ngx/paperless-ngx/pull/8034))
-   Fix: Update filename correctly if the document is in the trash [@stumpylog](https://github.com/stumpylog) ([#8066](https://github.com/paperless-ngx/paperless-ngx/pull/8066))
-   Fix: Handle a special case where removing none marker could result in an absolute path [@stumpylog](https://github.com/stumpylog) ([#8060](https://github.com/paperless-ngx/paperless-ngx/pull/8060))
-   Fix: disable custom field signals during import in 2.13.0 [@shamoon](https://github.com/shamoon) ([#8065](https://github.com/paperless-ngx/paperless-ngx/pull/8065))
-   Fix: doc link documents search should exclude null [@shamoon](https://github.com/shamoon) ([#8064](https://github.com/paperless-ngx/paperless-ngx/pull/8064))
-   Enhancement: auto-rename document files when select type custom fields are changed [@shamoon](https://github.com/shamoon) ([#8045](https://github.com/paperless-ngx/paperless-ngx/pull/8045))
-   Fix: fix custom field query empty element removal [@shamoon](https://github.com/shamoon) ([#8056](https://github.com/paperless-ngx/paperless-ngx/pull/8056))
-   Fix: dont include all allauth urls [@shamoon](https://github.com/shamoon) ([#8010](https://github.com/paperless-ngx/paperless-ngx/pull/8010))
-   Enhancement / fix: include social accounts and api tokens in export [@shamoon](https://github.com/shamoon) ([#8016](https://github.com/paperless-ngx/paperless-ngx/pull/8016))
-   Fix: oauth settings without base url [@shamoon](https://github.com/shamoon) ([#8020](https://github.com/paperless-ngx/paperless-ngx/pull/8020))
</details>

## paperless-ngx 2.13.0

### Notable Changes

-   Feature: OAuth2 Gmail and Outlook email support [@shamoon](https://github.com/shamoon) ([#7866](https://github.com/paperless-ngx/paperless-ngx/pull/7866))
-   Feature: Enhanced templating for filename format [@stumpylog](https://github.com/stumpylog) ([#7836](https://github.com/paperless-ngx/paperless-ngx/pull/7836))
-   Feature: custom fields queries [@shamoon](https://github.com/shamoon) ([#7761](https://github.com/paperless-ngx/paperless-ngx/pull/7761))
-   Chore: Drop Python 3.9 support [@stumpylog](https://github.com/stumpylog) ([#7774](https://github.com/paperless-ngx/paperless-ngx/pull/7774))

### Features

-   Enhancement: QoL, auto-focus default select field in custom field dropdown [@shamoon](https://github.com/shamoon) ([#7961](https://github.com/paperless-ngx/paperless-ngx/pull/7961))
-   Change: open not edit [@shamoon](https://github.com/shamoon) ([#7942](https://github.com/paperless-ngx/paperless-ngx/pull/7942))
-   Enhancement: support retain barcode split pages [@shamoon](https://github.com/shamoon) ([#7912](https://github.com/paperless-ngx/paperless-ngx/pull/7912))
-   Enhancement: don't wait for doc API to load preview [@shamoon](https://github.com/shamoon) ([#7894](https://github.com/paperless-ngx/paperless-ngx/pull/7894))
-   Feature: OAuth2 Gmail and Outlook email support [@shamoon](https://github.com/shamoon) ([#7866](https://github.com/paperless-ngx/paperless-ngx/pull/7866))
-   Enhancement: live preview of storage path [@shamoon](https://github.com/shamoon) ([#7870](https://github.com/paperless-ngx/paperless-ngx/pull/7870))
-   Enhancement: management list button improvements [@shamoon](https://github.com/shamoon) ([#7848](https://github.com/paperless-ngx/paperless-ngx/pull/7848))
-   Enhancement: check for mail destination directory, log post-consume errors [@mrichtarsky](https://github.com/mrichtarsky) ([#7808](https://github.com/paperless-ngx/paperless-ngx/pull/7808))
-   Enhancement: workflow overview toggle enable button [@shamoon](https://github.com/shamoon) ([#7818](https://github.com/paperless-ngx/paperless-ngx/pull/7818))
-   Enhancement: disable-able mail rules, add toggle to overview [@shamoon](https://github.com/shamoon) ([#7810](https://github.com/paperless-ngx/paperless-ngx/pull/7810))
-   Feature: auto-clean some invalid pdfs [@shamoon](https://github.com/shamoon) ([#7651](https://github.com/paperless-ngx/paperless-ngx/pull/7651))
-   Feature: page count [@s0llvan](https://github.com/s0llvan) ([#7750](https://github.com/paperless-ngx/paperless-ngx/pull/7750))
-   Enhancement: use apt only when needed docker-entrypoint.sh [@gawa971](https://github.com/gawa971) ([#7756](https://github.com/paperless-ngx/paperless-ngx/pull/7756))
-   Enhancement: set Django SESSION_EXPIRE_AT_BROWSER_CLOSE from PAPERLESS_ACCOUNT_SESSION_REMEMBER [@shamoon](https://github.com/shamoon) ([#7748](https://github.com/paperless-ngx/paperless-ngx/pull/7748))
-   Enhancement: allow setting session cookie age [@shamoon](https://github.com/shamoon) ([#7743](https://github.com/paperless-ngx/paperless-ngx/pull/7743))
-   Feature: copy workflows and mail rules, improve layout [@shamoon](https://github.com/shamoon) ([#7727](https://github.com/paperless-ngx/paperless-ngx/pull/7727))

### Bug Fixes

-   Fix: remove space before my profile button in dropdown [@tooomm](https://github.com/tooomm) ([#7963](https://github.com/paperless-ngx/paperless-ngx/pull/7963))
-   Fix: v2.13.0 RC1 - Handling of Nones when using custom fields in filepath templating [@stumpylog](https://github.com/stumpylog) ([#7933](https://github.com/paperless-ngx/paperless-ngx/pull/7933))
-   Fix: v2.13.0 RC1 - trigger move and rename after CustomFieldInstance saved [@shamoon](https://github.com/shamoon) ([#7927](https://github.com/paperless-ngx/paperless-ngx/pull/7927))
-   Fix: v2.13.0 RC1 - increase field max lengths to accommodate larger tokens [@shamoon](https://github.com/shamoon) ([#7916](https://github.com/paperless-ngx/paperless-ngx/pull/7916))
-   Fix: preserve text linebreaks in doc edit [@shamoon](https://github.com/shamoon) ([#7908](https://github.com/paperless-ngx/paperless-ngx/pull/7908))
-   Fix: only show colon on cards if correspondent and title shown [@shamoon](https://github.com/shamoon) ([#7893](https://github.com/paperless-ngx/paperless-ngx/pull/7893))
-   Fix: Allow ASN values of 0 from barcodes [@stumpylog](https://github.com/stumpylog) ([#7878](https://github.com/paperless-ngx/paperless-ngx/pull/7878))
-   Fix: fix auto-dismiss completed tasks on open document [@shamoon](https://github.com/shamoon) ([#7869](https://github.com/paperless-ngx/paperless-ngx/pull/7869))
-   Fix: trigger change warning for saved views with default fields if changed [@shamoon](https://github.com/shamoon) ([#7865](https://github.com/paperless-ngx/paperless-ngx/pull/7865))
-   Fix: hidden canvas element causes scroll bug [@shamoon](https://github.com/shamoon) ([#7770](https://github.com/paperless-ngx/paperless-ngx/pull/7770))
-   Fix: handle overflowing dropdowns on mobile [@shamoon](https://github.com/shamoon) ([#7758](https://github.com/paperless-ngx/paperless-ngx/pull/7758))
-   Fix: chrome scrolling in >= 129 [@shamoon](https://github.com/shamoon) ([#7738](https://github.com/paperless-ngx/paperless-ngx/pull/7738))

### Maintenance

-   Enhancement: use apt only when needed docker-entrypoint.sh [@gawa971](https://github.com/gawa971) ([#7756](https://github.com/paperless-ngx/paperless-ngx/pull/7756))

### Dependencies

<details>
<summary>10 changes</summary>

-   Chore(deps-dev): Bump @codecov/webpack-plugin from 1.0.1 to 1.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7830](https://github.com/paperless-ngx/paperless-ngx/pull/7830))
-   Chore(deps-dev): Bump @types/node from 22.5.2 to 22.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7829](https://github.com/paperless-ngx/paperless-ngx/pull/7829))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7827](https://github.com/paperless-ngx/paperless-ngx/pull/7827))
-   Chore(deps-dev): Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#7826](https://github.com/paperless-ngx/paperless-ngx/pull/7826))
-   Chore(deps-dev): Bump @playwright/test from 1.46.1 to 1.47.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#7828](https://github.com/paperless-ngx/paperless-ngx/pull/7828))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#7825](https://github.com/paperless-ngx/paperless-ngx/pull/7825))
-   Chore: Upgrades OCRMyPDF to v16 [@stumpylog](https://github.com/stumpylog) ([#7815](https://github.com/paperless-ngx/paperless-ngx/pull/7815))
-   Chore: Upgrades the Docker image to use Python 3.12 [@stumpylog](https://github.com/stumpylog) ([#7796](https://github.com/paperless-ngx/paperless-ngx/pull/7796))
-   Chore: Upgrade Django to 5.1 [@stumpylog](https://github.com/stumpylog) ([#7795](https://github.com/paperless-ngx/paperless-ngx/pull/7795))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7723](https://github.com/paperless-ngx/paperless-ngx/pull/7723))
</details>

### All App Changes

<details>
<summary>43 changes</summary>

-   Change: Use a TextField for the storage path field [@stumpylog](https://github.com/stumpylog) ([#7967](https://github.com/paperless-ngx/paperless-ngx/pull/7967))
-   Fix: remove space before my profile button in dropdown [@tooomm](https://github.com/tooomm) ([#7963](https://github.com/paperless-ngx/paperless-ngx/pull/7963))
-   Enhancement: QoL, auto-focus default select field in custom field dropdown [@shamoon](https://github.com/shamoon) ([#7961](https://github.com/paperless-ngx/paperless-ngx/pull/7961))
-   Change: open not edit [@shamoon](https://github.com/shamoon) ([#7942](https://github.com/paperless-ngx/paperless-ngx/pull/7942))
-   Fix: v2.13.0 RC1 - Handling of Nones when using custom fields in filepath templating [@stumpylog](https://github.com/stumpylog) ([#7933](https://github.com/paperless-ngx/paperless-ngx/pull/7933))
-   Fix: v2.13.0 RC1 - trigger move and rename after CustomFieldInstance saved [@shamoon](https://github.com/shamoon) ([#7927](https://github.com/paperless-ngx/paperless-ngx/pull/7927))
-   Fix: v2.13.0 RC1 - increase field max lengths to accommodate larger tokens [@shamoon](https://github.com/shamoon) ([#7916](https://github.com/paperless-ngx/paperless-ngx/pull/7916))
-   Enhancement: support retain barcode split pages [@shamoon](https://github.com/shamoon) ([#7912](https://github.com/paperless-ngx/paperless-ngx/pull/7912))
-   Fix: preserve text linebreaks in doc edit [@shamoon](https://github.com/shamoon) ([#7908](https://github.com/paperless-ngx/paperless-ngx/pull/7908))
-   Enhancement: don't wait for doc API to load preview [@shamoon](https://github.com/shamoon) ([#7894](https://github.com/paperless-ngx/paperless-ngx/pull/7894))
-   Fix: only show colon on cards if correspondent and title shown [@shamoon](https://github.com/shamoon) ([#7893](https://github.com/paperless-ngx/paperless-ngx/pull/7893))
-   Feature: OAuth2 Gmail and Outlook email support [@shamoon](https://github.com/shamoon) ([#7866](https://github.com/paperless-ngx/paperless-ngx/pull/7866))
-   Chore: Consolidate workflow logic [@shamoon](https://github.com/shamoon) ([#7880](https://github.com/paperless-ngx/paperless-ngx/pull/7880))
-   Enhancement: live preview of storage path [@shamoon](https://github.com/shamoon) ([#7870](https://github.com/paperless-ngx/paperless-ngx/pull/7870))
-   Fix: Allow ASN values of 0 from barcodes [@stumpylog](https://github.com/stumpylog) ([#7878](https://github.com/paperless-ngx/paperless-ngx/pull/7878))
-   Fix: fix auto-dismiss completed tasks on open document [@shamoon](https://github.com/shamoon) ([#7869](https://github.com/paperless-ngx/paperless-ngx/pull/7869))
-   Fix: trigger change warning for saved views with default fields if changed [@shamoon](https://github.com/shamoon) ([#7865](https://github.com/paperless-ngx/paperless-ngx/pull/7865))
-   Feature: Enhanced templating for filename format [@stumpylog](https://github.com/stumpylog) ([#7836](https://github.com/paperless-ngx/paperless-ngx/pull/7836))
-   Enhancement: management list button improvements [@shamoon](https://github.com/shamoon) ([#7848](https://github.com/paperless-ngx/paperless-ngx/pull/7848))
-   Enhancement: check for mail destination directory, log post-consume errors [@mrichtarsky](https://github.com/mrichtarsky) ([#7808](https://github.com/paperless-ngx/paperless-ngx/pull/7808))
-   Feature: custom fields queries [@shamoon](https://github.com/shamoon) ([#7761](https://github.com/paperless-ngx/paperless-ngx/pull/7761))
-   Chore(deps-dev): Bump @codecov/webpack-plugin from 1.0.1 to 1.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7830](https://github.com/paperless-ngx/paperless-ngx/pull/7830))
-   Chore(deps-dev): Bump @types/node from 22.5.2 to 22.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7829](https://github.com/paperless-ngx/paperless-ngx/pull/7829))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7827](https://github.com/paperless-ngx/paperless-ngx/pull/7827))
-   Chore(deps-dev): Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#7826](https://github.com/paperless-ngx/paperless-ngx/pull/7826))
-   Chore(deps-dev): Bump @playwright/test from 1.46.1 to 1.47.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#7828](https://github.com/paperless-ngx/paperless-ngx/pull/7828))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#7825](https://github.com/paperless-ngx/paperless-ngx/pull/7825))
-   Chore: Upgrades OCRMyPDF to v16 [@stumpylog](https://github.com/stumpylog) ([#7815](https://github.com/paperless-ngx/paperless-ngx/pull/7815))
-   Enhancement: workflow overview toggle enable button [@shamoon](https://github.com/shamoon) ([#7818](https://github.com/paperless-ngx/paperless-ngx/pull/7818))
-   Enhancement: disable-able mail rules, add toggle to overview [@shamoon](https://github.com/shamoon) ([#7810](https://github.com/paperless-ngx/paperless-ngx/pull/7810))
-   Chore: Upgrades the Docker image to use Python 3.12 [@stumpylog](https://github.com/stumpylog) ([#7796](https://github.com/paperless-ngx/paperless-ngx/pull/7796))
-   Chore: Upgrade Django to 5.1 [@stumpylog](https://github.com/stumpylog) ([#7795](https://github.com/paperless-ngx/paperless-ngx/pull/7795))
-   Chore: Drop Python 3.9 support [@stumpylog](https://github.com/stumpylog) ([#7774](https://github.com/paperless-ngx/paperless-ngx/pull/7774))
-   Feature: auto-clean some invalid pdfs [@shamoon](https://github.com/shamoon) ([#7651](https://github.com/paperless-ngx/paperless-ngx/pull/7651))
-   Feature: page count [@s0llvan](https://github.com/s0llvan) ([#7750](https://github.com/paperless-ngx/paperless-ngx/pull/7750))
-   Fix: hidden canvas element causes scroll bug [@shamoon](https://github.com/shamoon) ([#7770](https://github.com/paperless-ngx/paperless-ngx/pull/7770))
-   Enhancement: compactify dates dropdown [@shamoon](https://github.com/shamoon) ([#7759](https://github.com/paperless-ngx/paperless-ngx/pull/7759))
-   Fix: handle overflowing dropdowns on mobile [@shamoon](https://github.com/shamoon) ([#7758](https://github.com/paperless-ngx/paperless-ngx/pull/7758))
-   Enhancement: set Django SESSION_EXPIRE_AT_BROWSER_CLOSE from PAPERLESS_ACCOUNT_SESSION_REMEMBER [@shamoon](https://github.com/shamoon) ([#7748](https://github.com/paperless-ngx/paperless-ngx/pull/7748))
-   Enhancement: allow setting session cookie age [@shamoon](https://github.com/shamoon) ([#7743](https://github.com/paperless-ngx/paperless-ngx/pull/7743))
-   Fix: chrome scrolling in >= 129 [@shamoon](https://github.com/shamoon) ([#7738](https://github.com/paperless-ngx/paperless-ngx/pull/7738))
-   Feature: copy workflows and mail rules, improve layout [@shamoon](https://github.com/shamoon) ([#7727](https://github.com/paperless-ngx/paperless-ngx/pull/7727))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7723](https://github.com/paperless-ngx/paperless-ngx/pull/7723))
</details>

## paperless-ngx 2.12.1

### Bug Fixes

-   Fix: wait to apply tag changes until other changes saved with multiple workflow actions [@shamoon](https://github.com/shamoon) ([#7711](https://github.com/paperless-ngx/paperless-ngx/pull/7711))
-   Fix: delete_pages should require ownership (not just change perms) [@shamoon](https://github.com/shamoon) ([#7714](https://github.com/paperless-ngx/paperless-ngx/pull/7714))
-   Fix: filter out shown custom fields that have been deleted from saved… [@shamoon](https://github.com/shamoon) ([#7710](https://github.com/paperless-ngx/paperless-ngx/pull/7710))
-   Fix: only filter by string or number properties for filter pipe [@shamoon](https://github.com/shamoon) ([#7699](https://github.com/paperless-ngx/paperless-ngx/pull/7699))
-   Fix: saved view permissions fixes [@shamoon](https://github.com/shamoon) ([#7672](https://github.com/paperless-ngx/paperless-ngx/pull/7672))
-   Fix: add permissions for OPTIONS requests for notes [@shamoon](https://github.com/shamoon) ([#7661](https://github.com/paperless-ngx/paperless-ngx/pull/7661))

### All App Changes

<details>
<summary>7 changes</summary>

-   Fix: wait to apply tag changes until other changes saved with multiple workflow actions [@shamoon](https://github.com/shamoon) ([#7711](https://github.com/paperless-ngx/paperless-ngx/pull/7711))
-   Fix: delete_pages should require ownership (not just change perms) [@shamoon](https://github.com/shamoon) ([#7714](https://github.com/paperless-ngx/paperless-ngx/pull/7714))
-   Enhancement: improve text contrast for selected documents in list view dark mode [@shamoon](https://github.com/shamoon) ([#7712](https://github.com/paperless-ngx/paperless-ngx/pull/7712))
-   Fix: filter out shown custom fields that have been deleted from saved… [@shamoon](https://github.com/shamoon) ([#7710](https://github.com/paperless-ngx/paperless-ngx/pull/7710))
-   Fix: only filter by string or number properties for filter pipe [@shamoon](https://github.com/shamoon) ([#7699](https://github.com/paperless-ngx/paperless-ngx/pull/7699))
-   Fix: saved view permissions fixes [@shamoon](https://github.com/shamoon) ([#7672](https://github.com/paperless-ngx/paperless-ngx/pull/7672))
-   Fix: add permissions for OPTIONS requests for notes [@shamoon](https://github.com/shamoon) ([#7661](https://github.com/paperless-ngx/paperless-ngx/pull/7661))
</details>

## paperless-ngx 2.12.0

### Features / Enhancements

-   Enhancement: re-work mail rule dialog, support multiple include patterns [@shamoon](https://github.com/shamoon) ([#7635](https://github.com/paperless-ngx/paperless-ngx/pull/7635))
-   Enhancement: add Korean language [@shamoon](https://github.com/shamoon) ([#7573](https://github.com/paperless-ngx/paperless-ngx/pull/7573))
-   Enhancement: allow multiple filename attachment exclusion patterns for a mail rule [@MelleD](https://github.com/MelleD) ([#5524](https://github.com/paperless-ngx/paperless-ngx/pull/5524))
-   Refactor: Use django-filter logic for filtering full text search queries [@yichi-yang](https://github.com/yichi-yang) ([#7507](https://github.com/paperless-ngx/paperless-ngx/pull/7507))
-   Refactor: Reduce number of SQL queries when serializing List[Document] [@yichi-yang](https://github.com/yichi-yang) ([#7505](https://github.com/paperless-ngx/paperless-ngx/pull/7505))

### Bug Fixes

-   Fix: use JSON for note audit log entries [@shamoon](https://github.com/shamoon) ([#7650](https://github.com/paperless-ngx/paperless-ngx/pull/7650))
-   Fix: Rework system check so it won't crash if tesseract is not found [@stumpylog](https://github.com/stumpylog) ([#7640](https://github.com/paperless-ngx/paperless-ngx/pull/7640))
-   Fix: correct broken pdfjs worker src after upgrade to pdfjs v4 [@shamoon](https://github.com/shamoon) ([#7626](https://github.com/paperless-ngx/paperless-ngx/pull/7626))
-   Chore: remove unused frontend dependencies [@shamoon](https://github.com/shamoon) ([#7607](https://github.com/paperless-ngx/paperless-ngx/pull/7607))
-   Fix: fix non-clickable scroll wheel in file uploads list [@shamoon](https://github.com/shamoon) ([#7591](https://github.com/paperless-ngx/paperless-ngx/pull/7591))
-   Fix: deselect file tasks select all button on dismiss [@shamoon](https://github.com/shamoon) ([#7592](https://github.com/paperless-ngx/paperless-ngx/pull/7592))
-   Fix: saved view sidebar heading not always visible [@shamoon](https://github.com/shamoon) ([#7584](https://github.com/paperless-ngx/paperless-ngx/pull/7584))
-   Fix: correct select field wrapping with long text [@shamoon](https://github.com/shamoon) ([#7572](https://github.com/paperless-ngx/paperless-ngx/pull/7572))
-   Fix: update ng-bootstrap to fix datepicker bug [@shamoon](https://github.com/shamoon) ([#7567](https://github.com/paperless-ngx/paperless-ngx/pull/7567))

### Dependencies

<details>
<summary>11 changes</summary>

-   Chore(deps): Bump cryptography from 42.0.8 to 43.0.1 [@dependabot](https://github.com/dependabot) ([#7620](https://github.com/paperless-ngx/paperless-ngx/pull/7620))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#7608](https://github.com/paperless-ngx/paperless-ngx/pull/7608))
-   Chore(deps): Bump rapidfuzz from 3.9.6 to 3.9.7 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7611](https://github.com/paperless-ngx/paperless-ngx/pull/7611))
-   Chore(deps): Bump tslib from 2.6.3 to 2.7.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7606](https://github.com/paperless-ngx/paperless-ngx/pull/7606))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.45.3 to 1.46.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.45.3 to 1.46.1 in /src-ui @dependabot) ([#7603](https://github.com/paperless-ngx/paperless-ngx/pull/7603))
-   Chore(deps-dev): Bump typescript from 5.4.5 to 5.5.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7604](https://github.com/paperless-ngx/paperless-ngx/pull/7604))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7600](https://github.com/paperless-ngx/paperless-ngx/pull/7600))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#7599](https://github.com/paperless-ngx/paperless-ngx/pull/7599))
-   Chore(deps): Bump pathvalidate from 3.2.0 to 3.2.1 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7548](https://github.com/paperless-ngx/paperless-ngx/pull/7548))
-   Chore(deps): Bump micromatch from 4.0.5 to 4.0.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#7551](https://github.com/paperless-ngx/paperless-ngx/pull/7551))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7545](https://github.com/paperless-ngx/paperless-ngx/pull/7545))
</details>

### All App Changes

<details>
<summary>27 changes</summary>

-   Chore: Update backend dependencies in bulk [@stumpylog](https://github.com/stumpylog) ([#7656](https://github.com/paperless-ngx/paperless-ngx/pull/7656))
-   Fix: Rework system check so it won't crash if tesseract is not found [@stumpylog](https://github.com/stumpylog) ([#7640](https://github.com/paperless-ngx/paperless-ngx/pull/7640))
-   Refactor: performance and storage optimization of barcode scanning [@loewexy](https://github.com/loewexy) ([#7646](https://github.com/paperless-ngx/paperless-ngx/pull/7646))
-   Fix: use JSON for note audit log entries [@shamoon](https://github.com/shamoon) ([#7650](https://github.com/paperless-ngx/paperless-ngx/pull/7650))
-   Enhancement: re-work mail rule dialog, support multiple include patterns [@shamoon](https://github.com/shamoon) ([#7635](https://github.com/paperless-ngx/paperless-ngx/pull/7635))
-   Fix: correct broken pdfjs worker src after upgrade to pdfjs v4 [@shamoon](https://github.com/shamoon) ([#7626](https://github.com/paperless-ngx/paperless-ngx/pull/7626))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#7608](https://github.com/paperless-ngx/paperless-ngx/pull/7608))
-   Chore(deps): Bump rapidfuzz from 3.9.6 to 3.9.7 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7611](https://github.com/paperless-ngx/paperless-ngx/pull/7611))
-   Chore: remove unused frontend dependencies [@shamoon](https://github.com/shamoon) ([#7607](https://github.com/paperless-ngx/paperless-ngx/pull/7607))
-   Chore(deps): Bump tslib from 2.6.3 to 2.7.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7606](https://github.com/paperless-ngx/paperless-ngx/pull/7606))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.45.3 to 1.46.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.45.3 to 1.46.1 in /src-ui @dependabot) ([#7603](https://github.com/paperless-ngx/paperless-ngx/pull/7603))
-   Chore(deps-dev): Bump typescript from 5.4.5 to 5.5.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7604](https://github.com/paperless-ngx/paperless-ngx/pull/7604))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7600](https://github.com/paperless-ngx/paperless-ngx/pull/7600))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 21 updates [@dependabot](https://github.com/dependabot) ([#7599](https://github.com/paperless-ngx/paperless-ngx/pull/7599))
-   Fix: fix non-clickable scroll wheel in file uploads list [@shamoon](https://github.com/shamoon) ([#7591](https://github.com/paperless-ngx/paperless-ngx/pull/7591))
-   Fix: deselect file tasks select all button on dismiss [@shamoon](https://github.com/shamoon) ([#7592](https://github.com/paperless-ngx/paperless-ngx/pull/7592))
-   Fix: saved view sidebar heading not always visible [@shamoon](https://github.com/shamoon) ([#7584](https://github.com/paperless-ngx/paperless-ngx/pull/7584))
-   Enhancement: add Korean language [@shamoon](https://github.com/shamoon) ([#7573](https://github.com/paperless-ngx/paperless-ngx/pull/7573))
-   Enhancement: mail message preprocessor for gpg encrypted mails [@dbankmann](https://github.com/dbankmann) ([#7456](https://github.com/paperless-ngx/paperless-ngx/pull/7456))
-   Fix: correct select field wrapping with long text [@shamoon](https://github.com/shamoon) ([#7572](https://github.com/paperless-ngx/paperless-ngx/pull/7572))
-   Fix: update ng-bootstrap to fix datepicker bug [@shamoon](https://github.com/shamoon) ([#7567](https://github.com/paperless-ngx/paperless-ngx/pull/7567))
-   Enhancement: allow multiple filename attachment exclusion patterns for a mail rule [@MelleD](https://github.com/MelleD) ([#5524](https://github.com/paperless-ngx/paperless-ngx/pull/5524))
-   Chore(deps): Bump pathvalidate from 3.2.0 to 3.2.1 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7548](https://github.com/paperless-ngx/paperless-ngx/pull/7548))
-   Chore(deps): Bump micromatch from 4.0.5 to 4.0.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#7551](https://github.com/paperless-ngx/paperless-ngx/pull/7551))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7545](https://github.com/paperless-ngx/paperless-ngx/pull/7545))
-   Refactor: Use django-filter logic for filtering full text search queries [@yichi-yang](https://github.com/yichi-yang) ([#7507](https://github.com/paperless-ngx/paperless-ngx/pull/7507))
-   Refactor: Reduce number of SQL queries when serializing List[Document] [@yichi-yang](https://github.com/yichi-yang) ([#7505](https://github.com/paperless-ngx/paperless-ngx/pull/7505))
</details>

## paperless-ngx 2.11.6

### Bug Fixes

-   Fix: fix nltk tokenizer breaking change [@shamoon](https://github.com/shamoon) ([#7522](https://github.com/paperless-ngx/paperless-ngx/pull/7522))

### All App Changes

<details>
<summary>1 change</summary>

-   Fix: fix nltk tokenizer breaking change [@shamoon](https://github.com/shamoon) ([#7522](https://github.com/paperless-ngx/paperless-ngx/pull/7522))
</details>

## paperless-ngx 2.11.5

### Bug Fixes

-   Fix: use JSON for update archive file auditlog entries [@shamoon](https://github.com/shamoon) ([#7503](https://github.com/paperless-ngx/paperless-ngx/pull/7503))
-   Fix: respect deskew / rotate pages from AppConfig if set [@shamoon](https://github.com/shamoon) ([#7501](https://github.com/paperless-ngx/paperless-ngx/pull/7501))

### Dependencies

<details>
<summary>5 changes</summary>

-   Chore(deps): Bump the small-changes group across 1 directory with 6 updates [@dependabot](https://github.com/dependabot) ([#7502](https://github.com/paperless-ngx/paperless-ngx/pull/7502))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7497](https://github.com/paperless-ngx/paperless-ngx/pull/7497))
-   Chore(deps-dev): Bump axios from 1.6.7 to 1.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7472](https://github.com/paperless-ngx/paperless-ngx/pull/7472))
-   Chore(deps-dev): Bump ruff from 0.5.6 to 0.5.7 in the development group [@dependabot](https://github.com/dependabot) ([#7457](https://github.com/paperless-ngx/paperless-ngx/pull/7457))
-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#7460](https://github.com/paperless-ngx/paperless-ngx/pull/7460))
</details>

### All App Changes

<details>
<summary>7 changes</summary>

-   Fix: use JSON for update archive file auditlog entries [@shamoon](https://github.com/shamoon) ([#7503](https://github.com/paperless-ngx/paperless-ngx/pull/7503))
-   Chore(deps): Bump the small-changes group across 1 directory with 6 updates [@dependabot](https://github.com/dependabot) ([#7502](https://github.com/paperless-ngx/paperless-ngx/pull/7502))
-   Fix: respect deskew / rotate pages from AppConfig if set [@shamoon](https://github.com/shamoon) ([#7501](https://github.com/paperless-ngx/paperless-ngx/pull/7501))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7497](https://github.com/paperless-ngx/paperless-ngx/pull/7497))
-   Chore(deps-dev): Bump axios from 1.6.7 to 1.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#7472](https://github.com/paperless-ngx/paperless-ngx/pull/7472))
-   Chore(deps-dev): Bump ruff from 0.5.6 to 0.5.7 in the development group [@dependabot](https://github.com/dependabot) ([#7457](https://github.com/paperless-ngx/paperless-ngx/pull/7457))
-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#7460](https://github.com/paperless-ngx/paperless-ngx/pull/7460))
</details>

## paperless-ngx 2.11.4

### Bug Fixes

-   Fix: initial upload message not being dismissed [@shamoon](https://github.com/shamoon) ([#7438](https://github.com/paperless-ngx/paperless-ngx/pull/7438))

### All App Changes

-   Fix: initial upload message not being dismissed [@shamoon](https://github.com/shamoon) ([#7438](https://github.com/paperless-ngx/paperless-ngx/pull/7438))

## paperless-ngx 2.11.3

### Features

-   Enhancement: optimize tasks / stats reload [@shamoon](https://github.com/shamoon) ([#7402](https://github.com/paperless-ngx/paperless-ngx/pull/7402))
-   Enhancement: allow specifying default currency for Monetary custom field [@shamoon](https://github.com/shamoon) ([#7381](https://github.com/paperless-ngx/paperless-ngx/pull/7381))
-   Enhancement: specify when pre-check fails for documents in trash [@shamoon](https://github.com/shamoon) ([#7355](https://github.com/paperless-ngx/paperless-ngx/pull/7355))

### Bug Fixes

-   Fix: clear selection after reload for management lists [@shamoon](https://github.com/shamoon) ([#7421](https://github.com/paperless-ngx/paperless-ngx/pull/7421))
-   Fix: disable inline create buttons if insufficient permissions [@shamoon](https://github.com/shamoon) ([#7401](https://github.com/paperless-ngx/paperless-ngx/pull/7401))
-   Fix: use entire document for dropzone [@shamoon](https://github.com/shamoon) ([#7342](https://github.com/paperless-ngx/paperless-ngx/pull/7342))

### Maintenance

-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.7.0 to 0.8.0 in the actions group [@dependabot](https://github.com/dependabot) ([#7371](https://github.com/paperless-ngx/paperless-ngx/pull/7371))

### Dependencies

<details>
<summary>11 changes</summary>

-   Chore(deps): Bump django from 4.2.14 to 4.2.15 [@dependabot](https://github.com/dependabot) ([#7412](https://github.com/paperless-ngx/paperless-ngx/pull/7412))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#7394](https://github.com/paperless-ngx/paperless-ngx/pull/7394))
-   Chore(deps): Bump the small-changes group with 5 updates [@dependabot](https://github.com/dependabot) ([#7397](https://github.com/paperless-ngx/paperless-ngx/pull/7397))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.42.1 to 1.45.3 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.42.1 to 1.45.3 in /src-ui @dependabot) ([#7367](https://github.com/paperless-ngx/paperless-ngx/pull/7367))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.12.2 to 22.0.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.12.2 to 22.0.2 in /src-ui @dependabot) ([#7366](https://github.com/paperless-ngx/paperless-ngx/pull/7366))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7365](https://github.com/paperless-ngx/paperless-ngx/pull/7365))
-   Chore(deps): Bump uuid from 9.0.1 to 10.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7370](https://github.com/paperless-ngx/paperless-ngx/pull/7370))
-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.7.0 to 0.8.0 in the actions group [@dependabot](https://github.com/dependabot) ([#7371](https://github.com/paperless-ngx/paperless-ngx/pull/7371))
-   Chore(deps): Bump zone.js from 0.14.4 to 0.14.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#7368](https://github.com/paperless-ngx/paperless-ngx/pull/7368))
-   Chore(deps-dev): Bump jest-preset-angular from 14.1.1 to 14.2.2 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#7364](https://github.com/paperless-ngx/paperless-ngx/pull/7364))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 20 updates [@dependabot](https://github.com/dependabot) ([#7363](https://github.com/paperless-ngx/paperless-ngx/pull/7363))
</details>

### All App Changes

<details>
<summary>15 changes</summary>

-   Fix: clear selection after reload for management lists [@shamoon](https://github.com/shamoon) ([#7421](https://github.com/paperless-ngx/paperless-ngx/pull/7421))
-   Enhancement: optimize tasks / stats reload [@shamoon](https://github.com/shamoon) ([#7402](https://github.com/paperless-ngx/paperless-ngx/pull/7402))
-   Enhancement: allow specifying default currency for Monetary custom field [@shamoon](https://github.com/shamoon) ([#7381](https://github.com/paperless-ngx/paperless-ngx/pull/7381))
-   Enhancement: specify when pre-check fails for documents in trash [@shamoon](https://github.com/shamoon) ([#7355](https://github.com/paperless-ngx/paperless-ngx/pull/7355))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#7394](https://github.com/paperless-ngx/paperless-ngx/pull/7394))
-   Fix: disable inline create buttons if insufficient permissions [@shamoon](https://github.com/shamoon) ([#7401](https://github.com/paperless-ngx/paperless-ngx/pull/7401))
-   Chore(deps): Bump the small-changes group with 5 updates [@dependabot](https://github.com/dependabot) ([#7397](https://github.com/paperless-ngx/paperless-ngx/pull/7397))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.42.1 to 1.45.3 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.42.1 to 1.45.3 in /src-ui @dependabot) ([#7367](https://github.com/paperless-ngx/paperless-ngx/pull/7367))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.12.2 to 22.0.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.12.2 to 22.0.2 in /src-ui @dependabot) ([#7366](https://github.com/paperless-ngx/paperless-ngx/pull/7366))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#7365](https://github.com/paperless-ngx/paperless-ngx/pull/7365))
-   Chore(deps): Bump uuid from 9.0.1 to 10.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#7370](https://github.com/paperless-ngx/paperless-ngx/pull/7370))
-   Chore(deps): Bump zone.js from 0.14.4 to 0.14.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#7368](https://github.com/paperless-ngx/paperless-ngx/pull/7368))
-   Chore(deps-dev): Bump jest-preset-angular from 14.1.1 to 14.2.2 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#7364](https://github.com/paperless-ngx/paperless-ngx/pull/7364))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 20 updates [@dependabot](https://github.com/dependabot) ([#7363](https://github.com/paperless-ngx/paperless-ngx/pull/7363))
-   Fix: use entire document for dropzone [@shamoon](https://github.com/shamoon) ([#7342](https://github.com/paperless-ngx/paperless-ngx/pull/7342))
</details>

## paperless-ngx 2.11.2

### Changes

-   Change: more clearly handle init permissions error [@shamoon](https://github.com/shamoon) ([#7334](https://github.com/paperless-ngx/paperless-ngx/pull/7334))
-   Chore: add permissions info link from webUI [@shamoon](https://github.com/shamoon) ([#7310](https://github.com/paperless-ngx/paperless-ngx/pull/7310))
-   Fix: increase search input text contrast with light custom theme colors [@JayBkr](https://github.com/JayBkr) ([#7303](https://github.com/paperless-ngx/paperless-ngx/pull/7303))

### Dependencies

-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7296](https://github.com/paperless-ngx/paperless-ngx/pull/7296))
-   Chore(deps): Bump tika-client from 0.5.0 to 0.6.0 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7297](https://github.com/paperless-ngx/paperless-ngx/pull/7297))

### All App Changes

<details>
<summary>5 changes</summary>

-   Change: more clearly handle init permissions error [@shamoon](https://github.com/shamoon) ([#7334](https://github.com/paperless-ngx/paperless-ngx/pull/7334))
-   Chore: add permissions info link from webUI [@shamoon](https://github.com/shamoon) ([#7310](https://github.com/paperless-ngx/paperless-ngx/pull/7310))
-   Fix: increase search input text contrast with light custom theme colors [@JayBkr](https://github.com/JayBkr) ([#7303](https://github.com/paperless-ngx/paperless-ngx/pull/7303))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7296](https://github.com/paperless-ngx/paperless-ngx/pull/7296))
-   Chore(deps): Bump tika-client from 0.5.0 to 0.6.0 in the small-changes group [@dependabot](https://github.com/dependabot) ([#7297](https://github.com/paperless-ngx/paperless-ngx/pull/7297))
</details>

## paperless-ngx 2.11.1

### Features

-   Enhancement: include owner username in post-consumption variables [@Freddy-0](https://github.com/Freddy-0) ([#7270](https://github.com/paperless-ngx/paperless-ngx/pull/7270))

### Bug Fixes

-   Fix: support multiple inbox tags from stats widget [@shamoon](https://github.com/shamoon) ([#7281](https://github.com/paperless-ngx/paperless-ngx/pull/7281))
-   Fix: Removes Turkish from the NLTK languages [@stumpylog](https://github.com/stumpylog) ([#7246](https://github.com/paperless-ngx/paperless-ngx/pull/7246))
-   Fix: include trashed docs in existing doc check [@shamoon](https://github.com/shamoon) ([#7229](https://github.com/paperless-ngx/paperless-ngx/pull/7229))

### Dependencies

-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7261](https://github.com/paperless-ngx/paperless-ngx/pull/7261))
-   Chore(deps): Bump the small-changes group across 1 directory with 2 updates [@dependabot](https://github.com/dependabot) ([#7266](https://github.com/paperless-ngx/paperless-ngx/pull/7266))

### All App Changes

<details>
<summary>7 changes</summary>

-   Fix: support multiple inbox tags from stats widget [@shamoon](https://github.com/shamoon) ([#7281](https://github.com/paperless-ngx/paperless-ngx/pull/7281))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7261](https://github.com/paperless-ngx/paperless-ngx/pull/7261))
-   Chore(deps): Bump the small-changes group across 1 directory with 2 updates [@dependabot](https://github.com/dependabot) ([#7266](https://github.com/paperless-ngx/paperless-ngx/pull/7266))
-   Enhancement: include owner username in post-consumption variables [@Freddy-0](https://github.com/Freddy-0) ([#7270](https://github.com/paperless-ngx/paperless-ngx/pull/7270))
-   Chore: Squash older automatic migrations [@stumpylog](https://github.com/stumpylog) ([#7267](https://github.com/paperless-ngx/paperless-ngx/pull/7267))
-   Fix: Removes Turkish from the NLTK languages [@stumpylog](https://github.com/stumpylog) ([#7246](https://github.com/paperless-ngx/paperless-ngx/pull/7246))
-   Fix: include trashed docs in existing doc check [@shamoon](https://github.com/shamoon) ([#7229](https://github.com/paperless-ngx/paperless-ngx/pull/7229))
</details>

## paperless-ngx 2.11.0

### Breaking Changes

-   Feature: Upgrade Gotenberg to v8 [@stumpylog](https://github.com/stumpylog) ([#7094](https://github.com/paperless-ngx/paperless-ngx/pull/7094))

### Features

-   Enhancement: disable add split button when appropriate [@shamoon](https://github.com/shamoon) ([#7215](https://github.com/paperless-ngx/paperless-ngx/pull/7215))
-   Enhancement: wrapping of saved view fields d-n-d UI [@shamoon](https://github.com/shamoon) ([#7216](https://github.com/paperless-ngx/paperless-ngx/pull/7216))
-   Enhancement: support custom field icontains filter for select type [@shamoon](https://github.com/shamoon) ([#7199](https://github.com/paperless-ngx/paperless-ngx/pull/7199))
-   Feature: select custom field type [@shamoon](https://github.com/shamoon) ([#7167](https://github.com/paperless-ngx/paperless-ngx/pull/7167))
-   Feature: automatic sso redirect [@shamoon](https://github.com/shamoon) ([#7168](https://github.com/paperless-ngx/paperless-ngx/pull/7168))
-   Enhancement: show more columns in mail frontend admin [@shamoon](https://github.com/shamoon) ([#7158](https://github.com/paperless-ngx/paperless-ngx/pull/7158))
-   Enhancement: use request user as owner of split / merge docs [@shamoon](https://github.com/shamoon) ([#7112](https://github.com/paperless-ngx/paperless-ngx/pull/7112))
-   Enhancement: improve date parsing with accented characters [@fdubuy](https://github.com/fdubuy) ([#7100](https://github.com/paperless-ngx/paperless-ngx/pull/7100))
-   Feature: improve history display of object names etc [@shamoon](https://github.com/shamoon) ([#7102](https://github.com/paperless-ngx/paperless-ngx/pull/7102))
-   Feature: Upgrade Gotenberg to v8 [@stumpylog](https://github.com/stumpylog) ([#7094](https://github.com/paperless-ngx/paperless-ngx/pull/7094))

### Bug Fixes

-   Fix: include documents in trash for existing asn check [@shamoon](https://github.com/shamoon) ([#7189](https://github.com/paperless-ngx/paperless-ngx/pull/7189))
-   Fix: include documents in trash in sanity check [@shamoon](https://github.com/shamoon) ([#7133](https://github.com/paperless-ngx/paperless-ngx/pull/7133))
-   Fix: handle errors for trash actions and only show documents user can restore or delete [@shamoon](https://github.com/shamoon) ([#7119](https://github.com/paperless-ngx/paperless-ngx/pull/7119))
-   Fix: dont include documents in trash in counts [@shamoon](https://github.com/shamoon) ([#7111](https://github.com/paperless-ngx/paperless-ngx/pull/7111))
-   Fix: use temp dir for split / merge [@shamoon](https://github.com/shamoon) ([#7105](https://github.com/paperless-ngx/paperless-ngx/pull/7105))

### Maintenance

-   Chore: upgrade to DRF 3.15 [@shamoon](https://github.com/shamoon) ([#7134](https://github.com/paperless-ngx/paperless-ngx/pull/7134))
-   Chore(deps): Bump docker/build-push-action from 5 to 6 in the actions group [@dependabot](https://github.com/dependabot) ([#7125](https://github.com/paperless-ngx/paperless-ngx/pull/7125))
-   Chore: Ignores DRF 3.15.2 [@stumpylog](https://github.com/stumpylog) ([#7122](https://github.com/paperless-ngx/paperless-ngx/pull/7122))
-   Chore: show docker tag in UI for ci test builds [@shamoon](https://github.com/shamoon) ([#7083](https://github.com/paperless-ngx/paperless-ngx/pull/7083))

### Dependencies

<details>
<summary>11 changes</summary>

-   Chore: Bulk backend updates [@stumpylog](https://github.com/stumpylog) ([#7209](https://github.com/paperless-ngx/paperless-ngx/pull/7209))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 14 updates [@dependabot](https://github.com/dependabot) ([#7200](https://github.com/paperless-ngx/paperless-ngx/pull/7200))
-   Chore(deps): Bump certifi from 2024.6.2 to 2024.7.4 [@dependabot](https://github.com/dependabot) ([#7166](https://github.com/paperless-ngx/paperless-ngx/pull/7166))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 6 updates [@dependabot](https://github.com/dependabot) ([#7148](https://github.com/paperless-ngx/paperless-ngx/pull/7148))
-   Chore(deps): Bump django-multiselectfield from 0.1.12 to 0.1.13 in the django group [@dependabot](https://github.com/dependabot) ([#7147](https://github.com/paperless-ngx/paperless-ngx/pull/7147))
-   Chore(deps): Bump docker/build-push-action from 5 to 6 in the actions group [@dependabot](https://github.com/dependabot) ([#7125](https://github.com/paperless-ngx/paperless-ngx/pull/7125))
-   Chore(deps): Bump the small-changes group across 1 directory with 4 updates [@dependabot](https://github.com/dependabot) ([#7128](https://github.com/paperless-ngx/paperless-ngx/pull/7128))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#7126](https://github.com/paperless-ngx/paperless-ngx/pull/7126))
-   Chore(deps-dev): Bump ruff from 0.4.9 to 0.5.0 in the development group across 1 directory [@dependabot](https://github.com/dependabot) ([#7120](https://github.com/paperless-ngx/paperless-ngx/pull/7120))
-   Chore(deps-dev): Bump ws from 8.17.0 to 8.17.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#7114](https://github.com/paperless-ngx/paperless-ngx/pull/7114))
-   Chore: update to Angular v18 [@shamoon](https://github.com/shamoon) ([#7106](https://github.com/paperless-ngx/paperless-ngx/pull/7106))
</details>

### All App Changes

<details>
<summary>25 changes</summary>

-   Enhancement: disable add split button when appropriate [@shamoon](https://github.com/shamoon) ([#7215](https://github.com/paperless-ngx/paperless-ngx/pull/7215))
-   Enhancement: wrapping of saved view fields d-n-d UI [@shamoon](https://github.com/shamoon) ([#7216](https://github.com/paperless-ngx/paperless-ngx/pull/7216))
-   Chore: Bulk backend updates [@stumpylog](https://github.com/stumpylog) ([#7209](https://github.com/paperless-ngx/paperless-ngx/pull/7209))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 14 updates [@dependabot](https://github.com/dependabot) ([#7200](https://github.com/paperless-ngx/paperless-ngx/pull/7200))
-   Enhancement: support custom field icontains filter for select type [@shamoon](https://github.com/shamoon) ([#7199](https://github.com/paperless-ngx/paperless-ngx/pull/7199))
-   Chore: upgrade to DRF 3.15 [@shamoon](https://github.com/shamoon) ([#7134](https://github.com/paperless-ngx/paperless-ngx/pull/7134))
-   Feature: select custom field type [@shamoon](https://github.com/shamoon) ([#7167](https://github.com/paperless-ngx/paperless-ngx/pull/7167))
-   Feature: automatic sso redirect [@shamoon](https://github.com/shamoon) ([#7168](https://github.com/paperless-ngx/paperless-ngx/pull/7168))
-   Fix: include documents in trash for existing asn check [@shamoon](https://github.com/shamoon) ([#7189](https://github.com/paperless-ngx/paperless-ngx/pull/7189))
-   Chore: Initial conversion to pytest fixtures [@stumpylog](https://github.com/stumpylog) ([#7110](https://github.com/paperless-ngx/paperless-ngx/pull/7110))
-   Enhancement: show more columns in mail frontend admin [@shamoon](https://github.com/shamoon) ([#7158](https://github.com/paperless-ngx/paperless-ngx/pull/7158))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 6 updates [@dependabot](https://github.com/dependabot) ([#7148](https://github.com/paperless-ngx/paperless-ngx/pull/7148))
-   Chore(deps): Bump django-multiselectfield from 0.1.12 to 0.1.13 in the django group [@dependabot](https://github.com/dependabot) ([#7147](https://github.com/paperless-ngx/paperless-ngx/pull/7147))
-   Fix: include documents in trash in sanity check [@shamoon](https://github.com/shamoon) ([#7133](https://github.com/paperless-ngx/paperless-ngx/pull/7133))
-   Chore(deps): Bump the small-changes group across 1 directory with 4 updates [@dependabot](https://github.com/dependabot) ([#7128](https://github.com/paperless-ngx/paperless-ngx/pull/7128))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#7126](https://github.com/paperless-ngx/paperless-ngx/pull/7126))
-   Enhancement: use request user as owner of split / merge docs [@shamoon](https://github.com/shamoon) ([#7112](https://github.com/paperless-ngx/paperless-ngx/pull/7112))
-   Fix: handle errors for trash actions and only show documents user can restore or delete [@shamoon](https://github.com/shamoon) ([#7119](https://github.com/paperless-ngx/paperless-ngx/pull/7119))
-   Chore(deps-dev): Bump ruff from 0.4.9 to 0.5.0 in the development group across 1 directory [@dependabot](https://github.com/dependabot) ([#7120](https://github.com/paperless-ngx/paperless-ngx/pull/7120))
-   Chore(deps-dev): Bump ws from 8.17.0 to 8.17.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#7114](https://github.com/paperless-ngx/paperless-ngx/pull/7114))
-   Chore: update to Angular v18 [@shamoon](https://github.com/shamoon) ([#7106](https://github.com/paperless-ngx/paperless-ngx/pull/7106))
-   Enhancement: improve date parsing with accented characters [@fdubuy](https://github.com/fdubuy) ([#7100](https://github.com/paperless-ngx/paperless-ngx/pull/7100))
-   Feature: improve history display of object names etc [@shamoon](https://github.com/shamoon) ([#7102](https://github.com/paperless-ngx/paperless-ngx/pull/7102))
-   Fix: dont include documents in trash in counts [@shamoon](https://github.com/shamoon) ([#7111](https://github.com/paperless-ngx/paperless-ngx/pull/7111))
-   Fix: use temp dir for split / merge [@shamoon](https://github.com/shamoon) ([#7105](https://github.com/paperless-ngx/paperless-ngx/pull/7105))
</details>

## paperless-ngx 2.10.2

### Bug Fixes

-   Fix: always update document modified property on bulk edit operations [@shamoon](https://github.com/shamoon) ([#7079](https://github.com/paperless-ngx/paperless-ngx/pull/7079))
-   Fix: correct frontend retrieval of trash delay setting [@shamoon](https://github.com/shamoon) ([#7067](https://github.com/paperless-ngx/paperless-ngx/pull/7067))
-   Fix: index fresh document data after update archive file [@shamoon](https://github.com/shamoon) ([#7057](https://github.com/paperless-ngx/paperless-ngx/pull/7057))
-   Fix: Safari browser PDF viewer not loading in 2.10.x [@shamoon](https://github.com/shamoon) ([#7056](https://github.com/paperless-ngx/paperless-ngx/pull/7056))
-   Fix: Prefer the exporter metadata JSON file over the version JSON file [@stumpylog](https://github.com/stumpylog) ([#7048](https://github.com/paperless-ngx/paperless-ngx/pull/7048))

### All App Changes

<details>
<summary>5 changes</summary>

-   Fix: always update document modified property on bulk edit operations [@shamoon](https://github.com/shamoon) ([#7079](https://github.com/paperless-ngx/paperless-ngx/pull/7079))
-   Fix: correct frontend retrieval of trash delay setting [@shamoon](https://github.com/shamoon) ([#7067](https://github.com/paperless-ngx/paperless-ngx/pull/7067))
-   Fix: index fresh document data after update archive file [@shamoon](https://github.com/shamoon) ([#7057](https://github.com/paperless-ngx/paperless-ngx/pull/7057))
-   Fix: Safari browser PDF viewer not loading in 2.10.x [@shamoon](https://github.com/shamoon) ([#7056](https://github.com/paperless-ngx/paperless-ngx/pull/7056))
-   Fix: Prefer the exporter metadata JSON file over the version JSON file [@stumpylog](https://github.com/stumpylog) ([#7048](https://github.com/paperless-ngx/paperless-ngx/pull/7048))
</details>

## paperless-ngx 2.10.1

### Bug Fixes

-   Fix: dont require admin perms to view trash on frontend @shamoon ([#7028](https://github.com/paperless-ngx/paperless-ngx/pull/7028))

## paperless-ngx 2.10.0

### Features

-   Feature: documents trash aka soft delete [@shamoon](https://github.com/shamoon) ([#6944](https://github.com/paperless-ngx/paperless-ngx/pull/6944))
-   Enhancement: better boolean custom field display [@shamoon](https://github.com/shamoon) ([#7001](https://github.com/paperless-ngx/paperless-ngx/pull/7001))
-   Feature: Allow encrypting sensitive fields in export [@stumpylog](https://github.com/stumpylog) ([#6927](https://github.com/paperless-ngx/paperless-ngx/pull/6927))
-   Enhancement: allow consumption of odg files [@daniel-boehme](https://github.com/daniel-boehme) ([#6940](https://github.com/paperless-ngx/paperless-ngx/pull/6940))

### Bug Fixes

-   Fix: Document history could include extra fields [@stumpylog](https://github.com/stumpylog) ([#6989](https://github.com/paperless-ngx/paperless-ngx/pull/6989))
-   Fix: use local pdf worker js [@shamoon](https://github.com/shamoon) ([#6990](https://github.com/paperless-ngx/paperless-ngx/pull/6990))
-   Fix: Revert masking the content field from auditlog [@tribut](https://github.com/tribut) ([#6981](https://github.com/paperless-ngx/paperless-ngx/pull/6981))
-   Fix: respect model permissions for tasks API endpoint [@shamoon](https://github.com/shamoon) ([#6958](https://github.com/paperless-ngx/paperless-ngx/pull/6958))
-   Fix: Make the logging of an email message to be something useful [@stumpylog](https://github.com/stumpylog) ([#6901](https://github.com/paperless-ngx/paperless-ngx/pull/6901))

### Documentation

-   Documentation: Corrections and clarifications for Python support [@stumpylog](https://github.com/stumpylog) ([#6995](https://github.com/paperless-ngx/paperless-ngx/pull/6995))

### Maintenance

-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.6.0 to 0.7.0 in the actions group [@dependabot](https://github.com/dependabot) ([#6968](https://github.com/paperless-ngx/paperless-ngx/pull/6968))
-   Chore: Configures dependabot to ignore djangorestframework [@stumpylog](https://github.com/stumpylog) ([#6967](https://github.com/paperless-ngx/paperless-ngx/pull/6967))

### Dependencies

<details>
<summary>10 changes</summary>

-   Chore(deps): Bump pipenv from 2023.12.1 to 2024.0.1 [@stumpylog](https://github.com/stumpylog) ([#7019](https://github.com/paperless-ngx/paperless-ngx/pull/7019))
-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#7013](https://github.com/paperless-ngx/paperless-ngx/pull/7013))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7012](https://github.com/paperless-ngx/paperless-ngx/pull/7012))
-   Chore(deps-dev): Bump ws from 8.15.1 to 8.17.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#7015](https://github.com/paperless-ngx/paperless-ngx/pull/7015))
-   Chore(deps): Bump urllib3 from 2.2.1 to 2.2.2 [@dependabot](https://github.com/dependabot) ([#7014](https://github.com/paperless-ngx/paperless-ngx/pull/7014))
-   Chore: update packages used by mail parser html template [@shamoon](https://github.com/shamoon) ([#6970](https://github.com/paperless-ngx/paperless-ngx/pull/6970))
-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.6.0 to 0.7.0 in the actions group [@dependabot](https://github.com/dependabot) ([#6968](https://github.com/paperless-ngx/paperless-ngx/pull/6968))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#6953](https://github.com/paperless-ngx/paperless-ngx/pull/6953))
-   Chore: Updates to latest Trixie version of Ghostscript 10.03.1 [@stumpylog](https://github.com/stumpylog) ([#6956](https://github.com/paperless-ngx/paperless-ngx/pull/6956))
-   Chore(deps): Bump tornado from 6.4 to 6.4.1 [@dependabot](https://github.com/dependabot) ([#6930](https://github.com/paperless-ngx/paperless-ngx/pull/6930))
</details>

### All App Changes

<details>
<summary>17 changes</summary>

-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#7013](https://github.com/paperless-ngx/paperless-ngx/pull/7013))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#7012](https://github.com/paperless-ngx/paperless-ngx/pull/7012))
-   Chore(deps-dev): Bump ws from 8.15.1 to 8.17.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#7015](https://github.com/paperless-ngx/paperless-ngx/pull/7015))
-   Feature: documents trash aka soft delete [@shamoon](https://github.com/shamoon) ([#6944](https://github.com/paperless-ngx/paperless-ngx/pull/6944))
-   Enhancement: better boolean custom field display [@shamoon](https://github.com/shamoon) ([#7001](https://github.com/paperless-ngx/paperless-ngx/pull/7001))
-   Fix: default order of documents gets lost in QuerySet pipeline [@madduck](https://github.com/madduck) ([#6982](https://github.com/paperless-ngx/paperless-ngx/pull/6982))
-   Fix: Document history could include extra fields [@stumpylog](https://github.com/stumpylog) ([#6989](https://github.com/paperless-ngx/paperless-ngx/pull/6989))
-   Fix: use local pdf worker js [@shamoon](https://github.com/shamoon) ([#6990](https://github.com/paperless-ngx/paperless-ngx/pull/6990))
-   Fix: Revert masking the content field from auditlog [@tribut](https://github.com/tribut) ([#6981](https://github.com/paperless-ngx/paperless-ngx/pull/6981))
-   Chore: update packages used by mail parser html template [@shamoon](https://github.com/shamoon) ([#6970](https://github.com/paperless-ngx/paperless-ngx/pull/6970))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#6953](https://github.com/paperless-ngx/paperless-ngx/pull/6953))
-   Fix: respect model permissions for tasks API endpoint [@shamoon](https://github.com/shamoon) ([#6958](https://github.com/paperless-ngx/paperless-ngx/pull/6958))
-   Feature: Allow encrypting sensitive fields in export [@stumpylog](https://github.com/stumpylog) ([#6927](https://github.com/paperless-ngx/paperless-ngx/pull/6927))
-   Enhancement: allow consumption of odg files [@daniel-boehme](https://github.com/daniel-boehme) ([#6940](https://github.com/paperless-ngx/paperless-ngx/pull/6940))
-   Enhancement: use note model permissions for notes [@shamoon](https://github.com/shamoon) ([#6913](https://github.com/paperless-ngx/paperless-ngx/pull/6913))
-   Chore: Resolves test issues with Python 3.12 [@stumpylog](https://github.com/stumpylog) ([#6902](https://github.com/paperless-ngx/paperless-ngx/pull/6902))
-   Fix: Make the logging of an email message to be something useful [@stumpylog](https://github.com/stumpylog) ([#6901](https://github.com/paperless-ngx/paperless-ngx/pull/6901))
</details>

## paperless-ngx 2.9.0

### Features

-   Feature: Allow a data only export/import cycle [@stumpylog](https://github.com/stumpylog) ([#6871](https://github.com/paperless-ngx/paperless-ngx/pull/6871))
-   Change: rename 'redo OCR' to 'reprocess' to clarify behavior [@shamoon](https://github.com/shamoon) ([#6866](https://github.com/paperless-ngx/paperless-ngx/pull/6866))
-   Enhancement: Support custom path for the classification file [@lino-b](https://github.com/lino-b) ([#6858](https://github.com/paperless-ngx/paperless-ngx/pull/6858))
-   Enhancement: default to title/content search, allow choosing full search link from global search [@shamoon](https://github.com/shamoon) ([#6805](https://github.com/paperless-ngx/paperless-ngx/pull/6805))
-   Enhancement: only include correspondent 'last_correspondence' if requested [@shamoon](https://github.com/shamoon) ([#6792](https://github.com/paperless-ngx/paperless-ngx/pull/6792))
-   Enhancement: delete pages PDF action [@shamoon](https://github.com/shamoon) ([#6772](https://github.com/paperless-ngx/paperless-ngx/pull/6772))
-   Enhancement: support custom logo / title on login page [@shamoon](https://github.com/shamoon) ([#6775](https://github.com/paperless-ngx/paperless-ngx/pull/6775))

### Bug Fixes

-   Fix: including ordering param for id\_\_in retrievals [@shamoon](https://github.com/shamoon) ([#6875](https://github.com/paperless-ngx/paperless-ngx/pull/6875))
-   Fix: Don't allow the workflow save to override other process updates [@stumpylog](https://github.com/stumpylog) ([#6849](https://github.com/paperless-ngx/paperless-ngx/pull/6849))
-   Fix: consistently use created_date for doc display [@shamoon](https://github.com/shamoon) ([#6758](https://github.com/paperless-ngx/paperless-ngx/pull/6758))

### Maintenance

-   Chore: Change the code formatter to Ruff [@stumpylog](https://github.com/stumpylog) ([#6756](https://github.com/paperless-ngx/paperless-ngx/pull/6756))
-   Chore: Backend updates [@stumpylog](https://github.com/stumpylog) ([#6755](https://github.com/paperless-ngx/paperless-ngx/pull/6755))
-   Chore(deps): Bump crowdin/github-action from 1 to 2 in the actions group [@dependabot](https://github.com/dependabot) ([#6881](https://github.com/paperless-ngx/paperless-ngx/pull/6881))

### Dependencies

<details>
<summary>12 changes</summary>

-   Chore(deps-dev): Bump jest-preset-angular from 14.0.4 to 14.1.0 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#6879](https://github.com/paperless-ngx/paperless-ngx/pull/6879))
-   Chore: Backend dependencies update [@stumpylog](https://github.com/stumpylog) ([#6892](https://github.com/paperless-ngx/paperless-ngx/pull/6892))
-   Chore(deps): Bump crowdin/github-action from 1 to 2 in the actions group [@dependabot](https://github.com/dependabot) ([#6881](https://github.com/paperless-ngx/paperless-ngx/pull/6881))
-   Chore: Updates Ghostscript to 10.03.1 [@stumpylog](https://github.com/stumpylog) ([#6854](https://github.com/paperless-ngx/paperless-ngx/pull/6854))
-   Chore(deps-dev): Bump the development group across 1 directory with 2 updates [@dependabot](https://github.com/dependabot) ([#6851](https://github.com/paperless-ngx/paperless-ngx/pull/6851))
-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#6843](https://github.com/paperless-ngx/paperless-ngx/pull/6843))
-   Chore(deps): Use psycopg as recommended [@stumpylog](https://github.com/stumpylog) ([#6811](https://github.com/paperless-ngx/paperless-ngx/pull/6811))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6793](https://github.com/paperless-ngx/paperless-ngx/pull/6793))
-   Chore(deps): Bump requests from 2.31.0 to 2.32.0 [@dependabot](https://github.com/dependabot) ([#6795](https://github.com/paperless-ngx/paperless-ngx/pull/6795))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#6761](https://github.com/paperless-ngx/paperless-ngx/pull/6761))
-   Chore: Backend updates [@stumpylog](https://github.com/stumpylog) ([#6755](https://github.com/paperless-ngx/paperless-ngx/pull/6755))
-   Chore: revert pngx pdf viewer to third party package [@shamoon](https://github.com/shamoon) ([#6741](https://github.com/paperless-ngx/paperless-ngx/pull/6741))
</details>

### All App Changes

<details>
<summary>19 changes</summary>

-   Chore(deps-dev): Bump jest-preset-angular from 14.0.4 to 14.1.0 in /src-ui in the frontend-jest-dependencies group [@dependabot](https://github.com/dependabot) ([#6879](https://github.com/paperless-ngx/paperless-ngx/pull/6879))
-   Fix: including ordering param for id\_\_in retrievals [@shamoon](https://github.com/shamoon) ([#6875](https://github.com/paperless-ngx/paperless-ngx/pull/6875))
-   Feature: Allow a data only export/import cycle [@stumpylog](https://github.com/stumpylog) ([#6871](https://github.com/paperless-ngx/paperless-ngx/pull/6871))
-   Change: rename 'redo OCR' to 'reprocess' to clarify behavior [@shamoon](https://github.com/shamoon) ([#6866](https://github.com/paperless-ngx/paperless-ngx/pull/6866))
-   Enhancement: Support custom path for the classification file [@lino-b](https://github.com/lino-b) ([#6858](https://github.com/paperless-ngx/paperless-ngx/pull/6858))
-   Chore(deps-dev): Bump the development group across 1 directory with 2 updates [@dependabot](https://github.com/dependabot) ([#6851](https://github.com/paperless-ngx/paperless-ngx/pull/6851))
-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#6843](https://github.com/paperless-ngx/paperless-ngx/pull/6843))
-   Fix: Don't allow the workflow save to override other process updates [@stumpylog](https://github.com/stumpylog) ([#6849](https://github.com/paperless-ngx/paperless-ngx/pull/6849))
-   Chore(deps): Use psycopg as recommended [@stumpylog](https://github.com/stumpylog) ([#6811](https://github.com/paperless-ngx/paperless-ngx/pull/6811))
-   Enhancement: default to title/content search, allow choosing full search link from global search [@shamoon](https://github.com/shamoon) ([#6805](https://github.com/paperless-ngx/paperless-ngx/pull/6805))
-   Enhancement: only include correspondent 'last_correspondence' if requested [@shamoon](https://github.com/shamoon) ([#6792](https://github.com/paperless-ngx/paperless-ngx/pull/6792))
-   Enhancement: accessibility improvements for tags, doc links, dashboard views [@shamoon](https://github.com/shamoon) ([#6786](https://github.com/paperless-ngx/paperless-ngx/pull/6786))
-   Enhancement: delete pages PDF action [@shamoon](https://github.com/shamoon) ([#6772](https://github.com/paperless-ngx/paperless-ngx/pull/6772))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6793](https://github.com/paperless-ngx/paperless-ngx/pull/6793))
-   Enhancement: support custom logo / title on login page [@shamoon](https://github.com/shamoon) ([#6775](https://github.com/paperless-ngx/paperless-ngx/pull/6775))
-   Chore: Change the code formatter to Ruff [@stumpylog](https://github.com/stumpylog) ([#6756](https://github.com/paperless-ngx/paperless-ngx/pull/6756))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#6761](https://github.com/paperless-ngx/paperless-ngx/pull/6761))
-   Fix: consistently use created_date for doc display [@shamoon](https://github.com/shamoon) ([#6758](https://github.com/paperless-ngx/paperless-ngx/pull/6758))
-   Chore: revert pngx pdf viewer to third party package [@shamoon](https://github.com/shamoon) ([#6741](https://github.com/paperless-ngx/paperless-ngx/pull/6741))
</details>

## paperless-ngx 2.8.6

### Bug Fixes

-   Security: disallow API remote-user auth if disabled [@shamoon](https://github.com/shamoon) ([#6739](https://github.com/paperless-ngx/paperless-ngx/pull/6739))
-   Fix: retain sort field from global search filtering, use FILTER_HAS_TAGS_ALL [@shamoon](https://github.com/shamoon) ([#6737](https://github.com/paperless-ngx/paperless-ngx/pull/6737))

### All App Changes

<details>
<summary>2 changes</summary>

-   Security: disallow API remote-user auth if disabled [@shamoon](https://github.com/shamoon) ([#6739](https://github.com/paperless-ngx/paperless-ngx/pull/6739))
-   Fix: retain sort field from global search filtering, use FILTER_HAS_TAGS_ALL [@shamoon](https://github.com/shamoon) ([#6737](https://github.com/paperless-ngx/paperless-ngx/pull/6737))
</details>

## paperless-ngx 2.8.5

### Bug Fixes

-   Fix: restore search highlighting on large cards results [@shamoon](https://github.com/shamoon) ([#6728](https://github.com/paperless-ngx/paperless-ngx/pull/6728))
-   Fix: global search filtering links broken in 2.8.4 [@shamoon](https://github.com/shamoon) ([#6726](https://github.com/paperless-ngx/paperless-ngx/pull/6726))
-   Fix: some buttons incorrectly aligned in 2.8.4 [@shamoon](https://github.com/shamoon) ([#6715](https://github.com/paperless-ngx/paperless-ngx/pull/6715))
-   Fix: don't format ASN as number on dashboard [@shamoon](https://github.com/shamoon) ([#6708](https://github.com/paperless-ngx/paperless-ngx/pull/6708))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: restore search highlighting on large cards results [@shamoon](https://github.com/shamoon) ([#6728](https://github.com/paperless-ngx/paperless-ngx/pull/6728))
-   Fix: global search filtering links broken in 2.8.4 [@shamoon](https://github.com/shamoon) ([#6726](https://github.com/paperless-ngx/paperless-ngx/pull/6726))
-   Fix: some buttons incorrectly aligned in 2.8.4 [@shamoon](https://github.com/shamoon) ([#6715](https://github.com/paperless-ngx/paperless-ngx/pull/6715))
-   Fix: don't format ASN as number on dashboard [@shamoon](https://github.com/shamoon) ([#6708](https://github.com/paperless-ngx/paperless-ngx/pull/6708))
</details>

## paperless-ngx 2.8.4

### Features

-   Enhancement: display current ASN in statistics [@darmiel](https://github.com/darmiel) ([#6692](https://github.com/paperless-ngx/paperless-ngx/pull/6692))
-   Enhancement: global search tweaks [@shamoon](https://github.com/shamoon) ([#6674](https://github.com/paperless-ngx/paperless-ngx/pull/6674))

### Bug Fixes

-   Security: Correctly disable in pdfjs [@shamoon](https://github.com/shamoon) ([#6702](https://github.com/paperless-ngx/paperless-ngx/pull/6702))
-   Fix: history timestamp tooltip illegible in dark mode [@shamoon](https://github.com/shamoon) ([#6696](https://github.com/paperless-ngx/paperless-ngx/pull/6696))
-   Fix: only count inbox documents from inbox tags with permissions [@shamoon](https://github.com/shamoon) ([#6670](https://github.com/paperless-ngx/paperless-ngx/pull/6670))

### All App Changes

<details>
<summary>5 changes</summary>

-   Enhancement: global search tweaks [@shamoon](https://github.com/shamoon) ([#6674](https://github.com/paperless-ngx/paperless-ngx/pull/6674))
-   Security: Correctly disable in pdfjs [@shamoon](https://github.com/shamoon) ([#6702](https://github.com/paperless-ngx/paperless-ngx/pull/6702))
-   Fix: history timestamp tooltip illegible in dark mode [@shamoon](https://github.com/shamoon) ([#6696](https://github.com/paperless-ngx/paperless-ngx/pull/6696))
-   Enhancement: display current ASN in statistics [@darmiel](https://github.com/darmiel) ([#6692](https://github.com/paperless-ngx/paperless-ngx/pull/6692))
-   Fix: only count inbox documents from inbox tags with permissions [@shamoon](https://github.com/shamoon) ([#6670](https://github.com/paperless-ngx/paperless-ngx/pull/6670))
</details>

## paperless-ngx 2.8.3

### Bug Fixes

-   Fix: respect superuser for document history [@shamoon](https://github.com/shamoon) ([#6661](https://github.com/paperless-ngx/paperless-ngx/pull/6661))
-   Fix: allow 0 in monetary field [@shamoon](https://github.com/shamoon) ([#6658](https://github.com/paperless-ngx/paperless-ngx/pull/6658))
-   Fix: custom field removal doesn't always trigger change detection [@shamoon](https://github.com/shamoon) ([#6653](https://github.com/paperless-ngx/paperless-ngx/pull/6653))
-   Fix: Downgrade and lock lxml [@stumpylog](https://github.com/stumpylog) ([#6655](https://github.com/paperless-ngx/paperless-ngx/pull/6655))
-   Fix: correctly handle global search esc key when open and button foucsed [@shamoon](https://github.com/shamoon) ([#6644](https://github.com/paperless-ngx/paperless-ngx/pull/6644))
-   Fix: consistent monetary field display in list and cards [@shamoon](https://github.com/shamoon) ([#6645](https://github.com/paperless-ngx/paperless-ngx/pull/6645))
-   Fix: doc links and more illegible in light mode [@shamoon](https://github.com/shamoon) ([#6643](https://github.com/paperless-ngx/paperless-ngx/pull/6643))
-   Fix: Allow auditlog to be disabled [@stumpylog](https://github.com/stumpylog) ([#6638](https://github.com/paperless-ngx/paperless-ngx/pull/6638))

### Documentation

-   Chore(docs): Update the sample Compose file to latest database [@stumpylog](https://github.com/stumpylog) ([#6639](https://github.com/paperless-ngx/paperless-ngx/pull/6639))

### All App Changes

<details>
<summary>7 changes</summary>

-   Fix: respect superuser for document history [@shamoon](https://github.com/shamoon) ([#6661](https://github.com/paperless-ngx/paperless-ngx/pull/6661))
-   Fix: allow 0 in monetary field [@shamoon](https://github.com/shamoon) ([#6658](https://github.com/paperless-ngx/paperless-ngx/pull/6658))
-   Fix: custom field removal doesn't always trigger change detection [@shamoon](https://github.com/shamoon) ([#6653](https://github.com/paperless-ngx/paperless-ngx/pull/6653))
-   Fix: correctly handle global search esc key when open and button foucsed [@shamoon](https://github.com/shamoon) ([#6644](https://github.com/paperless-ngx/paperless-ngx/pull/6644))
-   Fix: consistent monetary field display in list and cards [@shamoon](https://github.com/shamoon) ([#6645](https://github.com/paperless-ngx/paperless-ngx/pull/6645))
-   Fix: doc links and more illegible in light mode [@shamoon](https://github.com/shamoon) ([#6643](https://github.com/paperless-ngx/paperless-ngx/pull/6643))
-   Fix: Allow auditlog to be disabled [@stumpylog](https://github.com/stumpylog) ([#6638](https://github.com/paperless-ngx/paperless-ngx/pull/6638))
</details>

## paperless-ngx 2.8.2

### Bug Fixes

-   Fix: Restore the compression of static files for x86_64 [@stumpylog](https://github.com/stumpylog) ([#6627](https://github.com/paperless-ngx/paperless-ngx/pull/6627))
-   Fix: make backend monetary validation accept unpadded decimals [@shamoon](https://github.com/shamoon) ([#6626](https://github.com/paperless-ngx/paperless-ngx/pull/6626))
-   Fix: allow bulk edit with existing fields [@shamoon](https://github.com/shamoon) ([#6625](https://github.com/paperless-ngx/paperless-ngx/pull/6625))
-   Fix: table view doesn't immediately display custom fields on app startup [@shamoon](https://github.com/shamoon) ([#6600](https://github.com/paperless-ngx/paperless-ngx/pull/6600))
-   Fix: dont use limit in subqueries in global search for mariadb compatibility [@shamoon](https://github.com/shamoon) ([#6611](https://github.com/paperless-ngx/paperless-ngx/pull/6611))
-   Fix: exclude admin perms from group permissions serializer [@shamoon](https://github.com/shamoon) ([#6608](https://github.com/paperless-ngx/paperless-ngx/pull/6608))
-   Fix: global search text illegible in light mode [@shamoon](https://github.com/shamoon) ([#6602](https://github.com/paperless-ngx/paperless-ngx/pull/6602))
-   Fix: document history text color illegible in light mode [@shamoon](https://github.com/shamoon) ([#6601](https://github.com/paperless-ngx/paperless-ngx/pull/6601))

### All App Changes

<details>
<summary>10 changes</summary>

-   Fix: Restore the compression of static files for x86_64 [@stumpylog](https://github.com/stumpylog) ([#6627](https://github.com/paperless-ngx/paperless-ngx/pull/6627))
-   Fix: make backend monetary validation accept unpadded decimals [@shamoon](https://github.com/shamoon) ([#6626](https://github.com/paperless-ngx/paperless-ngx/pull/6626))
-   Fix: allow bulk edit with existing fields [@shamoon](https://github.com/shamoon) ([#6625](https://github.com/paperless-ngx/paperless-ngx/pull/6625))
-   Enhancement: show custom field name on cards if empty, add tooltip [@shamoon](https://github.com/shamoon) ([#6620](https://github.com/paperless-ngx/paperless-ngx/pull/6620))
-   Security: Disable in pdfjs [@shamoon](https://github.com/shamoon) ([#6615](https://github.com/paperless-ngx/paperless-ngx/pull/6615))
-   Fix: table view doesn't immediately display custom fields on app startup [@shamoon](https://github.com/shamoon) ([#6600](https://github.com/paperless-ngx/paperless-ngx/pull/6600))
-   Fix: dont use limit in subqueries in global search for mariadb compatibility [@shamoon](https://github.com/shamoon) ([#6611](https://github.com/paperless-ngx/paperless-ngx/pull/6611))
-   Fix: exclude admin perms from group permissions serializer [@shamoon](https://github.com/shamoon) ([#6608](https://github.com/paperless-ngx/paperless-ngx/pull/6608))
-   Fix: global search text illegible in light mode [@shamoon](https://github.com/shamoon) ([#6602](https://github.com/paperless-ngx/paperless-ngx/pull/6602))
-   Fix: document history text color illegible in light mode [@shamoon](https://github.com/shamoon) ([#6601](https://github.com/paperless-ngx/paperless-ngx/pull/6601))
</details>

## paperless-ngx 2.8.1

### Bug Fixes

-   Fix: saved views dont immediately display custom fields in table view [@shamoon](https://github.com/shamoon) ([#6594](https://github.com/paperless-ngx/paperless-ngx/pull/6594))
-   Fix: bulk edit custom fields should support multiple items [@shamoon](https://github.com/shamoon) ([#6589](https://github.com/paperless-ngx/paperless-ngx/pull/6589))

### Dependencies

-   Chore(deps-dev): Bump jinja2 from 3.1.3 to 3.1.4 [@dependabot](https://github.com/dependabot) ([#6579](https://github.com/paperless-ngx/paperless-ngx/pull/6579))
-   Chore(deps-dev): Bump mkdocs-glightbox from 0.3.7 to 0.4.0 in the small-changes group [@dependabot](https://github.com/dependabot) ([#6581](https://github.com/paperless-ngx/paperless-ngx/pull/6581))

### All App Changes

<details>
<summary>3 changes</summary>

-   Fix: saved views dont immediately display custom fields in table view [@shamoon](https://github.com/shamoon) ([#6594](https://github.com/paperless-ngx/paperless-ngx/pull/6594))
-   Chore(deps-dev): Bump mkdocs-glightbox from 0.3.7 to 0.4.0 in the small-changes group [@dependabot](https://github.com/dependabot) ([#6581](https://github.com/paperless-ngx/paperless-ngx/pull/6581))
-   Fix: bulk edit custom fields should support multiple items [@shamoon](https://github.com/shamoon) ([#6589](https://github.com/paperless-ngx/paperless-ngx/pull/6589))
</details>

## paperless-ngx 2.8.0

### Breaking Changes

-   Fix: remove admin.logentry perm, use admin (staff) status [@shamoon](https://github.com/shamoon) ([#6380](https://github.com/paperless-ngx/paperless-ngx/pull/6380))

### Notable Changes

-   Feature: global search, keyboard shortcuts / hotkey support [@shamoon](https://github.com/shamoon) ([#6449](https://github.com/paperless-ngx/paperless-ngx/pull/6449))
-   Feature: custom fields filtering \& bulk editing [@shamoon](https://github.com/shamoon) ([#6484](https://github.com/paperless-ngx/paperless-ngx/pull/6484))
-   Feature: customizable fields display for documents, saved views \& dashboard widgets [@shamoon](https://github.com/shamoon) ([#6439](https://github.com/paperless-ngx/paperless-ngx/pull/6439))
-   Feature: document history (audit log UI) [@shamoon](https://github.com/shamoon) ([#6388](https://github.com/paperless-ngx/paperless-ngx/pull/6388))
-   Chore: Convert the consumer to a plugin [@stumpylog](https://github.com/stumpylog) ([#6361](https://github.com/paperless-ngx/paperless-ngx/pull/6361))

### Features

-   Feature: global search, keyboard shortcuts / hotkey support [@shamoon](https://github.com/shamoon) ([#6449](https://github.com/paperless-ngx/paperless-ngx/pull/6449))
-   Feature: customizable fields display for documents, saved views \& dashboard widgets [@shamoon](https://github.com/shamoon) ([#6439](https://github.com/paperless-ngx/paperless-ngx/pull/6439))
-   Feature: document history (audit log UI) [@shamoon](https://github.com/shamoon) ([#6388](https://github.com/paperless-ngx/paperless-ngx/pull/6388))
-   Enhancement: refactor monetary field [@shamoon](https://github.com/shamoon) ([#6370](https://github.com/paperless-ngx/paperless-ngx/pull/6370))
-   Chore: Convert the consumer to a plugin [@stumpylog](https://github.com/stumpylog) ([#6361](https://github.com/paperless-ngx/paperless-ngx/pull/6361))

### Bug Fixes

-   Fix: always check workflow if set [@shamoon](https://github.com/shamoon) ([#6474](https://github.com/paperless-ngx/paperless-ngx/pull/6474))
-   Fix: use responsive tables for management lists [@DlieBG](https://github.com/DlieBG) ([#6460](https://github.com/paperless-ngx/paperless-ngx/pull/6460))
-   Fix: password reset done template [@shamoon](https://github.com/shamoon) ([#6444](https://github.com/paperless-ngx/paperless-ngx/pull/6444))
-   Fix: show message on empty group list [@DlieBG](https://github.com/DlieBG) ([#6393](https://github.com/paperless-ngx/paperless-ngx/pull/6393))
-   Fix: remove admin.logentry perm, use admin (staff) status [@shamoon](https://github.com/shamoon) ([#6380](https://github.com/paperless-ngx/paperless-ngx/pull/6380))
-   Fix: dont dismiss active alerts on dismiss completed [@shamoon](https://github.com/shamoon) ([#6364](https://github.com/paperless-ngx/paperless-ngx/pull/6364))
-   Fix: Allow lowercase letters in monetary currency code field [@shamoon](https://github.com/shamoon) ([#6359](https://github.com/paperless-ngx/paperless-ngx/pull/6359))
-   Fix: Allow negative monetary values with a current code [@stumpylog](https://github.com/stumpylog) ([#6358](https://github.com/paperless-ngx/paperless-ngx/pull/6358))
-   Fix: add timezone fallback to install script [@Harald-Berghoff](https://github.com/Harald-Berghoff) ([#6336](https://github.com/paperless-ngx/paperless-ngx/pull/6336))

### Maintenance

-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.5.0 to 0.6.0 in the actions group [@dependabot](https://github.com/dependabot) ([#6541](https://github.com/paperless-ngx/paperless-ngx/pull/6541))
-   Chore(deps): Bump all allowed backend packages [@stumpylog](https://github.com/stumpylog) ([#6562](https://github.com/paperless-ngx/paperless-ngx/pull/6562))

### Dependencies

<details>
<summary>10 changes</summary>

-   Chore(deps): Bump stumpylog/image-cleaner-action from 0.5.0 to 0.6.0 in the actions group [@dependabot](https://github.com/dependabot) ([#6541](https://github.com/paperless-ngx/paperless-ngx/pull/6541))
-   Chore(deps-dev): Bump ejs from 3.1.9 to 3.1.10 in /src-ui [@dependabot](https://github.com/dependabot) ([#6540](https://github.com/paperless-ngx/paperless-ngx/pull/6540))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 13 updates [@dependabot](https://github.com/dependabot) ([#6539](https://github.com/paperless-ngx/paperless-ngx/pull/6539))
-   Chore(deps): Bump python-ipware from 2.0.3 to 3.0.0 in the major-versions group [@dependabot](https://github.com/dependabot) ([#6468](https://github.com/paperless-ngx/paperless-ngx/pull/6468))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6466](https://github.com/paperless-ngx/paperless-ngx/pull/6466))
-   Chore: Updates Docker bundled QPDF to 11.9.0 [@stumpylog](https://github.com/stumpylog) ([#6423](https://github.com/paperless-ngx/paperless-ngx/pull/6423))
-   Chore(deps): Bump gunicorn from 21.2.0 to 22.0.0 [@dependabot](https://github.com/dependabot) ([#6416](https://github.com/paperless-ngx/paperless-ngx/pull/6416))
-   Chore(deps): Bump the small-changes group with 11 updates [@dependabot](https://github.com/dependabot) ([#6405](https://github.com/paperless-ngx/paperless-ngx/pull/6405))
-   Chore(deps): Bump idna from 3.6 to 3.7 [@dependabot](https://github.com/dependabot) ([#6377](https://github.com/paperless-ngx/paperless-ngx/pull/6377))
-   Chore(deps): Bump tar from 6.2.0 to 6.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#6373](https://github.com/paperless-ngx/paperless-ngx/pull/6373))
</details>

### All App Changes

<details>
<summary>23 changes</summary>

-   Feature: global search, keyboard shortcuts / hotkey support [@shamoon](https://github.com/shamoon) ([#6449](https://github.com/paperless-ngx/paperless-ngx/pull/6449))
-   Chore(deps-dev): Bump ejs from 3.1.9 to 3.1.10 in /src-ui [@dependabot](https://github.com/dependabot) ([#6540](https://github.com/paperless-ngx/paperless-ngx/pull/6540))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 13 updates [@dependabot](https://github.com/dependabot) ([#6539](https://github.com/paperless-ngx/paperless-ngx/pull/6539))
-   Chore: Hand craft SQL queries [@stumpylog](https://github.com/stumpylog) ([#6489](https://github.com/paperless-ngx/paperless-ngx/pull/6489))
-   Feature: custom fields filtering \& bulk editing [@shamoon](https://github.com/shamoon) ([#6484](https://github.com/paperless-ngx/paperless-ngx/pull/6484))
-   Feature: customizable fields display for documents, saved views \& dashboard widgets [@shamoon](https://github.com/shamoon) ([#6439](https://github.com/paperless-ngx/paperless-ngx/pull/6439))
-   Chore(deps): Bump python-ipware from 2.0.3 to 3.0.0 in the major-versions group [@dependabot](https://github.com/dependabot) ([#6468](https://github.com/paperless-ngx/paperless-ngx/pull/6468))
-   Feature: document history (audit log UI) [@shamoon](https://github.com/shamoon) ([#6388](https://github.com/paperless-ngx/paperless-ngx/pull/6388))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6466](https://github.com/paperless-ngx/paperless-ngx/pull/6466))
-   Fix: always check workflow if set [@shamoon](https://github.com/shamoon) ([#6474](https://github.com/paperless-ngx/paperless-ngx/pull/6474))
-   Fix: use responsive tables for management lists [@DlieBG](https://github.com/DlieBG) ([#6460](https://github.com/paperless-ngx/paperless-ngx/pull/6460))
-   Fix: password reset done template [@shamoon](https://github.com/shamoon) ([#6444](https://github.com/paperless-ngx/paperless-ngx/pull/6444))
-   Enhancement: refactor monetary field [@shamoon](https://github.com/shamoon) ([#6370](https://github.com/paperless-ngx/paperless-ngx/pull/6370))
-   Enhancement: improve layout, button labels for custom fields dropdown [@shamoon](https://github.com/shamoon) ([#6362](https://github.com/paperless-ngx/paperless-ngx/pull/6362))
-   Chore: Convert the consumer to a plugin [@stumpylog](https://github.com/stumpylog) ([#6361](https://github.com/paperless-ngx/paperless-ngx/pull/6361))
-   Chore(deps): Bump the small-changes group with 11 updates [@dependabot](https://github.com/dependabot) ([#6405](https://github.com/paperless-ngx/paperless-ngx/pull/6405))
-   Enhancement: Hide columns in document list if user does not have permissions [@theomega](https://github.com/theomega) ([#6415](https://github.com/paperless-ngx/paperless-ngx/pull/6415))
-   Fix: show message on empty group list [@DlieBG](https://github.com/DlieBG) ([#6393](https://github.com/paperless-ngx/paperless-ngx/pull/6393))
-   Fix: remove admin.logentry perm, use admin (staff) status [@shamoon](https://github.com/shamoon) ([#6380](https://github.com/paperless-ngx/paperless-ngx/pull/6380))
-   Chore(deps): Bump tar from 6.2.0 to 6.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#6373](https://github.com/paperless-ngx/paperless-ngx/pull/6373))
-   Fix: dont dismiss active alerts on dismiss completed [@shamoon](https://github.com/shamoon) ([#6364](https://github.com/paperless-ngx/paperless-ngx/pull/6364))
-   Fix: Allow lowercase letters in monetary currency code field [@shamoon](https://github.com/shamoon) ([#6359](https://github.com/paperless-ngx/paperless-ngx/pull/6359))
-   Fix: Allow negative monetary values with a current code [@stumpylog](https://github.com/stumpylog) ([#6358](https://github.com/paperless-ngx/paperless-ngx/pull/6358))
</details>

## paperless-ngx 2.7.2

### Bug Fixes

-   Fix: select dropdown background colors not visible in light mode [@shamoon](https://github.com/shamoon) ([#6323](https://github.com/paperless-ngx/paperless-ngx/pull/6323))
-   Fix: spacing in reset and incorrect display in saved views [@shamoon](https://github.com/shamoon) ([#6324](https://github.com/paperless-ngx/paperless-ngx/pull/6324))
-   Fix: disable invalid create endpoints [@shamoon](https://github.com/shamoon) ([#6320](https://github.com/paperless-ngx/paperless-ngx/pull/6320))
-   Fix: dont initialize page numbers, allow split with browser pdf viewer [@shamoon](https://github.com/shamoon) ([#6314](https://github.com/paperless-ngx/paperless-ngx/pull/6314))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: select dropdown background colors not visible in light mode [@shamoon](https://github.com/shamoon) ([#6323](https://github.com/paperless-ngx/paperless-ngx/pull/6323))
-   Fix: spacing in reset and incorrect display in saved views [@shamoon](https://github.com/shamoon) ([#6324](https://github.com/paperless-ngx/paperless-ngx/pull/6324))
-   Fix: disable invalid create endpoints [@shamoon](https://github.com/shamoon) ([#6320](https://github.com/paperless-ngx/paperless-ngx/pull/6320))
-   Fix: dont initialize page numbers, allow split with browser pdf viewer [@shamoon](https://github.com/shamoon) ([#6314](https://github.com/paperless-ngx/paperless-ngx/pull/6314))
</details>

## paperless-ngx 2.7.1

### Bug Fixes

-   Fix: Only disable split button if pages = 1 [@shamoon](https://github.com/shamoon) ([#6304](https://github.com/paperless-ngx/paperless-ngx/pull/6304))
-   Fix: Use correct custom field id when splitting [@shamoon](https://github.com/shamoon) ([#6303](https://github.com/paperless-ngx/paperless-ngx/pull/6303))
-   Fix: Rotation fails due to celery chord [@stumpylog](https://github.com/stumpylog) ([#6306](https://github.com/paperless-ngx/paperless-ngx/pull/6306))
-   Fix: split user / group objects error [@shamoon](https://github.com/shamoon) ([#6302](https://github.com/paperless-ngx/paperless-ngx/pull/6302))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: Only disable split button if pages = 1 [@shamoon](https://github.com/shamoon) ([#6304](https://github.com/paperless-ngx/paperless-ngx/pull/6304))
-   Fix: Use correct custom field id when splitting [@shamoon](https://github.com/shamoon) ([#6303](https://github.com/paperless-ngx/paperless-ngx/pull/6303))
-   Fix: Rotation fails due to celery chord [@stumpylog](https://github.com/stumpylog) ([#6306](https://github.com/paperless-ngx/paperless-ngx/pull/6306))
-   Fix: split user / group objects error [@shamoon](https://github.com/shamoon) ([#6302](https://github.com/paperless-ngx/paperless-ngx/pull/6302))
</details>

## paperless-ngx 2.7.0

### Notable Changes

-   Feature: PDF actions - merge, split \& rotate @shamoon ([#6094](https://github.com/paperless-ngx/paperless-ngx/pull/6094))
-   Change: enable auditlog by default, fix import / export @shamoon ([#6267](https://github.com/paperless-ngx/paperless-ngx/pull/6267))

### Enhancements

-   Enhancement: always place search term first in autocomplete results @shamoon ([#6142](https://github.com/paperless-ngx/paperless-ngx/pull/6142))

### Maintenance

-   Chore: Standardize subprocess running and logging [@stumpylog](https://github.com/stumpylog) ([#6275](https://github.com/paperless-ngx/paperless-ngx/pull/6275))

### Bug Fixes

-   Fix: Escape the secret key when writing it to the env file [@stumpylog](https://github.com/stumpylog) ([#6243](https://github.com/paperless-ngx/paperless-ngx/pull/6243))
-   Fix: Hide sidebar labels if group is empty [@shamoon](https://github.com/shamoon) ([#6254](https://github.com/paperless-ngx/paperless-ngx/pull/6254))
-   Fix: management list clear all should clear header checkbox [@shamoon](https://github.com/shamoon) ([#6253](https://github.com/paperless-ngx/paperless-ngx/pull/6253))
-   Fix: start-align object names in some UI lists [@shamoon](https://github.com/shamoon) ([#6188](https://github.com/paperless-ngx/paperless-ngx/pull/6188))
-   Fix: allow scroll long upload files alerts list [@shamoon](https://github.com/shamoon) ([#6184](https://github.com/paperless-ngx/paperless-ngx/pull/6184))
-   Fix: document_renamer fails with audit_log enabled [@shamoon](https://github.com/shamoon) ([#6175](https://github.com/paperless-ngx/paperless-ngx/pull/6175))
-   Fix: catch sessionStorage errors for large documents [@shamoon](https://github.com/shamoon) ([#6150](https://github.com/paperless-ngx/paperless-ngx/pull/6150))

### Dependencies

<details>
<summary>9 changes</summary>

-   Chore(deps): Bump pillow from 10.2.0 to 10.3.0 [@dependabot](https://github.com/dependabot) ([#6268](https://github.com/paperless-ngx/paperless-ngx/pull/6268))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6276](https://github.com/paperless-ngx/paperless-ngx/pull/6276))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 17 updates [@dependabot](https://github.com/dependabot) ([#6248](https://github.com/paperless-ngx/paperless-ngx/pull/6248))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.42.0 to 1.42.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.42.0 to 1.42.1 in /src-ui @dependabot) ([#6250](https://github.com/paperless-ngx/paperless-ngx/pull/6250))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.24 to 20.12.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.24 to 20.12.2 in /src-ui @dependabot) ([#6251](https://github.com/paperless-ngx/paperless-ngx/pull/6251))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#6249](https://github.com/paperless-ngx/paperless-ngx/pull/6249))
-   Chore(deps-dev): Bump express from 4.18.3 to 4.19.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#6207](https://github.com/paperless-ngx/paperless-ngx/pull/6207))
-   Chore(deps-dev): Bump webpack-dev-middleware from 5.3.3 to 5.3.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#6161](https://github.com/paperless-ngx/paperless-ngx/pull/6161))
-   Chore(deps-dev): Bump the development group with 4 updates [@dependabot](https://github.com/dependabot) ([#6131](https://github.com/paperless-ngx/paperless-ngx/pull/6131))
</details>

### All App Changes

<details>
<summary>20 changes</summary>

-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#6276](https://github.com/paperless-ngx/paperless-ngx/pull/6276))
-   Chore: Standardize subprocess running and logging [@stumpylog](https://github.com/stumpylog) ([#6275](https://github.com/paperless-ngx/paperless-ngx/pull/6275))
-   Change: enable auditlog by default, fix import / export [@shamoon](https://github.com/shamoon) ([#6267](https://github.com/paperless-ngx/paperless-ngx/pull/6267))
-   Fix: Hide sidebar labels if group is empty [@shamoon](https://github.com/shamoon) ([#6254](https://github.com/paperless-ngx/paperless-ngx/pull/6254))
-   Fix: management list clear all should clear header checkbox [@shamoon](https://github.com/shamoon) ([#6253](https://github.com/paperless-ngx/paperless-ngx/pull/6253))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 17 updates [@dependabot](https://github.com/dependabot) ([#6248](https://github.com/paperless-ngx/paperless-ngx/pull/6248))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.42.0 to 1.42.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.42.0 to 1.42.1 in /src-ui @dependabot) ([#6250](https://github.com/paperless-ngx/paperless-ngx/pull/6250))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.24 to 20.12.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.24 to 20.12.2 in /src-ui @dependabot) ([#6251](https://github.com/paperless-ngx/paperless-ngx/pull/6251))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#6249](https://github.com/paperless-ngx/paperless-ngx/pull/6249))
-   Enhancement: support custom fields in post_document endpoint [@shamoon](https://github.com/shamoon) ([#6222](https://github.com/paperless-ngx/paperless-ngx/pull/6222))
-   Enhancement: add ASN to consume rejection message [@eliasp](https://github.com/eliasp) ([#6217](https://github.com/paperless-ngx/paperless-ngx/pull/6217))
-   Chore(deps-dev): Bump express from 4.18.3 to 4.19.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#6207](https://github.com/paperless-ngx/paperless-ngx/pull/6207))
-   Feature: PDF actions - merge, split \& rotate [@shamoon](https://github.com/shamoon) ([#6094](https://github.com/paperless-ngx/paperless-ngx/pull/6094))
-   Fix: start-align object names in some UI lists [@shamoon](https://github.com/shamoon) ([#6188](https://github.com/paperless-ngx/paperless-ngx/pull/6188))
-   Fix: allow scroll long upload files alerts list [@shamoon](https://github.com/shamoon) ([#6184](https://github.com/paperless-ngx/paperless-ngx/pull/6184))
-   Fix: document_renamer fails with audit_log enabled [@shamoon](https://github.com/shamoon) ([#6175](https://github.com/paperless-ngx/paperless-ngx/pull/6175))
-   Chore(deps-dev): Bump webpack-dev-middleware from 5.3.3 to 5.3.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#6161](https://github.com/paperless-ngx/paperless-ngx/pull/6161))
-   Enhancement: always place search term first in autocomplete results [@shamoon](https://github.com/shamoon) ([#6142](https://github.com/paperless-ngx/paperless-ngx/pull/6142))
-   Fix: catch sessionStorage errors for large documents [@shamoon](https://github.com/shamoon) ([#6150](https://github.com/paperless-ngx/paperless-ngx/pull/6150))
-   Chore(deps-dev): Bump the development group with 4 updates [@dependabot](https://github.com/dependabot) ([#6131](https://github.com/paperless-ngx/paperless-ngx/pull/6131))
</details>

## paperless-ngx 2.6.3

### Bug Fixes

-   Fix: allow setting allauth [@shamoon](https://github.com/shamoon) ([#6105](https://github.com/paperless-ngx/paperless-ngx/pull/6105))
-   Change: dont require empty bulk edit parameters [@shamoon](https://github.com/shamoon) ([#6059](https://github.com/paperless-ngx/paperless-ngx/pull/6059))

### Dependencies

<details>
<summary>4 changes</summary>

-   Chore(deps-dev): Bump follow-redirects from 1.15.5 to 1.15.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#6120](https://github.com/paperless-ngx/paperless-ngx/pull/6120))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#6079](https://github.com/paperless-ngx/paperless-ngx/pull/6079))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#6080](https://github.com/paperless-ngx/paperless-ngx/pull/6080))
-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#6081](https://github.com/paperless-ngx/paperless-ngx/pull/6081))
</details>

### All App Changes

<details>
<summary>8 changes</summary>

-   Chore(deps-dev): Bump follow-redirects from 1.15.5 to 1.15.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#6120](https://github.com/paperless-ngx/paperless-ngx/pull/6120))
-   Fix: allow setting allauth [@shamoon](https://github.com/shamoon) ([#6105](https://github.com/paperless-ngx/paperless-ngx/pull/6105))
-   Change: remove credentials from redis url in system status [@shamoon](https://github.com/shamoon) ([#6104](https://github.com/paperless-ngx/paperless-ngx/pull/6104))
-   Chore(deps-dev): Bump the development group with 3 updates [@dependabot](https://github.com/dependabot) ([#6079](https://github.com/paperless-ngx/paperless-ngx/pull/6079))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#6080](https://github.com/paperless-ngx/paperless-ngx/pull/6080))
-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#6081](https://github.com/paperless-ngx/paperless-ngx/pull/6081))
-   Change: dont require empty bulk edit parameters [@shamoon](https://github.com/shamoon) ([#6059](https://github.com/paperless-ngx/paperless-ngx/pull/6059))
-   Fix: missing translation string [@DimitriDR](https://github.com/DimitriDR) ([#6054](https://github.com/paperless-ngx/paperless-ngx/pull/6054))
</details>

## paperless-ngx 2.6.2

### Features

-   Enhancement: move and rename files when storage paths deleted, update file handling docs [@shamoon](https://github.com/shamoon) ([#6033](https://github.com/paperless-ngx/paperless-ngx/pull/6033))
-   Enhancement: better detection of default currency code [@shamoon](https://github.com/shamoon) ([#6020](https://github.com/paperless-ngx/paperless-ngx/pull/6020))

### Bug Fixes

-   Fix: make document counts in object lists permissions-aware [@shamoon](https://github.com/shamoon) ([#6019](https://github.com/paperless-ngx/paperless-ngx/pull/6019))

### All App Changes

<details>
<summary>3 changes</summary>

-   Enhancement: move and rename files when storage paths deleted, update file handling docs [@shamoon](https://github.com/shamoon) ([#6033](https://github.com/paperless-ngx/paperless-ngx/pull/6033))
-   Fix: make document counts in object lists permissions-aware [@shamoon](https://github.com/shamoon) ([#6019](https://github.com/paperless-ngx/paperless-ngx/pull/6019))
-   Enhancement: better detection of default currency code [@shamoon](https://github.com/shamoon) ([#6020](https://github.com/paperless-ngx/paperless-ngx/pull/6020))
</details>

## paperless-ngx 2.6.1

### All App Changes

-   Change: tweaks to system status [@shamoon](https://github.com/shamoon) ([#6008](https://github.com/paperless-ngx/paperless-ngx/pull/6008))

## paperless-ngx 2.6.0

### Features

-   Feature: Allow user to control PIL image pixel limit [@stumpylog](https://github.com/stumpylog) ([#5997](https://github.com/paperless-ngx/paperless-ngx/pull/5997))
-   Feature: Allow a user to disable the pixel limit for OCR entirely [@stumpylog](https://github.com/stumpylog) ([#5996](https://github.com/paperless-ngx/paperless-ngx/pull/5996))
-   Feature: workflow removal action [@shamoon](https://github.com/shamoon) ([#5928](https://github.com/paperless-ngx/paperless-ngx/pull/5928))
-   Feature: system status [@shamoon](https://github.com/shamoon) ([#5743](https://github.com/paperless-ngx/paperless-ngx/pull/5743))
-   Enhancement: better monetary field with currency code [@shamoon](https://github.com/shamoon) ([#5858](https://github.com/paperless-ngx/paperless-ngx/pull/5858))
-   Enhancement: support disabling regular login [@shamoon](https://github.com/shamoon) ([#5816](https://github.com/paperless-ngx/paperless-ngx/pull/5816))

### Bug Fixes

-   Fix: refactor base path settings, correct logout redirect [@shamoon](https://github.com/shamoon) ([#5976](https://github.com/paperless-ngx/paperless-ngx/pull/5976))
-   Fix: always pass from UI, dont require in API [@shamoon](https://github.com/shamoon) ([#5962](https://github.com/paperless-ngx/paperless-ngx/pull/5962))
-   Fix: Clear metadata cache when the filename(s) change [@stumpylog](https://github.com/stumpylog) ([#5957](https://github.com/paperless-ngx/paperless-ngx/pull/5957))
-   Fix: include monetary, float and doc link values in search filters [@shamoon](https://github.com/shamoon) ([#5951](https://github.com/paperless-ngx/paperless-ngx/pull/5951))
-   Fix: Better handling of a corrupted index [@stumpylog](https://github.com/stumpylog) ([#5950](https://github.com/paperless-ngx/paperless-ngx/pull/5950))
-   Fix: Don't assume the location of scratch directory in Docker [@stumpylog](https://github.com/stumpylog) ([#5948](https://github.com/paperless-ngx/paperless-ngx/pull/5948))
-   Fix: ensure document title always limited to 128 chars [@shamoon](https://github.com/shamoon) ([#5934](https://github.com/paperless-ngx/paperless-ngx/pull/5934))
-   Fix: use for password reset emails, if set [@shamoon](https://github.com/shamoon) ([#5902](https://github.com/paperless-ngx/paperless-ngx/pull/5902))
-   Fix: Correct docker compose check in install script [@ShanSanear](https://github.com/ShanSanear) ([#5917](https://github.com/paperless-ngx/paperless-ngx/pull/5917))
-   Fix: respect global permissions for UI settings [@shamoon](https://github.com/shamoon) ([#5919](https://github.com/paperless-ngx/paperless-ngx/pull/5919))
-   Fix: allow disable email verification during signup [@shamoon](https://github.com/shamoon) ([#5895](https://github.com/paperless-ngx/paperless-ngx/pull/5895))
-   Fix: refactor accounts templates and create signup template [@shamoon](https://github.com/shamoon) ([#5899](https://github.com/paperless-ngx/paperless-ngx/pull/5899))

### Maintenance

-   Chore(deps): Bump the actions group with 3 updates [@dependabot](https://github.com/dependabot) ([#5907](https://github.com/paperless-ngx/paperless-ngx/pull/5907))
-   Chore: Ignores uvicorn updates in dependabot [@stumpylog](https://github.com/stumpylog) ([#5906](https://github.com/paperless-ngx/paperless-ngx/pull/5906))

### Dependencies

<details>
<summary>15 changes</summary>

-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#6001](https://github.com/paperless-ngx/paperless-ngx/pull/6001))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5998](https://github.com/paperless-ngx/paperless-ngx/pull/5998))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#6000](https://github.com/paperless-ngx/paperless-ngx/pull/6000))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.41.2 to 1.42.0 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.41.2 to 1.42.0 in /src-ui @dependabot) ([#5964](https://github.com/paperless-ngx/paperless-ngx/pull/5964))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.20 to 20.11.24 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.20 to 20.11.24 in /src-ui @dependabot) ([#5965](https://github.com/paperless-ngx/paperless-ngx/pull/5965))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 11 updates [@dependabot](https://github.com/dependabot) ([#5963](https://github.com/paperless-ngx/paperless-ngx/pull/5963))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#5918](https://github.com/paperless-ngx/paperless-ngx/pull/5918))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.16 to 20.11.20 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.16 to 20.11.20 in /src-ui @dependabot) ([#5912](https://github.com/paperless-ngx/paperless-ngx/pull/5912))
-   Chore(deps): Bump zone.js from 0.14.3 to 0.14.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#5913](https://github.com/paperless-ngx/paperless-ngx/pull/5913))
-   Chore(deps): Bump bootstrap from 5.3.2 to 5.3.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5911](https://github.com/paperless-ngx/paperless-ngx/pull/5911))
-   Chore(deps-dev): Bump typescript from 5.2.2 to 5.3.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5915](https://github.com/paperless-ngx/paperless-ngx/pull/5915))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 15 updates [@dependabot](https://github.com/dependabot) ([#5908](https://github.com/paperless-ngx/paperless-ngx/pull/5908))
-   Chore(deps): Bump the small-changes group with 4 updates [@dependabot](https://github.com/dependabot) ([#5916](https://github.com/paperless-ngx/paperless-ngx/pull/5916))
-   Chore(deps-dev): Bump the development group with 4 updates [@dependabot](https://github.com/dependabot) ([#5914](https://github.com/paperless-ngx/paperless-ngx/pull/5914))
-   Chore(deps): Bump the actions group with 3 updates [@dependabot](https://github.com/dependabot) ([#5907](https://github.com/paperless-ngx/paperless-ngx/pull/5907))
</details>

### All App Changes

<details>
<summary>33 changes</summary>

-   Feature: Allow user to control PIL image pixel limit [@stumpylog](https://github.com/stumpylog) ([#5997](https://github.com/paperless-ngx/paperless-ngx/pull/5997))
-   Enhancement: show ID when editing objects [@shamoon](https://github.com/shamoon) ([#6003](https://github.com/paperless-ngx/paperless-ngx/pull/6003))
-   Feature: Allow a user to disable the pixel limit for OCR entirely [@stumpylog](https://github.com/stumpylog) ([#5996](https://github.com/paperless-ngx/paperless-ngx/pull/5996))
-   Chore(deps): Bump the small-changes group with 3 updates [@dependabot](https://github.com/dependabot) ([#6001](https://github.com/paperless-ngx/paperless-ngx/pull/6001))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5998](https://github.com/paperless-ngx/paperless-ngx/pull/5998))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#6000](https://github.com/paperless-ngx/paperless-ngx/pull/6000))
-   Feature: workflow removal action [@shamoon](https://github.com/shamoon) ([#5928](https://github.com/paperless-ngx/paperless-ngx/pull/5928))
-   Feature: system status [@shamoon](https://github.com/shamoon) ([#5743](https://github.com/paperless-ngx/paperless-ngx/pull/5743))
-   Fix: refactor base path settings, correct logout redirect [@shamoon](https://github.com/shamoon) ([#5976](https://github.com/paperless-ngx/paperless-ngx/pull/5976))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.41.2 to 1.42.0 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.41.2 to 1.42.0 in /src-ui @dependabot) ([#5964](https://github.com/paperless-ngx/paperless-ngx/pull/5964))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.20 to 20.11.24 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.20 to 20.11.24 in /src-ui @dependabot) ([#5965](https://github.com/paperless-ngx/paperless-ngx/pull/5965))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 11 updates [@dependabot](https://github.com/dependabot) ([#5963](https://github.com/paperless-ngx/paperless-ngx/pull/5963))
-   Fix: always pass from UI, dont require in API [@shamoon](https://github.com/shamoon) ([#5962](https://github.com/paperless-ngx/paperless-ngx/pull/5962))
-   Fix: Clear metadata cache when the filename(s) change [@stumpylog](https://github.com/stumpylog) ([#5957](https://github.com/paperless-ngx/paperless-ngx/pull/5957))
-   Fix: include monetary, float and doc link values in search filters [@shamoon](https://github.com/shamoon) ([#5951](https://github.com/paperless-ngx/paperless-ngx/pull/5951))
-   Fix: Better handling of a corrupted index [@stumpylog](https://github.com/stumpylog) ([#5950](https://github.com/paperless-ngx/paperless-ngx/pull/5950))
-   Chore: Includes OCRMyPdf logging into the log file [@stumpylog](https://github.com/stumpylog) ([#5947](https://github.com/paperless-ngx/paperless-ngx/pull/5947))
-   Fix: ensure document title always limited to 128 chars [@shamoon](https://github.com/shamoon) ([#5934](https://github.com/paperless-ngx/paperless-ngx/pull/5934))
-   Enhancement: better monetary field with currency code [@shamoon](https://github.com/shamoon) ([#5858](https://github.com/paperless-ngx/paperless-ngx/pull/5858))
-   Change: add Thumbs.db to default ignores [@DennisGaida](https://github.com/DennisGaida) ([#5924](https://github.com/paperless-ngx/paperless-ngx/pull/5924))
-   Fix: use for password reset emails, if set [@shamoon](https://github.com/shamoon) ([#5902](https://github.com/paperless-ngx/paperless-ngx/pull/5902))
-   Fix: respect global permissions for UI settings [@shamoon](https://github.com/shamoon) ([#5919](https://github.com/paperless-ngx/paperless-ngx/pull/5919))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#5918](https://github.com/paperless-ngx/paperless-ngx/pull/5918))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.11.16 to 20.11.20 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.11.16 to 20.11.20 in /src-ui @dependabot) ([#5912](https://github.com/paperless-ngx/paperless-ngx/pull/5912))
-   Chore(deps): Bump zone.js from 0.14.3 to 0.14.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#5913](https://github.com/paperless-ngx/paperless-ngx/pull/5913))
-   Chore(deps): Bump bootstrap from 5.3.2 to 5.3.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5911](https://github.com/paperless-ngx/paperless-ngx/pull/5911))
-   Chore(deps-dev): Bump typescript from 5.2.2 to 5.3.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5915](https://github.com/paperless-ngx/paperless-ngx/pull/5915))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 15 updates [@dependabot](https://github.com/dependabot) ([#5908](https://github.com/paperless-ngx/paperless-ngx/pull/5908))
-   Fix: allow disable email verification during signup [@shamoon](https://github.com/shamoon) ([#5895](https://github.com/paperless-ngx/paperless-ngx/pull/5895))
-   Fix: refactor accounts templates and create signup template [@shamoon](https://github.com/shamoon) ([#5899](https://github.com/paperless-ngx/paperless-ngx/pull/5899))
-   Chore(deps): Bump the small-changes group with 4 updates [@dependabot](https://github.com/dependabot) ([#5916](https://github.com/paperless-ngx/paperless-ngx/pull/5916))
-   Chore(deps-dev): Bump the development group with 4 updates [@dependabot](https://github.com/dependabot) ([#5914](https://github.com/paperless-ngx/paperless-ngx/pull/5914))
-   Enhancement: support disabling regular login [@shamoon](https://github.com/shamoon) ([#5816](https://github.com/paperless-ngx/paperless-ngx/pull/5816))
</details>

## paperless-ngx 2.5.4

### Bug Fixes

-   Fix: handle title placeholder for docs without original_filename [@shamoon](https://github.com/shamoon) ([#5828](https://github.com/paperless-ngx/paperless-ngx/pull/5828))
-   Fix: bulk edit objects does not respect global permissions [@shamoon](https://github.com/shamoon) ([#5888](https://github.com/paperless-ngx/paperless-ngx/pull/5888))
-   Fix: intermittent save \& close warnings [@shamoon](https://github.com/shamoon) ([#5838](https://github.com/paperless-ngx/paperless-ngx/pull/5838))
-   Fix: inotify read timeout not in ms [@grembo](https://github.com/grembo) ([#5876](https://github.com/paperless-ngx/paperless-ngx/pull/5876))
-   Fix: allow relative date queries not in quick list [@shamoon](https://github.com/shamoon) ([#5801](https://github.com/paperless-ngx/paperless-ngx/pull/5801))
-   Fix: pass rule id to consumed .eml files [@shamoon](https://github.com/shamoon) ([#5800](https://github.com/paperless-ngx/paperless-ngx/pull/5800))

### Dependencies

-   Chore(deps): Bump cryptography from 42.0.2 to 42.0.4 [@dependabot](https://github.com/dependabot) ([#5851](https://github.com/paperless-ngx/paperless-ngx/pull/5851))
-   Chore(deps-dev): Bump ip from 2.0.0 to 2.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#5835](https://github.com/paperless-ngx/paperless-ngx/pull/5835))
-   Chore(deps): Bump undici and [@<!---->angular-devkit/build-angular in /src-ui @dependabot](https://github.com/<!---->angular-devkit/build-angular in /src-ui @dependabot) ([#5796](https://github.com/paperless-ngx/paperless-ngx/pull/5796))

### All App Changes

<details>
<summary>8 changes</summary>

-   Fix: handle title placeholder for docs without original_filename [@shamoon](https://github.com/shamoon) ([#5828](https://github.com/paperless-ngx/paperless-ngx/pull/5828))
-   Fix: bulk edit objects does not respect global permissions [@shamoon](https://github.com/shamoon) ([#5888](https://github.com/paperless-ngx/paperless-ngx/pull/5888))
-   Fix: intermittent save \& close warnings [@shamoon](https://github.com/shamoon) ([#5838](https://github.com/paperless-ngx/paperless-ngx/pull/5838))
-   Fix: inotify read timeout not in ms [@grembo](https://github.com/grembo) ([#5876](https://github.com/paperless-ngx/paperless-ngx/pull/5876))
-   Chore(deps-dev): Bump ip from 2.0.0 to 2.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#5835](https://github.com/paperless-ngx/paperless-ngx/pull/5835))
-   Chore(deps): Bump undici and [@<!---->angular-devkit/build-angular in /src-ui @dependabot](https://github.com/<!---->angular-devkit/build-angular in /src-ui @dependabot) ([#5796](https://github.com/paperless-ngx/paperless-ngx/pull/5796))
-   Fix: allow relative date queries not in quick list [@shamoon](https://github.com/shamoon) ([#5801](https://github.com/paperless-ngx/paperless-ngx/pull/5801))
-   Fix: pass rule id to consumed .eml files [@shamoon](https://github.com/shamoon) ([#5800](https://github.com/paperless-ngx/paperless-ngx/pull/5800))
</details>

## paperless-ngx 2.5.3

### Bug Fixes

-   Fix: dont allow allauth redirects to any host [@shamoon](https://github.com/shamoon) ([#5783](https://github.com/paperless-ngx/paperless-ngx/pull/5783))
-   Fix: Interaction when both splitting and ASN are enabled [@stumpylog](https://github.com/stumpylog) ([#5779](https://github.com/paperless-ngx/paperless-ngx/pull/5779))
-   Fix: moved ssl_mode parameter for mysql backend engine [@MaciejSzczurek](https://github.com/MaciejSzczurek) ([#5771](https://github.com/paperless-ngx/paperless-ngx/pull/5771))

### All App Changes

<details>
<summary>3 changes</summary>

-   Fix: dont allow allauth redirects to any host [@shamoon](https://github.com/shamoon) ([#5783](https://github.com/paperless-ngx/paperless-ngx/pull/5783))
-   Fix: Interaction when both splitting and ASN are enabled [@stumpylog](https://github.com/stumpylog) ([#5779](https://github.com/paperless-ngx/paperless-ngx/pull/5779))
-   Fix: moved ssl_mode parameter for mysql backend engine [@MaciejSzczurek](https://github.com/MaciejSzczurek) ([#5771](https://github.com/paperless-ngx/paperless-ngx/pull/5771))
</details>

## paperless-ngx 2.5.2

### Bug Fixes

-   Fix: Generated secret key may include single or double quotes [@schmidtnz](https://github.com/schmidtnz) ([#5767](https://github.com/paperless-ngx/paperless-ngx/pull/5767))
-   Fix: consumer status alerts container blocks elements [@shamoon](https://github.com/shamoon) ([#5762](https://github.com/paperless-ngx/paperless-ngx/pull/5762))
-   Fix: handle document notes user format api change [@shamoon](https://github.com/shamoon) ([#5751](https://github.com/paperless-ngx/paperless-ngx/pull/5751))
-   Fix: Assign ASN from barcode only after any splitting [@stumpylog](https://github.com/stumpylog) ([#5745](https://github.com/paperless-ngx/paperless-ngx/pull/5745))

### Dependencies

-   Chore(deps): Bump the major-versions group with 1 update [@dependabot](https://github.com/dependabot) ([#5741](https://github.com/paperless-ngx/paperless-ngx/pull/5741))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: consumer status alerts container blocks elements [@shamoon](https://github.com/shamoon) ([#5762](https://github.com/paperless-ngx/paperless-ngx/pull/5762))
-   Fix: handle document notes user format api change [@shamoon](https://github.com/shamoon) ([#5751](https://github.com/paperless-ngx/paperless-ngx/pull/5751))
-   Fix: Assign ASN from barcode only after any splitting [@stumpylog](https://github.com/stumpylog) ([#5745](https://github.com/paperless-ngx/paperless-ngx/pull/5745))
-   Chore(deps): Bump the major-versions group with 1 update [@dependabot](https://github.com/dependabot) ([#5741](https://github.com/paperless-ngx/paperless-ngx/pull/5741))
</details>

## paperless-ngx 2.5.1

### Bug Fixes

-   Fix: Splitting on ASN barcodes even if not enabled [@stumpylog](https://github.com/stumpylog) ([#5740](https://github.com/paperless-ngx/paperless-ngx/pull/5740))

### Dependencies

-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5737](https://github.com/paperless-ngx/paperless-ngx/pull/5737))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#5739](https://github.com/paperless-ngx/paperless-ngx/pull/5739))

### All App Changes

<details>
<summary>3 changes</summary>

-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5737](https://github.com/paperless-ngx/paperless-ngx/pull/5737))
-   Chore(deps): Bump the django group with 1 update [@dependabot](https://github.com/dependabot) ([#5739](https://github.com/paperless-ngx/paperless-ngx/pull/5739))
-   Fix: Splitting on ASN barcodes even if not enabled [@stumpylog](https://github.com/stumpylog) ([#5740](https://github.com/paperless-ngx/paperless-ngx/pull/5740))
</details>

## paperless-ngx 2.5.0

### Breaking Changes

-   Enhancement: bulk delete objects [@shamoon](https://github.com/shamoon) ([#5688](https://github.com/paperless-ngx/paperless-ngx/pull/5688))

### Notable Changes

-   Feature: OIDC \& social authentication [@mpflanzer](https://github.com/mpflanzer) ([#5190](https://github.com/paperless-ngx/paperless-ngx/pull/5190))

### Features

-   Enhancement: confirm buttons [@shamoon](https://github.com/shamoon) ([#5680](https://github.com/paperless-ngx/paperless-ngx/pull/5680))
-   Enhancement: bulk delete objects [@shamoon](https://github.com/shamoon) ([#5688](https://github.com/paperless-ngx/paperless-ngx/pull/5688))
-   Feature: allow create objects from bulk edit [@shamoon](https://github.com/shamoon) ([#5667](https://github.com/paperless-ngx/paperless-ngx/pull/5667))
-   Feature: Allow tagging by putting barcodes on documents [@pkrahmer](https://github.com/pkrahmer) ([#5580](https://github.com/paperless-ngx/paperless-ngx/pull/5580))
-   Feature: Cache metadata and suggestions in Redis [@stumpylog](https://github.com/stumpylog) ([#5638](https://github.com/paperless-ngx/paperless-ngx/pull/5638))
-   Feature: Japanese translation [@shamoon](https://github.com/shamoon) ([#5641](https://github.com/paperless-ngx/paperless-ngx/pull/5641))
-   Feature: option for auto-remove inbox tags on save [@shamoon](https://github.com/shamoon) ([#5562](https://github.com/paperless-ngx/paperless-ngx/pull/5562))
-   Enhancement: allow paperless to run in read-only filesystem [@hegerdes](https://github.com/hegerdes) ([#5596](https://github.com/paperless-ngx/paperless-ngx/pull/5596))
-   Enhancement: mergeable bulk edit permissions [@shamoon](https://github.com/shamoon) ([#5508](https://github.com/paperless-ngx/paperless-ngx/pull/5508))
-   Enhancement: re-implement remote user auth for unsafe API requests as opt-in [@shamoon](https://github.com/shamoon) ([#5561](https://github.com/paperless-ngx/paperless-ngx/pull/5561))
-   Enhancement: Respect PDF cropbox for thumbnail generation [@henningBunk](https://github.com/henningBunk) ([#5531](https://github.com/paperless-ngx/paperless-ngx/pull/5531))

### Bug Fixes

-   Fix: Test metadata items for Unicode issues [@stumpylog](https://github.com/stumpylog) ([#5707](https://github.com/paperless-ngx/paperless-ngx/pull/5707))
-   Change: try to show preview even if metadata fails [@shamoon](https://github.com/shamoon) ([#5706](https://github.com/paperless-ngx/paperless-ngx/pull/5706))
-   Fix: only check workflow trigger source if not empty [@shamoon](https://github.com/shamoon) ([#5701](https://github.com/paperless-ngx/paperless-ngx/pull/5701))
-   Fix: frontend validation of number fields fails upon save [@shamoon](https://github.com/shamoon) ([#5646](https://github.com/paperless-ngx/paperless-ngx/pull/5646))
-   Fix: Explicit validation of custom field name unique constraint [@shamoon](https://github.com/shamoon) ([#5647](https://github.com/paperless-ngx/paperless-ngx/pull/5647))
-   Fix: Don't attempt to retrieve object types user doesn't have permissions to [@shamoon](https://github.com/shamoon) ([#5612](https://github.com/paperless-ngx/paperless-ngx/pull/5612))

### Documentation

-   Documentation: add detail about consumer polling behavior [@silmaril42](https://github.com/silmaril42) ([#5674](https://github.com/paperless-ngx/paperless-ngx/pull/5674))
-   Paperless-ngx Demo: new and improved [@shamoon](https://github.com/shamoon) ([#5639](https://github.com/paperless-ngx/paperless-ngx/pull/5639))
-   Documentation: Add docs about missing timezones in MySQL/MariaDB [@Programie](https://github.com/Programie) ([#5583](https://github.com/paperless-ngx/paperless-ngx/pull/5583))

### Maintenance

-   Chore(deps): Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#5629](https://github.com/paperless-ngx/paperless-ngx/pull/5629))
-   Chore(deps): Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#5597](https://github.com/paperless-ngx/paperless-ngx/pull/5597))

### Dependencies

<details>
<summary>9 changes</summary>

-   Chore: Backend dependencies update [@stumpylog](https://github.com/stumpylog) ([#5676](https://github.com/paperless-ngx/paperless-ngx/pull/5676))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.40.1 to 1.41.2 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.40.1 to 1.41.2 in /src-ui @dependabot) ([#5634](https://github.com/paperless-ngx/paperless-ngx/pull/5634))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#5630](https://github.com/paperless-ngx/paperless-ngx/pull/5630))
-   Chore(deps-dev): Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#5631](https://github.com/paperless-ngx/paperless-ngx/pull/5631))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#5632](https://github.com/paperless-ngx/paperless-ngx/pull/5632))
-   Chore(deps): Bump zone.js from 0.14.2 to 0.14.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5633](https://github.com/paperless-ngx/paperless-ngx/pull/5633))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.10.6 to 20.11.16 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.10.6 to 20.11.16 in /src-ui @dependabot) ([#5635](https://github.com/paperless-ngx/paperless-ngx/pull/5635))
-   Chore(deps): Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#5629](https://github.com/paperless-ngx/paperless-ngx/pull/5629))
-   Chore(deps): Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#5597](https://github.com/paperless-ngx/paperless-ngx/pull/5597))
</details>

### All App Changes

<details>
<summary>28 changes</summary>

-   Chore: Ensure all creations of directories create the parents too [@stumpylog](https://github.com/stumpylog) ([#5711](https://github.com/paperless-ngx/paperless-ngx/pull/5711))
-   Fix: Test metadata items for Unicode issues [@stumpylog](https://github.com/stumpylog) ([#5707](https://github.com/paperless-ngx/paperless-ngx/pull/5707))
-   Change: try to show preview even if metadata fails [@shamoon](https://github.com/shamoon) ([#5706](https://github.com/paperless-ngx/paperless-ngx/pull/5706))
-   Fix: only check workflow trigger source if not empty [@shamoon](https://github.com/shamoon) ([#5701](https://github.com/paperless-ngx/paperless-ngx/pull/5701))
-   Enhancement: confirm buttons [@shamoon](https://github.com/shamoon) ([#5680](https://github.com/paperless-ngx/paperless-ngx/pull/5680))
-   Enhancement: bulk delete objects [@shamoon](https://github.com/shamoon) ([#5688](https://github.com/paperless-ngx/paperless-ngx/pull/5688))
-   Chore: Backend dependencies update [@stumpylog](https://github.com/stumpylog) ([#5676](https://github.com/paperless-ngx/paperless-ngx/pull/5676))
-   Feature: OIDC \& social authentication [@mpflanzer](https://github.com/mpflanzer) ([#5190](https://github.com/paperless-ngx/paperless-ngx/pull/5190))
-   Chore: Don't write Python bytecode in the Docker image [@stumpylog](https://github.com/stumpylog) ([#5677](https://github.com/paperless-ngx/paperless-ngx/pull/5677))
-   Feature: allow create objects from bulk edit [@shamoon](https://github.com/shamoon) ([#5667](https://github.com/paperless-ngx/paperless-ngx/pull/5667))
-   Chore: Use memory cache backend in debug mode [@shamoon](https://github.com/shamoon) ([#5666](https://github.com/paperless-ngx/paperless-ngx/pull/5666))
-   Chore: Adds additional rules for Ruff linter [@stumpylog](https://github.com/stumpylog) ([#5660](https://github.com/paperless-ngx/paperless-ngx/pull/5660))
-   Feature: Allow tagging by putting barcodes on documents [@pkrahmer](https://github.com/pkrahmer) ([#5580](https://github.com/paperless-ngx/paperless-ngx/pull/5580))
-   Feature: Cache metadata and suggestions in Redis [@stumpylog](https://github.com/stumpylog) ([#5638](https://github.com/paperless-ngx/paperless-ngx/pull/5638))
-   Fix: frontend validation of number fields fails upon save [@shamoon](https://github.com/shamoon) ([#5646](https://github.com/paperless-ngx/paperless-ngx/pull/5646))
-   Fix: Explicit validation of custom field name unique constraint [@shamoon](https://github.com/shamoon) ([#5647](https://github.com/paperless-ngx/paperless-ngx/pull/5647))
-   Feature: Japanese translation [@shamoon](https://github.com/shamoon) ([#5641](https://github.com/paperless-ngx/paperless-ngx/pull/5641))
-   Chore(deps-dev): Bump [@<!---->playwright/test from 1.40.1 to 1.41.2 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.40.1 to 1.41.2 in /src-ui @dependabot) ([#5634](https://github.com/paperless-ngx/paperless-ngx/pull/5634))
-   Feature: option for auto-remove inbox tags on save [@shamoon](https://github.com/shamoon) ([#5562](https://github.com/paperless-ngx/paperless-ngx/pull/5562))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#5630](https://github.com/paperless-ngx/paperless-ngx/pull/5630))
-   Chore(deps-dev): Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#5631](https://github.com/paperless-ngx/paperless-ngx/pull/5631))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#5632](https://github.com/paperless-ngx/paperless-ngx/pull/5632))
-   Chore(deps): Bump zone.js from 0.14.2 to 0.14.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#5633](https://github.com/paperless-ngx/paperless-ngx/pull/5633))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.10.6 to 20.11.16 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.10.6 to 20.11.16 in /src-ui @dependabot) ([#5635](https://github.com/paperless-ngx/paperless-ngx/pull/5635))
-   Enhancement: mergeable bulk edit permissions [@shamoon](https://github.com/shamoon) ([#5508](https://github.com/paperless-ngx/paperless-ngx/pull/5508))
-   Enhancement: re-implement remote user auth for unsafe API requests as opt-in [@shamoon](https://github.com/shamoon) ([#5561](https://github.com/paperless-ngx/paperless-ngx/pull/5561))
-   Enhancement: Respect PDF cropbox for thumbnail generation [@henningBunk](https://github.com/henningBunk) ([#5531](https://github.com/paperless-ngx/paperless-ngx/pull/5531))
-   Fix: Don't attempt to retrieve object types user doesn't have permissions to [@shamoon](https://github.com/shamoon) ([#5612](https://github.com/paperless-ngx/paperless-ngx/pull/5612))
</details>

## paperless-ngx 2.4.3

### Bug Fixes

-   Fix: Ensure the scratch directory exists before consuming via the folder [@stumpylog](https://github.com/stumpylog) ([#5579](https://github.com/paperless-ngx/paperless-ngx/pull/5579))

### All App Changes

-   Fix: Ensure the scratch directory exists before consuming via the folder [@stumpylog](https://github.com/stumpylog) ([#5579](https://github.com/paperless-ngx/paperless-ngx/pull/5579))

## paperless-ngx 2.4.2

### Bug Fixes

-   Fix: improve one of the date matching regexes [@shamoon](https://github.com/shamoon) ([#5540](https://github.com/paperless-ngx/paperless-ngx/pull/5540))
-   Fix: tweak doc detail component behavior while awaiting metadata [@shamoon](https://github.com/shamoon) ([#5546](https://github.com/paperless-ngx/paperless-ngx/pull/5546))

### All App Changes

<details>
<summary>2 changes</summary>

-   Fix: improve one of the date matching regexes [@shamoon](https://github.com/shamoon) ([#5540](https://github.com/paperless-ngx/paperless-ngx/pull/5540))
-   Fix: tweak doc detail component behavior while awaiting metadata [@shamoon](https://github.com/shamoon) ([#5546](https://github.com/paperless-ngx/paperless-ngx/pull/5546))
</details>

## paperless-ngx 2.4.1

### Breaking Changes

-   Change: merge workflow permissions assignments instead of overwrite [@shamoon](https://github.com/shamoon) ([#5496](https://github.com/paperless-ngx/paperless-ngx/pull/5496))

### Bug Fixes

-   Fix: Minor frontend things in 2.4.0 [@shamoon](https://github.com/shamoon) ([#5514](https://github.com/paperless-ngx/paperless-ngx/pull/5514))
-   Fix: install script fails on alpine linux [@shamoon](https://github.com/shamoon) ([#5520](https://github.com/paperless-ngx/paperless-ngx/pull/5520))
-   Fix: enforce permissions for app config [@shamoon](https://github.com/shamoon) ([#5516](https://github.com/paperless-ngx/paperless-ngx/pull/5516))
-   Fix: render images not converted to pdf, refactor doc detail rendering [@shamoon](https://github.com/shamoon) ([#5475](https://github.com/paperless-ngx/paperless-ngx/pull/5475))
-   Fix: Dont parse numbers with exponent as integer [@shamoon](https://github.com/shamoon) ([#5457](https://github.com/paperless-ngx/paperless-ngx/pull/5457))

### Maintenance

-   Chore: Build fix- branches [@shamoon](https://github.com/shamoon) ([#5501](https://github.com/paperless-ngx/paperless-ngx/pull/5501))

### Dependencies

-   Chore(deps-dev): Bump the development group with 1 update [@dependabot](https://github.com/dependabot) ([#5503](https://github.com/paperless-ngx/paperless-ngx/pull/5503))

### All App Changes

<details>
<summary>7 changes</summary>

-   Revert "Enhancement: support remote user auth directly against API (DRF)" @shamoon ([#5534](https://github.com/paperless-ngx/paperless-ngx/pull/5534))
-   Fix: Minor frontend things in 2.4.0 [@shamoon](https://github.com/shamoon) ([#5514](https://github.com/paperless-ngx/paperless-ngx/pull/5514))
-   Fix: enforce permissions for app config [@shamoon](https://github.com/shamoon) ([#5516](https://github.com/paperless-ngx/paperless-ngx/pull/5516))
-   Change: merge workflow permissions assignments instead of overwrite [@shamoon](https://github.com/shamoon) ([#5496](https://github.com/paperless-ngx/paperless-ngx/pull/5496))
-   Chore(deps-dev): Bump the development group with 1 update [@dependabot](https://github.com/dependabot) ([#5503](https://github.com/paperless-ngx/paperless-ngx/pull/5503))
-   Fix: render images not converted to pdf, refactor doc detail rendering [@shamoon](https://github.com/shamoon) ([#5475](https://github.com/paperless-ngx/paperless-ngx/pull/5475))
-   Fix: Dont parse numbers with exponent as integer [@shamoon](https://github.com/shamoon) ([#5457](https://github.com/paperless-ngx/paperless-ngx/pull/5457))
</details>

## paperless-ngx 2.4.0

### Features

-   Enhancement: support remote user auth directly against API (DRF) [@shamoon](https://github.com/shamoon) ([#5386](https://github.com/paperless-ngx/paperless-ngx/pull/5386))
-   Feature: Add additional caching support to suggestions and metadata [@stumpylog](https://github.com/stumpylog) ([#5414](https://github.com/paperless-ngx/paperless-ngx/pull/5414))
-   Feature: help tooltips [@shamoon](https://github.com/shamoon) ([#5383](https://github.com/paperless-ngx/paperless-ngx/pull/5383))
-   Enhancement: warn when outdated doc detected [@shamoon](https://github.com/shamoon) ([#5372](https://github.com/paperless-ngx/paperless-ngx/pull/5372))
-   Feature: app branding [@shamoon](https://github.com/shamoon) ([#5357](https://github.com/paperless-ngx/paperless-ngx/pull/5357))

### Bug Fixes

-   Fix: doc link removal when has never been assigned [@shamoon](https://github.com/shamoon) ([#5451](https://github.com/paperless-ngx/paperless-ngx/pull/5451))
-   Fix: dont lose permissions ui if owner changed from [@shamoon](https://github.com/shamoon) ([#5433](https://github.com/paperless-ngx/paperless-ngx/pull/5433))
-   Fix: Getting next ASN when no documents have an ASN [@stumpylog](https://github.com/stumpylog) ([#5431](https://github.com/paperless-ngx/paperless-ngx/pull/5431))
-   Fix: signin username floating label [@shamoon](https://github.com/shamoon) ([#5424](https://github.com/paperless-ngx/paperless-ngx/pull/5424))
-   Fix: shared by me filter with multiple users / groups in postgres [@shamoon](https://github.com/shamoon) ([#5396](https://github.com/paperless-ngx/paperless-ngx/pull/5396))
-   Fix: Catch new warning when loading the classifier [@stumpylog](https://github.com/stumpylog) ([#5395](https://github.com/paperless-ngx/paperless-ngx/pull/5395))
-   Fix: doc detail component fixes [@shamoon](https://github.com/shamoon) ([#5373](https://github.com/paperless-ngx/paperless-ngx/pull/5373))

### Maintenance

-   Chore: better bootstrap icons [@shamoon](https://github.com/shamoon) ([#5403](https://github.com/paperless-ngx/paperless-ngx/pull/5403))
-   Chore: Close outdated support / general discussions [@shamoon](https://github.com/shamoon) ([#5443](https://github.com/paperless-ngx/paperless-ngx/pull/5443))

### Dependencies

-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#5413](https://github.com/paperless-ngx/paperless-ngx/pull/5413))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5412](https://github.com/paperless-ngx/paperless-ngx/pull/5412))
-   Chore(deps-dev): Bump jinja2 from 3.1.2 to 3.1.3 [@dependabot](https://github.com/dependabot) ([#5352](https://github.com/paperless-ngx/paperless-ngx/pull/5352))

### All App Changes

<details>
<summary>16 changes</summary>

-   Fix: doc link removal when has never been assigned [@shamoon](https://github.com/shamoon) ([#5451](https://github.com/paperless-ngx/paperless-ngx/pull/5451))
-   Chore: better bootstrap icons [@shamoon](https://github.com/shamoon) ([#5403](https://github.com/paperless-ngx/paperless-ngx/pull/5403))
-   Fix: dont lose permissions ui if owner changed from [@shamoon](https://github.com/shamoon) ([#5433](https://github.com/paperless-ngx/paperless-ngx/pull/5433))
-   Enhancement: support remote user auth directly against API (DRF) [@shamoon](https://github.com/shamoon) ([#5386](https://github.com/paperless-ngx/paperless-ngx/pull/5386))
-   Fix: Getting next ASN when no documents have an ASN [@stumpylog](https://github.com/stumpylog) ([#5431](https://github.com/paperless-ngx/paperless-ngx/pull/5431))
-   Feature: Add additional caching support to suggestions and metadata [@stumpylog](https://github.com/stumpylog) ([#5414](https://github.com/paperless-ngx/paperless-ngx/pull/5414))
-   Chore(deps): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#5413](https://github.com/paperless-ngx/paperless-ngx/pull/5413))
-   Chore(deps-dev): Bump the development group with 2 updates [@dependabot](https://github.com/dependabot) ([#5412](https://github.com/paperless-ngx/paperless-ngx/pull/5412))
-   Fix: signin username floating label [@shamoon](https://github.com/shamoon) ([#5424](https://github.com/paperless-ngx/paperless-ngx/pull/5424))
-   Feature: help tooltips [@shamoon](https://github.com/shamoon) ([#5383](https://github.com/paperless-ngx/paperless-ngx/pull/5383))
-   Enhancement / QoL: show selected tasks count [@shamoon](https://github.com/shamoon) ([#5379](https://github.com/paperless-ngx/paperless-ngx/pull/5379))
-   Fix: shared by me filter with multiple users / groups in postgres [@shamoon](https://github.com/shamoon) ([#5396](https://github.com/paperless-ngx/paperless-ngx/pull/5396))
-   Fix: doc detail component fixes [@shamoon](https://github.com/shamoon) ([#5373](https://github.com/paperless-ngx/paperless-ngx/pull/5373))
-   Enhancement: warn when outdated doc detected [@shamoon](https://github.com/shamoon) ([#5372](https://github.com/paperless-ngx/paperless-ngx/pull/5372))
-   Feature: app branding [@shamoon](https://github.com/shamoon) ([#5357](https://github.com/paperless-ngx/paperless-ngx/pull/5357))
-   Chore: Initial refactor of consume task [@stumpylog](https://github.com/stumpylog) ([#5367](https://github.com/paperless-ngx/paperless-ngx/pull/5367))
</details>

## paperless-ngx 2.3.3

### Enhancements

-   Enhancement: Explain behavior of unset app config boolean to user [@shamoon](https://github.com/shamoon) ([#5345](https://github.com/paperless-ngx/paperless-ngx/pull/5345))
-   Enhancement: title assignment placeholder error handling, fallback [@shamoon](https://github.com/shamoon) ([#5282](https://github.com/paperless-ngx/paperless-ngx/pull/5282))

### Bug Fixes

-   Fix: Don't require the JSON user arguments field, interpret empty string as [@stumpylog](https://github.com/stumpylog) ([#5320](https://github.com/paperless-ngx/paperless-ngx/pull/5320))

### Maintenance

-   Chore: Backend dependencies update [@stumpylog](https://github.com/stumpylog) ([#5336](https://github.com/paperless-ngx/paperless-ngx/pull/5336))
-   Chore: add pre-commit hook for codespell [@shamoon](https://github.com/shamoon) ([#5324](https://github.com/paperless-ngx/paperless-ngx/pull/5324))

### All App Changes

<details>
<summary>5 changes</summary>

-   Enhancement: Explain behavior of unset app config boolean to user [@shamoon](https://github.com/shamoon) ([#5345](https://github.com/paperless-ngx/paperless-ngx/pull/5345))
-   Enhancement: title assignment placeholder error handling, fallback [@shamoon](https://github.com/shamoon) ([#5282](https://github.com/paperless-ngx/paperless-ngx/pull/5282))
-   Chore: Backend dependencies update [@stumpylog](https://github.com/stumpylog) ([#5336](https://github.com/paperless-ngx/paperless-ngx/pull/5336))
-   Fix: Don't require the JSON user arguments field, interpret empty string as [@stumpylog](https://github.com/stumpylog) ([#5320](https://github.com/paperless-ngx/paperless-ngx/pull/5320))
-   Chore: add pre-commit hook for codespell [@shamoon](https://github.com/shamoon) ([#5324](https://github.com/paperless-ngx/paperless-ngx/pull/5324))
</details>

## paperless-ngx 2.3.2

### Bug Fixes

-   Fix: triggered workflow assignment of customfield fails if field exists in v2.3.1 [@shamoon](https://github.com/shamoon) ([#5302](https://github.com/paperless-ngx/paperless-ngx/pull/5302))
-   Fix: Decoding of user arguments for OCR [@stumpylog](https://github.com/stumpylog) ([#5307](https://github.com/paperless-ngx/paperless-ngx/pull/5307))
-   Fix: empty workflow trigger match field cannot be saved in v.2.3.1 [@shamoon](https://github.com/shamoon) ([#5301](https://github.com/paperless-ngx/paperless-ngx/pull/5301))
-   Fix: Use local time for added/updated workflow triggers [@stumpylog](https://github.com/stumpylog) ([#5304](https://github.com/paperless-ngx/paperless-ngx/pull/5304))
-   Fix: workflow edit form loses unsaved changes [@shamoon](https://github.com/shamoon) ([#5299](https://github.com/paperless-ngx/paperless-ngx/pull/5299))

### All App Changes

<details>
<summary>5 changes</summary>

-   Fix: triggered workflow assignment of customfield fails if field exists in v2.3.1 [@shamoon](https://github.com/shamoon) ([#5302](https://github.com/paperless-ngx/paperless-ngx/pull/5302))
-   Fix: Decoding of user arguments for OCR [@stumpylog](https://github.com/stumpylog) ([#5307](https://github.com/paperless-ngx/paperless-ngx/pull/5307))
-   Fix: empty workflow trigger match field cannot be saved in v.2.3.1 [@shamoon](https://github.com/shamoon) ([#5301](https://github.com/paperless-ngx/paperless-ngx/pull/5301))
-   Fix: Use local time for added/updated workflow triggers [@stumpylog](https://github.com/stumpylog) ([#5304](https://github.com/paperless-ngx/paperless-ngx/pull/5304))
-   Fix: workflow edit form loses unsaved changes [@shamoon](https://github.com/shamoon) ([#5299](https://github.com/paperless-ngx/paperless-ngx/pull/5299))
</details>

## paperless-ngx 2.3.1

### Bug Fixes

-   Fix: edit workflow form not displaying trigger settings [@shamoon](https://github.com/shamoon) ([#5276](https://github.com/paperless-ngx/paperless-ngx/pull/5276))
-   Fix: Prevent passing 0 pages to OCRMyPDF [@stumpylog](https://github.com/stumpylog) ([#5275](https://github.com/paperless-ngx/paperless-ngx/pull/5275))

### All App Changes

<details>
<summary>2 changes</summary>

-   Fix: edit workflow form not displaying trigger settings [@shamoon](https://github.com/shamoon) ([#5276](https://github.com/paperless-ngx/paperless-ngx/pull/5276))
-   Fix: Prevent passing 0 pages to OCRMyPDF [@stumpylog](https://github.com/stumpylog) ([#5275](https://github.com/paperless-ngx/paperless-ngx/pull/5275))
</details>

## paperless-ngx 2.3.0

### Notable Changes

-   Feature: Workflows [@shamoon](https://github.com/shamoon) ([#5121](https://github.com/paperless-ngx/paperless-ngx/pull/5121))
-   Feature: Allow setting backend configuration settings via the UI [@stumpylog](https://github.com/stumpylog) ([#5126](https://github.com/paperless-ngx/paperless-ngx/pull/5126))

### Features

-   Feature: Workflows [@shamoon](https://github.com/shamoon) ([#5121](https://github.com/paperless-ngx/paperless-ngx/pull/5121))
-   Feature: Allow setting backend configuration settings via the UI [@stumpylog](https://github.com/stumpylog) ([#5126](https://github.com/paperless-ngx/paperless-ngx/pull/5126))
-   Enhancement: fetch mails in bulk [@falkenbt](https://github.com/falkenbt) ([#5249](https://github.com/paperless-ngx/paperless-ngx/pull/5249))
-   Enhancement: add parameter to post_document API [@bevanjkay](https://github.com/bevanjkay) ([#5217](https://github.com/paperless-ngx/paperless-ngx/pull/5217))

### Bug Fixes

-   Chore: Replaces deprecated Django alias with standard library [@stumpylog](https://github.com/stumpylog) ([#5262](https://github.com/paperless-ngx/paperless-ngx/pull/5262))
-   Fix: Crash in barcode ASN reading when the file type isn't supported [@stumpylog](https://github.com/stumpylog) ([#5261](https://github.com/paperless-ngx/paperless-ngx/pull/5261))
-   Fix: Allows pre-consume scripts to modify the working path again [@stumpylog](https://github.com/stumpylog) ([#5260](https://github.com/paperless-ngx/paperless-ngx/pull/5260))
-   Change: Use fnmatch for more sane workflow path matching [@shamoon](https://github.com/shamoon) ([#5250](https://github.com/paperless-ngx/paperless-ngx/pull/5250))
-   Fix: zip exports not respecting the --delete option [@stumpylog](https://github.com/stumpylog) ([#5245](https://github.com/paperless-ngx/paperless-ngx/pull/5245))
-   Fix: correctly format tip admonition [@ChrisRBe](https://github.com/ChrisRBe) ([#5229](https://github.com/paperless-ngx/paperless-ngx/pull/5229))
-   Fix: filename format remove none when part of directory [@shamoon](https://github.com/shamoon) ([#5210](https://github.com/paperless-ngx/paperless-ngx/pull/5210))
-   Fix: Improve Performance for Listing and Paginating Documents [@antoinelibert](https://github.com/antoinelibert) ([#5195](https://github.com/paperless-ngx/paperless-ngx/pull/5195))
-   Fix: Disable custom field remove button if user does not have permissions [@shamoon](https://github.com/shamoon) ([#5194](https://github.com/paperless-ngx/paperless-ngx/pull/5194))
-   Fix: overlapping button focus highlight on login [@shamoon](https://github.com/shamoon) ([#5193](https://github.com/paperless-ngx/paperless-ngx/pull/5193))
-   Fix: symmetric doc links with target doc value None [@shamoon](https://github.com/shamoon) ([#5187](https://github.com/paperless-ngx/paperless-ngx/pull/5187))
-   Fix: setting empty doc link with docs to be removed [@shamoon](https://github.com/shamoon) ([#5174](https://github.com/paperless-ngx/paperless-ngx/pull/5174))
-   Enhancement: improve validation of custom field values [@shamoon](https://github.com/shamoon) ([#5166](https://github.com/paperless-ngx/paperless-ngx/pull/5166))
-   Fix: type casting of db values for 'shared by me' filter [@shamoon](https://github.com/shamoon) ([#5155](https://github.com/paperless-ngx/paperless-ngx/pull/5155))

### Documentation

-   Fix: correctly format tip admonition [@ChrisRBe](https://github.com/ChrisRBe) ([#5229](https://github.com/paperless-ngx/paperless-ngx/pull/5229))

### Maintenance

-   Chore(deps): Bump the actions group with 5 updates [@dependabot](https://github.com/dependabot) ([#5203](https://github.com/paperless-ngx/paperless-ngx/pull/5203))

### Dependencies

<details>
<summary>4 changes</summary>

-   Chore(deps): Bump the actions group with 5 updates [@dependabot](https://github.com/dependabot) ([#5203](https://github.com/paperless-ngx/paperless-ngx/pull/5203))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 10 updates [@dependabot](https://github.com/dependabot) ([#5204](https://github.com/paperless-ngx/paperless-ngx/pull/5204))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.10.4 to 20.10.6 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.10.4 to 20.10.6 in /src-ui @dependabot) ([#5207](https://github.com/paperless-ngx/paperless-ngx/pull/5207))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#5205](https://github.com/paperless-ngx/paperless-ngx/pull/5205))
</details>

### All App Changes

<details>
<summary>21 changes</summary>

-   Chore: Replaces deprecated Django alias with standard library [@stumpylog](https://github.com/stumpylog) ([#5262](https://github.com/paperless-ngx/paperless-ngx/pull/5262))
-   Fix: Crash in barcode ASN reading when the file type isn't supported [@stumpylog](https://github.com/stumpylog) ([#5261](https://github.com/paperless-ngx/paperless-ngx/pull/5261))
-   Fix: Allows pre-consume scripts to modify the working path again [@stumpylog](https://github.com/stumpylog) ([#5260](https://github.com/paperless-ngx/paperless-ngx/pull/5260))
-   Enhancement: add basic filters for listing of custom fields [@shamoon](https://github.com/shamoon) ([#5257](https://github.com/paperless-ngx/paperless-ngx/pull/5257))
-   Change: Use fnmatch for more sane workflow path matching [@shamoon](https://github.com/shamoon) ([#5250](https://github.com/paperless-ngx/paperless-ngx/pull/5250))
-   Enhancement: fetch mails in bulk [@falkenbt](https://github.com/falkenbt) ([#5249](https://github.com/paperless-ngx/paperless-ngx/pull/5249))
-   Fix: zip exports not respecting the --delete option [@stumpylog](https://github.com/stumpylog) ([#5245](https://github.com/paperless-ngx/paperless-ngx/pull/5245))
-   Enhancement: add parameter to post_document API [@bevanjkay](https://github.com/bevanjkay) ([#5217](https://github.com/paperless-ngx/paperless-ngx/pull/5217))
-   Feature: Workflows [@shamoon](https://github.com/shamoon) ([#5121](https://github.com/paperless-ngx/paperless-ngx/pull/5121))
-   Fix: filename format remove none when part of directory [@shamoon](https://github.com/shamoon) ([#5210](https://github.com/paperless-ngx/paperless-ngx/pull/5210))
-   Chore(deps): Bump the frontend-angular-dependencies group in /src-ui with 10 updates [@dependabot](https://github.com/dependabot) ([#5204](https://github.com/paperless-ngx/paperless-ngx/pull/5204))
-   Chore(deps-dev): Bump [@<!---->types/node from 20.10.4 to 20.10.6 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.10.4 to 20.10.6 in /src-ui @dependabot) ([#5207](https://github.com/paperless-ngx/paperless-ngx/pull/5207))
-   Chore(deps-dev): Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#5205](https://github.com/paperless-ngx/paperless-ngx/pull/5205))
-   Fix: Improve Performance for Listing and Paginating Documents [@antoinelibert](https://github.com/antoinelibert) ([#5195](https://github.com/paperless-ngx/paperless-ngx/pull/5195))
-   Fix: Disable custom field remove button if user does not have permissions [@shamoon](https://github.com/shamoon) ([#5194](https://github.com/paperless-ngx/paperless-ngx/pull/5194))
-   Fix: overlapping button focus highlight on login [@shamoon](https://github.com/shamoon) ([#5193](https://github.com/paperless-ngx/paperless-ngx/pull/5193))
-   Fix: symmetric doc links with target doc value None [@shamoon](https://github.com/shamoon) ([#5187](https://github.com/paperless-ngx/paperless-ngx/pull/5187))
-   Fix: setting empty doc link with docs to be removed [@shamoon](https://github.com/shamoon) ([#5174](https://github.com/paperless-ngx/paperless-ngx/pull/5174))
-   Feature: Allow setting backend configuration settings via the UI [@stumpylog](https://github.com/stumpylog) ([#5126](https://github.com/paperless-ngx/paperless-ngx/pull/5126))
-   Enhancement: improve validation of custom field values [@shamoon](https://github.com/shamoon) ([#5166](https://github.com/paperless-ngx/paperless-ngx/pull/5166))
-   Fix: type casting of db values for 'shared by me' filter [@shamoon](https://github.com/shamoon) ([#5155](https://github.com/paperless-ngx/paperless-ngx/pull/5155))
</details>

## paperless-ngx 2.2.1

### Bug Fixes

-   Fix: saving doc links with no value [@shamoon](https://github.com/shamoon) ([#5144](https://github.com/paperless-ngx/paperless-ngx/pull/5144))
-   Fix: allow multiple consumption templates to assign the same custom field [@shamoon](https://github.com/shamoon) ([#5142](https://github.com/paperless-ngx/paperless-ngx/pull/5142))
-   Fix: some dropdowns broken in 2.2.0 [@shamoon](https://github.com/shamoon) ([#5134](https://github.com/paperless-ngx/paperless-ngx/pull/5134))

### All App Changes

<details>
<summary>3 changes</summary>

-   Fix: saving doc links with no value [@shamoon](https://github.com/shamoon) ([#5144](https://github.com/paperless-ngx/paperless-ngx/pull/5144))
-   Fix: allow multiple consumption templates to assign the same custom field [@shamoon](https://github.com/shamoon) ([#5142](https://github.com/paperless-ngx/paperless-ngx/pull/5142))
-   Fix: some dropdowns broken in 2.2.0 [@shamoon](https://github.com/shamoon) ([#5134](https://github.com/paperless-ngx/paperless-ngx/pull/5134))
</details>

## paperless-ngx 2.2.0

### Features

-   Enhancement: Add tooltip for select dropdown items [@shamoon](https://github.com/shamoon) ([#5070](https://github.com/paperless-ngx/paperless-ngx/pull/5070))
-   Chore: Update Angular to v17 including new Angular control-flow [@shamoon](https://github.com/shamoon) ([#4980](https://github.com/paperless-ngx/paperless-ngx/pull/4980))
-   Enhancement: symmetric document links [@shamoon](https://github.com/shamoon) ([#4907](https://github.com/paperless-ngx/paperless-ngx/pull/4907))
-   Enhancement: shared icon \& shared by me filter [@shamoon](https://github.com/shamoon) ([#4859](https://github.com/paperless-ngx/paperless-ngx/pull/4859))
-   Enhancement: Improved popup preview, respect embedded viewer, error handling [@shamoon](https://github.com/shamoon) ([#4947](https://github.com/paperless-ngx/paperless-ngx/pull/4947))
-   Enhancement: Allow deletion of documents via the fuzzy matching command [@stumpylog](https://github.com/stumpylog) ([#4957](https://github.com/paperless-ngx/paperless-ngx/pull/4957))
-   Enhancement: document link field fixes [@shamoon](https://github.com/shamoon) ([#5020](https://github.com/paperless-ngx/paperless-ngx/pull/5020))
-   Enhancement: above and below doc detail save buttons [@shamoon](https://github.com/shamoon) ([#5008](https://github.com/paperless-ngx/paperless-ngx/pull/5008))

### Bug Fixes

-   Fix: Case where a mail attachment has no filename to use [@stumpylog](https://github.com/stumpylog) ([#5117](https://github.com/paperless-ngx/paperless-ngx/pull/5117))
-   Fix: Disable auto-login for API token requests [@shamoon](https://github.com/shamoon) ([#5094](https://github.com/paperless-ngx/paperless-ngx/pull/5094))
-   Fix: update ASN regex to support Unicode [@eukub](https://github.com/eukub) ([#5099](https://github.com/paperless-ngx/paperless-ngx/pull/5099))
-   Fix: ensure CSRF-Token on Index view [@baflo](https://github.com/baflo) ([#5082](https://github.com/paperless-ngx/paperless-ngx/pull/5082))
-   Fix: Stop auto-refresh logs / tasks after close [@shamoon](https://github.com/shamoon) ([#5089](https://github.com/paperless-ngx/paperless-ngx/pull/5089))
-   Fix: Make the admin panel accessible when using a large number of documents [@bogdal](https://github.com/bogdal) ([#5052](https://github.com/paperless-ngx/paperless-ngx/pull/5052))
-   Fix: dont allow null property via API [@shamoon](https://github.com/shamoon) ([#5063](https://github.com/paperless-ngx/paperless-ngx/pull/5063))
-   Fix: Updates Ghostscript to 10.02.1 for more bug fixes to it [@stumpylog](https://github.com/stumpylog) ([#5040](https://github.com/paperless-ngx/paperless-ngx/pull/5040))
-   Fix: allow system keyboard shortcuts in date fields [@shamoon](https://github.com/shamoon) ([#5009](https://github.com/paperless-ngx/paperless-ngx/pull/5009))
-   Fix password change detection on profile edit [@shamoon](https://github.com/shamoon) ([#5028](https://github.com/paperless-ngx/paperless-ngx/pull/5028))

### Documentation

-   Documentation: organize API endpoints [@dgsponer](https://github.com/dgsponer) ([#5077](https://github.com/paperless-ngx/paperless-ngx/pull/5077))

### Maintenance

-   Chore: Bulk backend update [@stumpylog](https://github.com/stumpylog) ([#5061](https://github.com/paperless-ngx/paperless-ngx/pull/5061))

### Dependencies

<details>
<summary>5 changes</summary>

-   Chore: Bulk backend update [@stumpylog](https://github.com/stumpylog) ([#5061](https://github.com/paperless-ngx/paperless-ngx/pull/5061))
-   Chore(deps): Bump the django group with 3 updates [@dependabot](https://github.com/dependabot) ([#5046](https://github.com/paperless-ngx/paperless-ngx/pull/5046))
-   Chore(deps): Bump the major-versions group with 1 update [@dependabot](https://github.com/dependabot) ([#5047](https://github.com/paperless-ngx/paperless-ngx/pull/5047))
-   Chore(deps): Bump the small-changes group with 6 updates [@dependabot](https://github.com/dependabot) ([#5048](https://github.com/paperless-ngx/paperless-ngx/pull/5048))
-   Fix: Updates Ghostscript to 10.02.1 for more bug fixes to it [@stumpylog](https://github.com/stumpylog) ([#5040](https://github.com/paperless-ngx/paperless-ngx/pull/5040))
</details>

### All App Changes

<details>
<summary>20 changes</summary>

-   Fix: Case where a mail attachment has no filename to use [@stumpylog](https://github.com/stumpylog) ([#5117](https://github.com/paperless-ngx/paperless-ngx/pull/5117))
-   Fix: Disable auto-login for API token requests [@shamoon](https://github.com/shamoon) ([#5094](https://github.com/paperless-ngx/paperless-ngx/pull/5094))
-   Fix: update ASN regex to support Unicode [@eukub](https://github.com/eukub) ([#5099](https://github.com/paperless-ngx/paperless-ngx/pull/5099))
-   Fix: ensure CSRF-Token on Index view [@baflo](https://github.com/baflo) ([#5082](https://github.com/paperless-ngx/paperless-ngx/pull/5082))
-   Fix: Stop auto-refresh logs / tasks after close [@shamoon](https://github.com/shamoon) ([#5089](https://github.com/paperless-ngx/paperless-ngx/pull/5089))
-   Enhancement: Add tooltip for select dropdown items [@shamoon](https://github.com/shamoon) ([#5070](https://github.com/paperless-ngx/paperless-ngx/pull/5070))
-   Fix: Make the admin panel accessible when using a large number of documents [@bogdal](https://github.com/bogdal) ([#5052](https://github.com/paperless-ngx/paperless-ngx/pull/5052))
-   Chore: Update Angular to v17 including new Angular control-flow [@shamoon](https://github.com/shamoon) ([#4980](https://github.com/paperless-ngx/paperless-ngx/pull/4980))
-   Fix: dont allow null property via API [@shamoon](https://github.com/shamoon) ([#5063](https://github.com/paperless-ngx/paperless-ngx/pull/5063))
-   Enhancement: symmetric document links [@shamoon](https://github.com/shamoon) ([#4907](https://github.com/paperless-ngx/paperless-ngx/pull/4907))
-   Enhancement: shared icon \& shared by me filter [@shamoon](https://github.com/shamoon) ([#4859](https://github.com/paperless-ngx/paperless-ngx/pull/4859))
-   Chore(deps): Bump the django group with 3 updates [@dependabot](https://github.com/dependabot) ([#5046](https://github.com/paperless-ngx/paperless-ngx/pull/5046))
-   Chore(deps): Bump the major-versions group with 1 update [@dependabot](https://github.com/dependabot) ([#5047](https://github.com/paperless-ngx/paperless-ngx/pull/5047))
-   Chore(deps): Bump the small-changes group with 6 updates [@dependabot](https://github.com/dependabot) ([#5048](https://github.com/paperless-ngx/paperless-ngx/pull/5048))
-   Enhancement: Improved popup preview, respect embedded viewer, error handling [@shamoon](https://github.com/shamoon) ([#4947](https://github.com/paperless-ngx/paperless-ngx/pull/4947))
-   Enhancement: Add {original_filename}, {added_time} to title placeholders [@TTT7275](https://github.com/TTT7275) ([#4972](https://github.com/paperless-ngx/paperless-ngx/pull/4972))
-   Feature: Allow deletion of documents via the fuzzy matching command [@stumpylog](https://github.com/stumpylog) ([#4957](https://github.com/paperless-ngx/paperless-ngx/pull/4957))
-   Fix: allow system keyboard shortcuts in date fields [@shamoon](https://github.com/shamoon) ([#5009](https://github.com/paperless-ngx/paperless-ngx/pull/5009))
-   Enhancement: document link field fixes [@shamoon](https://github.com/shamoon) ([#5020](https://github.com/paperless-ngx/paperless-ngx/pull/5020))
-   Fix password change detection on profile edit [@shamoon](https://github.com/shamoon) ([#5028](https://github.com/paperless-ngx/paperless-ngx/pull/5028))
</details>

## paperless-ngx 2.1.3

### Bug Fixes

-   Fix: Document metadata is lost during barcode splitting [@stumpylog](https://github.com/stumpylog) ([#4982](https://github.com/paperless-ngx/paperless-ngx/pull/4982))
-   Fix: Export of custom field instances during a split manifest export [@stumpylog](https://github.com/stumpylog) ([#4984](https://github.com/paperless-ngx/paperless-ngx/pull/4984))
-   Fix: Apply user arguments even in the case of the forcing OCR [@stumpylog](https://github.com/stumpylog) ([#4981](https://github.com/paperless-ngx/paperless-ngx/pull/4981))
-   Fix: support show errors for select dropdowns [@shamoon](https://github.com/shamoon) ([#4979](https://github.com/paperless-ngx/paperless-ngx/pull/4979))
-   Fix: Don't attempt to parse none objects during date searching [@bogdal](https://github.com/bogdal) ([#4977](https://github.com/paperless-ngx/paperless-ngx/pull/4977))

### All App Changes

<details>
<summary>6 changes</summary>

-   Refactor: Boost performance by reducing db queries [@bogdal](https://github.com/bogdal) ([#4990](https://github.com/paperless-ngx/paperless-ngx/pull/4990))
-   Fix: Document metadata is lost during barcode splitting [@stumpylog](https://github.com/stumpylog) ([#4982](https://github.com/paperless-ngx/paperless-ngx/pull/4982))
-   Fix: Export of custom field instances during a split manifest export [@stumpylog](https://github.com/stumpylog) ([#4984](https://github.com/paperless-ngx/paperless-ngx/pull/4984))
-   Fix: Apply user arguments even in the case of the forcing OCR [@stumpylog](https://github.com/stumpylog) ([#4981](https://github.com/paperless-ngx/paperless-ngx/pull/4981))
-   Fix: support show errors for select dropdowns [@shamoon](https://github.com/shamoon) ([#4979](https://github.com/paperless-ngx/paperless-ngx/pull/4979))
-   Fix: Don't attempt to parse none objects during date searching [@bogdal](https://github.com/bogdal) ([#4977](https://github.com/paperless-ngx/paperless-ngx/pull/4977))
</details>

## paperless-ngx 2.1.2

### Bug Fixes

-   Fix: sort consumption templates by order by default [@shamoon](https://github.com/shamoon) ([#4956](https://github.com/paperless-ngx/paperless-ngx/pull/4956))
-   Fix: Updates gotenberg-client, including workaround for Gotenberg non-latin handling [@stumpylog](https://github.com/stumpylog) ([#4944](https://github.com/paperless-ngx/paperless-ngx/pull/4944))
-   Fix: allow text copy in pngx pdf viewer [@shamoon](https://github.com/shamoon) ([#4938](https://github.com/paperless-ngx/paperless-ngx/pull/4938))
-   Fix: Don't allow autocomplete searches to fail on schema field matches [@stumpylog](https://github.com/stumpylog) ([#4934](https://github.com/paperless-ngx/paperless-ngx/pull/4934))
-   Fix: Convert search dates to UTC in advanced search [@bogdal](https://github.com/bogdal) ([#4891](https://github.com/paperless-ngx/paperless-ngx/pull/4891))
-   Fix: Use the attachment filename so downstream template matching works [@stumpylog](https://github.com/stumpylog) ([#4931](https://github.com/paperless-ngx/paperless-ngx/pull/4931))
-   Fix: frontend handle autocomplete failure gracefully [@shamoon](https://github.com/shamoon) ([#4903](https://github.com/paperless-ngx/paperless-ngx/pull/4903))

### Dependencies

-   Chore(deps-dev): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#4942](https://github.com/paperless-ngx/paperless-ngx/pull/4942))
-   Chore(deps-dev): Bump the development group with 1 update [@dependabot](https://github.com/dependabot) ([#4939](https://github.com/paperless-ngx/paperless-ngx/pull/4939))

### All App Changes

<details>
<summary>9 changes</summary>

-   Fix: sort consumption templates by order by default [@shamoon](https://github.com/shamoon) ([#4956](https://github.com/paperless-ngx/paperless-ngx/pull/4956))
-   Chore: reorganize api tests [@shamoon](https://github.com/shamoon) ([#4935](https://github.com/paperless-ngx/paperless-ngx/pull/4935))
-   Chore(deps-dev): Bump the small-changes group with 2 updates [@dependabot](https://github.com/dependabot) ([#4942](https://github.com/paperless-ngx/paperless-ngx/pull/4942))
-   Fix: allow text copy in pngx pdf viewer [@shamoon](https://github.com/shamoon) ([#4938](https://github.com/paperless-ngx/paperless-ngx/pull/4938))
-   Chore(deps-dev): Bump the development group with 1 update [@dependabot](https://github.com/dependabot) ([#4939](https://github.com/paperless-ngx/paperless-ngx/pull/4939))
-   Fix: Don't allow autocomplete searches to fail on schema field matches [@stumpylog](https://github.com/stumpylog) ([#4934](https://github.com/paperless-ngx/paperless-ngx/pull/4934))
-   Fix: Convert search dates to UTC in advanced search [@bogdal](https://github.com/bogdal) ([#4891](https://github.com/paperless-ngx/paperless-ngx/pull/4891))
-   Fix: Use the attachment filename so downstream template matching works [@stumpylog](https://github.com/stumpylog) ([#4931](https://github.com/paperless-ngx/paperless-ngx/pull/4931))
-   Fix: frontend handle autocomplete failure gracefully [@shamoon](https://github.com/shamoon) ([#4903](https://github.com/paperless-ngx/paperless-ngx/pull/4903))
</details>

## paperless-ngx 2.1.1

### Bug Fixes

-   Fix: disable toggle for share link creation without archive version, fix auto-copy in Safari [@shamoon](https://github.com/shamoon) ([#4885](https://github.com/paperless-ngx/paperless-ngx/pull/4885))
-   Fix: storage paths link incorrect in dashboard widget [@shamoon](https://github.com/shamoon) ([#4878](https://github.com/paperless-ngx/paperless-ngx/pull/4878))
-   Fix: respect baseURI for pdfjs worker URL [@shamoon](https://github.com/shamoon) ([#4865](https://github.com/paperless-ngx/paperless-ngx/pull/4865))
-   Fix: Allow users to configure the From email for password reset [@stumpylog](https://github.com/stumpylog) ([#4867](https://github.com/paperless-ngx/paperless-ngx/pull/4867))
-   Fix: dont show move icon for file tasks badge [@shamoon](https://github.com/shamoon) ([#4860](https://github.com/paperless-ngx/paperless-ngx/pull/4860))

### Maintenance

-   Chore: Simplifies how the documentation site is deployed [@stumpylog](https://github.com/stumpylog) ([#4858](https://github.com/paperless-ngx/paperless-ngx/pull/4858))

### All App Changes

<details>
<summary>5 changes</summary>

-   Fix: disable toggle for share link creation without archive version, fix auto-copy in Safari [@shamoon](https://github.com/shamoon) ([#4885](https://github.com/paperless-ngx/paperless-ngx/pull/4885))
-   Fix: storage paths link incorrect in dashboard widget [@shamoon](https://github.com/shamoon) ([#4878](https://github.com/paperless-ngx/paperless-ngx/pull/4878))
-   Fix: respect baseURI for pdfjs worker URL [@shamoon](https://github.com/shamoon) ([#4865](https://github.com/paperless-ngx/paperless-ngx/pull/4865))
-   Fix: Allow users to configure the From email for password reset [@stumpylog](https://github.com/stumpylog) ([#4867](https://github.com/paperless-ngx/paperless-ngx/pull/4867))
-   Fix: dont show move icon for file tasks badge [@shamoon](https://github.com/shamoon) ([#4860](https://github.com/paperless-ngx/paperless-ngx/pull/4860))
</details>

## paperless-ngx 2.1.0

### Features

-   Enhancement: implement document link custom field [@shamoon](https://github.com/shamoon) ([#4799](https://github.com/paperless-ngx/paperless-ngx/pull/4799))
-   Feature: Adds additional warnings during an import if it might fail [@stumpylog](https://github.com/stumpylog) ([#4814](https://github.com/paperless-ngx/paperless-ngx/pull/4814))
-   Feature: pngx PDF viewer with updated pdfjs [@shamoon](https://github.com/shamoon) ([#4679](https://github.com/paperless-ngx/paperless-ngx/pull/4679))
-   Enhancement: support automatically assigning custom fields via consumption templates [@shamoon](https://github.com/shamoon) ([#4727](https://github.com/paperless-ngx/paperless-ngx/pull/4727))
-   Feature: update user profile [@shamoon](https://github.com/shamoon) ([#4678](https://github.com/paperless-ngx/paperless-ngx/pull/4678))
-   Enhancement: Allow excluding mail attachments by name [@stumpylog](https://github.com/stumpylog) ([#4691](https://github.com/paperless-ngx/paperless-ngx/pull/4691))
-   Enhancement: auto-refresh logs \& tasks [@shamoon](https://github.com/shamoon) ([#4680](https://github.com/paperless-ngx/paperless-ngx/pull/4680))

### Bug Fixes

-   Fix: welcome widget text color [@shamoon](https://github.com/shamoon) ([#4829](https://github.com/paperless-ngx/paperless-ngx/pull/4829))
-   Fix: export consumption templates \& custom fields in exporter [@shamoon](https://github.com/shamoon) ([#4825](https://github.com/paperless-ngx/paperless-ngx/pull/4825))
-   Fix: bulk edit object permissions should use permissions object [@shamoon](https://github.com/shamoon) ([#4797](https://github.com/paperless-ngx/paperless-ngx/pull/4797))
-   Fix: empty string for consumption template field should be interpreted as [@shamoon](https://github.com/shamoon) ([#4762](https://github.com/paperless-ngx/paperless-ngx/pull/4762))
-   Fix: use default permissions for objects created via dropdown [@shamoon](https://github.com/shamoon) ([#4778](https://github.com/paperless-ngx/paperless-ngx/pull/4778))
-   Fix: Alpha layer removal could allow duplicates [@stumpylog](https://github.com/stumpylog) ([#4781](https://github.com/paperless-ngx/paperless-ngx/pull/4781))
-   Fix: update checker broke in v2.0.0 [@shamoon](https://github.com/shamoon) ([#4773](https://github.com/paperless-ngx/paperless-ngx/pull/4773))
-   Fix: only show global drag-drop when files included [@shamoon](https://github.com/shamoon) ([#4767](https://github.com/paperless-ngx/paperless-ngx/pull/4767))

### Documentation

-   Enhancement: implement document link custom field [@shamoon](https://github.com/shamoon) ([#4799](https://github.com/paperless-ngx/paperless-ngx/pull/4799))
-   Fix: export consumption templates \& custom fields in exporter [@shamoon](https://github.com/shamoon) ([#4825](https://github.com/paperless-ngx/paperless-ngx/pull/4825))
-   Documentation: Fix typos [@omahs](https://github.com/omahs) ([#4737](https://github.com/paperless-ngx/paperless-ngx/pull/4737))

### Maintenance

-   Bump the actions group with 2 updates [@dependabot](https://github.com/dependabot) ([#4745](https://github.com/paperless-ngx/paperless-ngx/pull/4745))

### Dependencies

<details>
<summary>7 changes</summary>

-   Bump the development group with 6 updates [@dependabot](https://github.com/dependabot) ([#4838](https://github.com/paperless-ngx/paperless-ngx/pull/4838))
-   Bump the actions group with 2 updates [@dependabot](https://github.com/dependabot) ([#4745](https://github.com/paperless-ngx/paperless-ngx/pull/4745))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4756](https://github.com/paperless-ngx/paperless-ngx/pull/4756))
-   Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#4744](https://github.com/paperless-ngx/paperless-ngx/pull/4744))
-   Bump [@<!---->playwright/test from 1.39.0 to 1.40.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.39.0 to 1.40.1 in /src-ui @dependabot) ([#4749](https://github.com/paperless-ngx/paperless-ngx/pull/4749))
-   Bump wait-on from 7.0.1 to 7.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#4747](https://github.com/paperless-ngx/paperless-ngx/pull/4747))
-   Bump [@<!---->types/node from 20.8.10 to 20.10.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.8.10 to 20.10.2 in /src-ui @dependabot) ([#4748](https://github.com/paperless-ngx/paperless-ngx/pull/4748))
</details>

### All App Changes

<details>
<summary>20 changes</summary>

-   Enhancement: implement document link custom field [@shamoon](https://github.com/shamoon) ([#4799](https://github.com/paperless-ngx/paperless-ngx/pull/4799))
-   Bump the development group with 6 updates [@dependabot](https://github.com/dependabot) ([#4838](https://github.com/paperless-ngx/paperless-ngx/pull/4838))
-   Fix: welcome widget text color [@shamoon](https://github.com/shamoon) ([#4829](https://github.com/paperless-ngx/paperless-ngx/pull/4829))
-   Fix: export consumption templates \& custom fields in exporter [@shamoon](https://github.com/shamoon) ([#4825](https://github.com/paperless-ngx/paperless-ngx/pull/4825))
-   Feature: Adds additional warnings during an import if it might fail [@stumpylog](https://github.com/stumpylog) ([#4814](https://github.com/paperless-ngx/paperless-ngx/pull/4814))
-   Feature: pngx PDF viewer with updated pdfjs [@shamoon](https://github.com/shamoon) ([#4679](https://github.com/paperless-ngx/paperless-ngx/pull/4679))
-   Fix: bulk edit object permissions should use permissions object [@shamoon](https://github.com/shamoon) ([#4797](https://github.com/paperless-ngx/paperless-ngx/pull/4797))
-   Enhancement: support automatically assigning custom fields via consumption templates [@shamoon](https://github.com/shamoon) ([#4727](https://github.com/paperless-ngx/paperless-ngx/pull/4727))
-   Fix: empty string for consumption template field should be interpreted as [@shamoon](https://github.com/shamoon) ([#4762](https://github.com/paperless-ngx/paperless-ngx/pull/4762))
-   Fix: use default permissions for objects created via dropdown [@shamoon](https://github.com/shamoon) ([#4778](https://github.com/paperless-ngx/paperless-ngx/pull/4778))
-   Fix: Alpha layer removal could allow duplicates [@stumpylog](https://github.com/stumpylog) ([#4781](https://github.com/paperless-ngx/paperless-ngx/pull/4781))
-   Feature: update user profile [@shamoon](https://github.com/shamoon) ([#4678](https://github.com/paperless-ngx/paperless-ngx/pull/4678))
-   Fix: update checker broke in v2.0.0 [@shamoon](https://github.com/shamoon) ([#4773](https://github.com/paperless-ngx/paperless-ngx/pull/4773))
-   Fix: only show global drag-drop when files included [@shamoon](https://github.com/shamoon) ([#4767](https://github.com/paperless-ngx/paperless-ngx/pull/4767))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4756](https://github.com/paperless-ngx/paperless-ngx/pull/4756))
-   Bump the frontend-jest-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#4744](https://github.com/paperless-ngx/paperless-ngx/pull/4744))
-   Bump [@<!---->playwright/test from 1.39.0 to 1.40.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.39.0 to 1.40.1 in /src-ui @dependabot) ([#4749](https://github.com/paperless-ngx/paperless-ngx/pull/4749))
-   Bump wait-on from 7.0.1 to 7.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#4747](https://github.com/paperless-ngx/paperless-ngx/pull/4747))
-   Bump [@<!---->types/node from 20.8.10 to 20.10.2 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.8.10 to 20.10.2 in /src-ui @dependabot) ([#4748](https://github.com/paperless-ngx/paperless-ngx/pull/4748))
-   Enhancement: auto-refresh logs \& tasks [@shamoon](https://github.com/shamoon) ([#4680](https://github.com/paperless-ngx/paperless-ngx/pull/4680))
</details>

## paperless-ngx 2.0.1

### Please Note

Exports generated in Paperless-ngx v2.0.0–2.0.1 will **not** contain consumption templates or custom fields, we recommend users upgrade to at least v2.1.

### Bug Fixes

-   Fix: Increase field the length for consumption template source [@stumpylog](https://github.com/stumpylog) ([#4719](https://github.com/paperless-ngx/paperless-ngx/pull/4719))
-   Fix: Set RGB color conversion strategy for PDF outputs [@stumpylog](https://github.com/stumpylog) ([#4709](https://github.com/paperless-ngx/paperless-ngx/pull/4709))
-   Fix: Add a warning about a low image DPI which may cause OCR to fail [@stumpylog](https://github.com/stumpylog) ([#4708](https://github.com/paperless-ngx/paperless-ngx/pull/4708))
-   Fix: share links for URLs containing 'api' incorrect in dropdown [@shamoon](https://github.com/shamoon) ([#4701](https://github.com/paperless-ngx/paperless-ngx/pull/4701))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: Increase field the length for consumption template source [@stumpylog](https://github.com/stumpylog) ([#4719](https://github.com/paperless-ngx/paperless-ngx/pull/4719))
-   Fix: Set RGB color conversion strategy for PDF outputs [@stumpylog](https://github.com/stumpylog) ([#4709](https://github.com/paperless-ngx/paperless-ngx/pull/4709))
-   Fix: Add a warning about a low image DPI which may cause OCR to fail [@stumpylog](https://github.com/stumpylog) ([#4708](https://github.com/paperless-ngx/paperless-ngx/pull/4708))
-   Fix: share links for URLs containing 'api' incorrect in dropdown [@shamoon](https://github.com/shamoon) ([#4701](https://github.com/paperless-ngx/paperless-ngx/pull/4701))
</details>

## paperless-ngx 2.0.0

### Please Note

Exports generated in Paperless-ngx v2.0.0–2.0.1 will **not** contain consumption templates or custom fields, we recommend users upgrade to at least v2.1.

### Breaking Changes

-   Breaking: Rename the environment variable for self-signed email certificates [@stumpylog](https://github.com/stumpylog) ([#4346](https://github.com/paperless-ngx/paperless-ngx/pull/4346))
-   Breaking: Drop support for Python 3.8 [@stumpylog](https://github.com/stumpylog) ([#4156](https://github.com/paperless-ngx/paperless-ngx/pull/4156))
-   Breaking: Remove ARMv7 building of the Docker image [@stumpylog](https://github.com/stumpylog) ([#3973](https://github.com/paperless-ngx/paperless-ngx/pull/3973))

### Notable Changes

-   Feature: consumption templates [@shamoon](https://github.com/shamoon) ([#4196](https://github.com/paperless-ngx/paperless-ngx/pull/4196))
-   Feature: Share links [@shamoon](https://github.com/shamoon) ([#3996](https://github.com/paperless-ngx/paperless-ngx/pull/3996))
-   Enhancement: Updates the underlying image to use Python 3.11 [@stumpylog](https://github.com/stumpylog) ([#4150](https://github.com/paperless-ngx/paperless-ngx/pull/4150))

### Features

-   Feature: compact notifications [@shamoon](https://github.com/shamoon) ([#4545](https://github.com/paperless-ngx/paperless-ngx/pull/4545))
-   Chore: Backend bulk updates [@stumpylog](https://github.com/stumpylog) ([#4509](https://github.com/paperless-ngx/paperless-ngx/pull/4509))
-   Feature: Hungarian translation [@shamoon](https://github.com/shamoon) ([#4552](https://github.com/paperless-ngx/paperless-ngx/pull/4552))
-   Chore: API support for id args for documents \& objects [@shamoon](https://github.com/shamoon) ([#4519](https://github.com/paperless-ngx/paperless-ngx/pull/4519))
-   Feature: Add Bulgarian translation [@shamoon](https://github.com/shamoon) ([#4470](https://github.com/paperless-ngx/paperless-ngx/pull/4470))
-   Feature: Audit Trail [@nanokatz](https://github.com/nanokatz) ([#4425](https://github.com/paperless-ngx/paperless-ngx/pull/4425))
-   Feature: Add ahead of time compression of the static files for x86_64 [@stumpylog](https://github.com/stumpylog) ([#4390](https://github.com/paperless-ngx/paperless-ngx/pull/4390))
-   Feature: sort sidebar views [@shamoon](https://github.com/shamoon) ([#4381](https://github.com/paperless-ngx/paperless-ngx/pull/4381))
-   Feature: Switches to a new client to handle communication with Gotenberg [@stumpylog](https://github.com/stumpylog) ([#4391](https://github.com/paperless-ngx/paperless-ngx/pull/4391))
-   barcode logic: strip non-numeric characters from detected ASN string [@queaker](https://github.com/queaker) ([#4379](https://github.com/paperless-ngx/paperless-ngx/pull/4379))
-   Feature: Include more updated base tools in Docker image [@stumpylog](https://github.com/stumpylog) ([#4319](https://github.com/paperless-ngx/paperless-ngx/pull/4319))
-   CI: speed-up frontend tests on ci [@shamoon](https://github.com/shamoon) ([#4316](https://github.com/paperless-ngx/paperless-ngx/pull/4316))
-   Feature: password reset [@shamoon](https://github.com/shamoon) ([#4289](https://github.com/paperless-ngx/paperless-ngx/pull/4289))
-   Enhancement: dashboard improvements, drag-n-drop reorder dashboard views [@shamoon](https://github.com/shamoon) ([#4252](https://github.com/paperless-ngx/paperless-ngx/pull/4252))
-   Feature: Updates Django to 4.2.5 [@stumpylog](https://github.com/stumpylog) ([#4278](https://github.com/paperless-ngx/paperless-ngx/pull/4278))
-   Enhancement: settings reorganization \& improvements, separate admin section [@shamoon](https://github.com/shamoon) ([#4251](https://github.com/paperless-ngx/paperless-ngx/pull/4251))
-   Feature: consumption templates [@shamoon](https://github.com/shamoon) ([#4196](https://github.com/paperless-ngx/paperless-ngx/pull/4196))
-   Enhancement: support default permissions for object creation via frontend [@shamoon](https://github.com/shamoon) ([#4233](https://github.com/paperless-ngx/paperless-ngx/pull/4233))
-   Fix: Set permissions before declaring volumes for rootless [@stumpylog](https://github.com/stumpylog) ([#4225](https://github.com/paperless-ngx/paperless-ngx/pull/4225))
-   Enhancement: bulk edit object permissions [@shamoon](https://github.com/shamoon) ([#4176](https://github.com/paperless-ngx/paperless-ngx/pull/4176))
-   Enhancement: Allow the user the specify the export zip file name [@stumpylog](https://github.com/stumpylog) ([#4189](https://github.com/paperless-ngx/paperless-ngx/pull/4189))
-   Feature: Share links [@shamoon](https://github.com/shamoon) ([#3996](https://github.com/paperless-ngx/paperless-ngx/pull/3996))
-   Chore: update docker image and ci to node 20 [@shamoon](https://github.com/shamoon) ([#4184](https://github.com/paperless-ngx/paperless-ngx/pull/4184))
-   Fix: Trim unneeded libraries from Docker image [@stumpylog](https://github.com/stumpylog) ([#4183](https://github.com/paperless-ngx/paperless-ngx/pull/4183))
-   Feature: New management command for fuzzy matching document content [@stumpylog](https://github.com/stumpylog) ([#4160](https://github.com/paperless-ngx/paperless-ngx/pull/4160))
-   Enhancement: Updates the underlying image to use Python 3.11 [@stumpylog](https://github.com/stumpylog) ([#4150](https://github.com/paperless-ngx/paperless-ngx/pull/4150))
-   Enhancement: frontend better handle slow backend requests [@shamoon](https://github.com/shamoon) ([#4055](https://github.com/paperless-ngx/paperless-ngx/pull/4055))
-   Chore: update docker image \& ci testing node to v18 [@shamoon](https://github.com/shamoon) ([#4149](https://github.com/paperless-ngx/paperless-ngx/pull/4149))
-   Enhancement: Improved error notifications [@shamoon](https://github.com/shamoon) ([#4062](https://github.com/paperless-ngx/paperless-ngx/pull/4062))
-   Feature: Official support for Python 3.11 [@stumpylog](https://github.com/stumpylog) ([#4146](https://github.com/paperless-ngx/paperless-ngx/pull/4146))
-   Enhancement: Add Afrikaans, Greek \& Norwegian languages [@shamoon](https://github.com/shamoon) ([#4088](https://github.com/paperless-ngx/paperless-ngx/pull/4088))
-   Enhancement: add task id to pre/post consume script as env [@andreheuer](https://github.com/andreheuer) ([#4037](https://github.com/paperless-ngx/paperless-ngx/pull/4037))
-   Enhancement: update bootstrap to v5.3.1 for backend static pages [@shamoon](https://github.com/shamoon) ([#4060](https://github.com/paperless-ngx/paperless-ngx/pull/4060))

### Bug Fixes

-   Fix: Add missing spaces to help string in [@joouha](https://github.com/joouha) ([#4674](https://github.com/paperless-ngx/paperless-ngx/pull/4674))
-   Fix: Typo invalidates precondition for doctype, resulting in Exception [@ArminGruner](https://github.com/ArminGruner) ([#4668](https://github.com/paperless-ngx/paperless-ngx/pull/4668))
-   Fix: Miscellaneous visual fixes in v2.0.0-beta.rc1 2 [@shamoon](https://github.com/shamoon) ([#4635](https://github.com/paperless-ngx/paperless-ngx/pull/4635))
-   Fix: Delay consumption after MODIFY inotify events [@frozenbrain](https://github.com/frozenbrain) ([#4626](https://github.com/paperless-ngx/paperless-ngx/pull/4626))
-   Documentation: Add note that trash dir must exist [@shamoon](https://github.com/shamoon) ([#4608](https://github.com/paperless-ngx/paperless-ngx/pull/4608))
-   Fix: Miscellaneous v2.0 visual fixes [@shamoon](https://github.com/shamoon) ([#4576](https://github.com/paperless-ngx/paperless-ngx/pull/4576))
-   Fix: Force UTF-8 for exporter manifests and don't allow escaping [@stumpylog](https://github.com/stumpylog) ([#4574](https://github.com/paperless-ngx/paperless-ngx/pull/4574))
-   Fix: plain text preview overflows [@shamoon](https://github.com/shamoon) ([#4555](https://github.com/paperless-ngx/paperless-ngx/pull/4555))
-   Fix: add permissions for custom fields with migration [@shamoon](https://github.com/shamoon) ([#4513](https://github.com/paperless-ngx/paperless-ngx/pull/4513))
-   Fix: visually hidden text breaks delete button wrap [@shamoon](https://github.com/shamoon) ([#4462](https://github.com/paperless-ngx/paperless-ngx/pull/4462))
-   Fix: API statistics document_file_type_counts return type [@shamoon](https://github.com/shamoon) ([#4464](https://github.com/paperless-ngx/paperless-ngx/pull/4464))
-   Fix: Always return a list for audit log check [@shamoon](https://github.com/shamoon) ([#4463](https://github.com/paperless-ngx/paperless-ngx/pull/4463))
-   Fix: Only create a Correspondent if the email matches rule filters [@stumpylog](https://github.com/stumpylog) ([#4431](https://github.com/paperless-ngx/paperless-ngx/pull/4431))
-   Fix: Combination of consume template with recursive tagging [@stumpylog](https://github.com/stumpylog) ([#4442](https://github.com/paperless-ngx/paperless-ngx/pull/4442))
-   Fix: replace drag drop \& clipboard deps with angular cdk [@shamoon](https://github.com/shamoon) ([#4362](https://github.com/paperless-ngx/paperless-ngx/pull/4362))
-   Fix: update document modified time on note creation / deletion [@shamoon](https://github.com/shamoon) ([#4374](https://github.com/paperless-ngx/paperless-ngx/pull/4374))
-   Fix: Updates to latest imap_tools which includes fix for the meta charset in HTML content [@stumpylog](https://github.com/stumpylog) ([#4355](https://github.com/paperless-ngx/paperless-ngx/pull/4355))
-   Fix: Missing creation of a folder in Docker image [@stumpylog](https://github.com/stumpylog) ([#4347](https://github.com/paperless-ngx/paperless-ngx/pull/4347))
-   Fix: Retry Tika parsing when Tika returns HTTP 500 [@stumpylog](https://github.com/stumpylog) ([#4334](https://github.com/paperless-ngx/paperless-ngx/pull/4334))
-   Fix: get highest ASN regardless of user [@shamoon](https://github.com/shamoon) ([#4326](https://github.com/paperless-ngx/paperless-ngx/pull/4326))
-   Fix: Generate secret key with C locale and increase allowed characters [@stumpylog](https://github.com/stumpylog) ([#4277](https://github.com/paperless-ngx/paperless-ngx/pull/4277))
-   Fix: long notes cause visual overflow [@shamoon](https://github.com/shamoon) ([#4287](https://github.com/paperless-ngx/paperless-ngx/pull/4287))
-   Fix: Ensures all old connections are closed in certain long lived places [@stumpylog](https://github.com/stumpylog) ([#4265](https://github.com/paperless-ngx/paperless-ngx/pull/4265))
-   CI: fix playwright browser version mismatch failures [@shamoon](https://github.com/shamoon) ([#4239](https://github.com/paperless-ngx/paperless-ngx/pull/4239))
-   Fix: Set a non-zero polling internal when inotify cannot import [@stumpylog](https://github.com/stumpylog) ([#4230](https://github.com/paperless-ngx/paperless-ngx/pull/4230))
-   Fix: Set permissions before declaring volumes for rootless [@stumpylog](https://github.com/stumpylog) ([#4225](https://github.com/paperless-ngx/paperless-ngx/pull/4225))
-   Documentation: Fix fuzzy matching details [@stumpylog](https://github.com/stumpylog) ([#4207](https://github.com/paperless-ngx/paperless-ngx/pull/4207))
-   Fix: application of theme color vars at root [@shamoon](https://github.com/shamoon) ([#4193](https://github.com/paperless-ngx/paperless-ngx/pull/4193))
-   Fix: Trim unneeded libraries from Docker image [@stumpylog](https://github.com/stumpylog) ([#4183](https://github.com/paperless-ngx/paperless-ngx/pull/4183))
-   Fix: support storage path placeholder via API [@shamoon](https://github.com/shamoon) ([#4179](https://github.com/paperless-ngx/paperless-ngx/pull/4179))
-   Fix: Logs the errors during thumbnail generation [@stumpylog](https://github.com/stumpylog) ([#4171](https://github.com/paperless-ngx/paperless-ngx/pull/4171))
-   Fix: remove owner details from saved_views api endpoint [@shamoon](https://github.com/shamoon) ([#4158](https://github.com/paperless-ngx/paperless-ngx/pull/4158))
-   Fix: dashboard widget card borders hidden by bkgd color [@shamoon](https://github.com/shamoon) ([#4155](https://github.com/paperless-ngx/paperless-ngx/pull/4155))
-   Fix: hide entire add user / group buttons if insufficient permissions [@shamoon](https://github.com/shamoon) ([#4133](https://github.com/paperless-ngx/paperless-ngx/pull/4133))

### Documentation

-   Documentation: Update documentation to refer only to Docker Compose v2 command [@stumpylog](https://github.com/stumpylog) ([#4650](https://github.com/paperless-ngx/paperless-ngx/pull/4650))
-   Documentation: fix typo, add to features list [@tooomm](https://github.com/tooomm) ([#4624](https://github.com/paperless-ngx/paperless-ngx/pull/4624))
-   Documentation: Add note that trash dir must exist [@shamoon](https://github.com/shamoon) ([#4608](https://github.com/paperless-ngx/paperless-ngx/pull/4608))
-   Documentation: Structure backup sections more clearly [@quantenProjects](https://github.com/quantenProjects) ([#4559](https://github.com/paperless-ngx/paperless-ngx/pull/4559))
-   Documentation: update docs, screenshots ahead of Paperless-ngx v2.0 [@shamoon](https://github.com/shamoon) ([#4542](https://github.com/paperless-ngx/paperless-ngx/pull/4542))
-   Chore: Cleanup command arguments and standardize process count handling [@stumpylog](https://github.com/stumpylog) ([#4541](https://github.com/paperless-ngx/paperless-ngx/pull/4541))
-   Add section for SELinux troubleshooting [@nachtjasmin](https://github.com/nachtjasmin) ([#4528](https://github.com/paperless-ngx/paperless-ngx/pull/4528))
-   Documentation: clarify document_exporter includes settings [@coaxial](https://github.com/coaxial) ([#4533](https://github.com/paperless-ngx/paperless-ngx/pull/4533))
-   Change: Install script improvements [@m-GDEV](https://github.com/m-GDEV) ([#4387](https://github.com/paperless-ngx/paperless-ngx/pull/4387))
-   Fix: update document modified time on note creation / deletion [@shamoon](https://github.com/shamoon) ([#4374](https://github.com/paperless-ngx/paperless-ngx/pull/4374))
-   Fix: correct set owner API location in docs, additional test [@shamoon](https://github.com/shamoon) ([#4366](https://github.com/paperless-ngx/paperless-ngx/pull/4366))
-   Documentation: Remove old information about building the Docker image locally [@stumpylog](https://github.com/stumpylog) ([#4354](https://github.com/paperless-ngx/paperless-ngx/pull/4354))
-   Documentation enhancement: add direct links for all config vars [@shamoon](https://github.com/shamoon) ([#4237](https://github.com/paperless-ngx/paperless-ngx/pull/4237))
-   Documentation: Fix fuzzy matching details [@stumpylog](https://github.com/stumpylog) ([#4207](https://github.com/paperless-ngx/paperless-ngx/pull/4207))

### Maintenance

-   Chore: Backend bulk updates [@stumpylog](https://github.com/stumpylog) ([#4509](https://github.com/paperless-ngx/paperless-ngx/pull/4509))
-   Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#4476](https://github.com/paperless-ngx/paperless-ngx/pull/4476))
-   Feature: Add Bulgarian translation [@shamoon](https://github.com/shamoon) ([#4470](https://github.com/paperless-ngx/paperless-ngx/pull/4470))
-   Chore: Stop duplicated action runs against internal PRs [@stumpylog](https://github.com/stumpylog) ([#4430](https://github.com/paperless-ngx/paperless-ngx/pull/4430))
-   CI: separate frontend deps install [@shamoon](https://github.com/shamoon) ([#4336](https://github.com/paperless-ngx/paperless-ngx/pull/4336))
-   CI: speed-up frontend tests on ci [@shamoon](https://github.com/shamoon) ([#4316](https://github.com/paperless-ngx/paperless-ngx/pull/4316))
-   Fix: Generate secret key with C locale and increase allowed characters [@stumpylog](https://github.com/stumpylog) ([#4277](https://github.com/paperless-ngx/paperless-ngx/pull/4277))
-   Bump leonsteinhaeuser/project-beta-automations from 2.1.0 to 2.2.1 [@dependabot](https://github.com/dependabot) ([#4281](https://github.com/paperless-ngx/paperless-ngx/pull/4281))
-   Chore: Updates dependabot to group more dependencies [@stumpylog](https://github.com/stumpylog) ([#4280](https://github.com/paperless-ngx/paperless-ngx/pull/4280))
-   Change: update translation string for tasks dialog [@shamoon](https://github.com/shamoon) ([#4263](https://github.com/paperless-ngx/paperless-ngx/pull/4263))
-   CI: fix playwright browser version mismatch failures [@shamoon](https://github.com/shamoon) ([#4239](https://github.com/paperless-ngx/paperless-ngx/pull/4239))
-   Bump docker/login-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4221](https://github.com/paperless-ngx/paperless-ngx/pull/4221))
-   Bump docker/setup-buildx-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4220](https://github.com/paperless-ngx/paperless-ngx/pull/4220))
-   Bump docker/setup-qemu-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4211](https://github.com/paperless-ngx/paperless-ngx/pull/4211))
-   Bump stumpylog/image-cleaner-action from 0.2.0 to 0.3.0 [@dependabot](https://github.com/dependabot) ([#4210](https://github.com/paperless-ngx/paperless-ngx/pull/4210))
-   Bump docker/metadata-action from 4 to 5 [@dependabot](https://github.com/dependabot) ([#4209](https://github.com/paperless-ngx/paperless-ngx/pull/4209))
-   Bump docker/build-push-action from 4 to 5 [@dependabot](https://github.com/dependabot) ([#4212](https://github.com/paperless-ngx/paperless-ngx/pull/4212))
-   Bump actions/checkout from 3 to 4 [@dependabot](https://github.com/dependabot) ([#4208](https://github.com/paperless-ngx/paperless-ngx/pull/4208))
-   Chore: update docker image and ci to node 20 [@shamoon](https://github.com/shamoon) ([#4184](https://github.com/paperless-ngx/paperless-ngx/pull/4184))

### Dependencies

<details>
<summary>39 changes</summary>

-   Chore: Bulk update of Python dependencies [@stumpylog](https://github.com/stumpylog) ([#4688](https://github.com/paperless-ngx/paperless-ngx/pull/4688))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4479](https://github.com/paperless-ngx/paperless-ngx/pull/4479))
-   Bump [@<!---->playwright/test from 1.38.1 to 1.39.0 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.38.1 to 1.39.0 in /src-ui @dependabot) ([#4480](https://github.com/paperless-ngx/paperless-ngx/pull/4480))
-   Bump concurrently from 8.2.1 to 8.2.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4481](https://github.com/paperless-ngx/paperless-ngx/pull/4481))
-   Bump the frontend-jest-dependencies group in /src-ui with 1 update [@dependabot](https://github.com/dependabot) ([#4478](https://github.com/paperless-ngx/paperless-ngx/pull/4478))
-   Bump the frontend-angular-dependencies group in /src-ui with 14 updates [@dependabot](https://github.com/dependabot) ([#4477](https://github.com/paperless-ngx/paperless-ngx/pull/4477))
-   Bump the actions group with 1 update [@dependabot](https://github.com/dependabot) ([#4476](https://github.com/paperless-ngx/paperless-ngx/pull/4476))
-   Bump [@<!---->babel/traverse from 7.22.11 to 7.23.2 in /src-ui @dependabot](https://github.com/<!---->babel/traverse from 7.22.11 to 7.23.2 in /src-ui @dependabot) ([#4389](https://github.com/paperless-ngx/paperless-ngx/pull/4389))
-   Fix: replace drag drop \& clipboard deps with angular cdk [@shamoon](https://github.com/shamoon) ([#4362](https://github.com/paperless-ngx/paperless-ngx/pull/4362))
-   Bump postcss from 8.4.12 to 8.4.31 in /src/paperless_mail/templates [@dependabot](https://github.com/dependabot) ([#4318](https://github.com/paperless-ngx/paperless-ngx/pull/4318))
-   Bump [@<!---->types/node from 20.7.0 to 20.8.0 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.7.0 to 20.8.0 in /src-ui @dependabot) ([#4303](https://github.com/paperless-ngx/paperless-ngx/pull/4303))
-   Bump the frontend-angular-dependencies group in /src-ui with 8 updates [@dependabot](https://github.com/dependabot) ([#4302](https://github.com/paperless-ngx/paperless-ngx/pull/4302))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4283](https://github.com/paperless-ngx/paperless-ngx/pull/4283))
-   Bump the frontend-angular-dependencies group in /src-ui with 10 updates [@dependabot](https://github.com/dependabot) ([#4282](https://github.com/paperless-ngx/paperless-ngx/pull/4282))
-   Bump [@<!---->types/node from 20.6.3 to 20.7.0 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.6.3 to 20.7.0 in /src-ui @dependabot) ([#4284](https://github.com/paperless-ngx/paperless-ngx/pull/4284))
-   Bump leonsteinhaeuser/project-beta-automations from 2.1.0 to 2.2.1 [@dependabot](https://github.com/dependabot) ([#4281](https://github.com/paperless-ngx/paperless-ngx/pull/4281))
-   Bump zone.js from 0.13.1 to 0.13.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#4223](https://github.com/paperless-ngx/paperless-ngx/pull/4223))
-   Bump [@<!---->types/node from 20.5.8 to 20.6.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.5.8 to 20.6.3 in /src-ui @dependabot) ([#4224](https://github.com/paperless-ngx/paperless-ngx/pull/4224))
-   Bump the frontend-angular-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#4222](https://github.com/paperless-ngx/paperless-ngx/pull/4222))
-   Bump docker/login-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4221](https://github.com/paperless-ngx/paperless-ngx/pull/4221))
-   Bump docker/setup-buildx-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4220](https://github.com/paperless-ngx/paperless-ngx/pull/4220))
-   Bump docker/setup-qemu-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#4211](https://github.com/paperless-ngx/paperless-ngx/pull/4211))
-   Bump bootstrap from 5.3.1 to 5.3.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4217](https://github.com/paperless-ngx/paperless-ngx/pull/4217))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4215](https://github.com/paperless-ngx/paperless-ngx/pull/4215))
-   Bump the frontend-jest-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#4218](https://github.com/paperless-ngx/paperless-ngx/pull/4218))
-   Bump stumpylog/image-cleaner-action from 0.2.0 to 0.3.0 [@dependabot](https://github.com/dependabot) ([#4210](https://github.com/paperless-ngx/paperless-ngx/pull/4210))
-   Bump docker/metadata-action from 4 to 5 [@dependabot](https://github.com/dependabot) ([#4209](https://github.com/paperless-ngx/paperless-ngx/pull/4209))
-   Bump uuid from 9.0.0 to 9.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#4216](https://github.com/paperless-ngx/paperless-ngx/pull/4216))
-   Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#4213](https://github.com/paperless-ngx/paperless-ngx/pull/4213))
-   Bump docker/build-push-action from 4 to 5 [@dependabot](https://github.com/dependabot) ([#4212](https://github.com/paperless-ngx/paperless-ngx/pull/4212))
-   Bump actions/checkout from 3 to 4 [@dependabot](https://github.com/dependabot) ([#4208](https://github.com/paperless-ngx/paperless-ngx/pull/4208))
-   Chore: update docker image \& ci testing node to v18 [@shamoon](https://github.com/shamoon) ([#4149](https://github.com/paperless-ngx/paperless-ngx/pull/4149))
-   Chore: Unlock dependencies \& update them all [@stumpylog](https://github.com/stumpylog) ([#4142](https://github.com/paperless-ngx/paperless-ngx/pull/4142))
-   Bump the frontend-jest-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#4112](https://github.com/paperless-ngx/paperless-ngx/pull/4112))
-   Bump tslib from 2.6.1 to 2.6.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4108](https://github.com/paperless-ngx/paperless-ngx/pull/4108))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4106](https://github.com/paperless-ngx/paperless-ngx/pull/4106))
-   Bump concurrently from 8.2.0 to 8.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#4111](https://github.com/paperless-ngx/paperless-ngx/pull/4111))
-   Bump [@<!---->types/node from 20.4.5 to 20.5.8 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.4.5 to 20.5.8 in /src-ui @dependabot) ([#4110](https://github.com/paperless-ngx/paperless-ngx/pull/4110))
-   Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#4104](https://github.com/paperless-ngx/paperless-ngx/pull/4104))
</details>

### All App Changes

<details>
<summary>95 changes</summary>

-   Fix: Add missing spaces to help string in [@joouha](https://github.com/joouha) ([#4674](https://github.com/paperless-ngx/paperless-ngx/pull/4674))
-   Fix: Typo invalidates precondition for doctype, resulting in Exception [@ArminGruner](https://github.com/ArminGruner) ([#4668](https://github.com/paperless-ngx/paperless-ngx/pull/4668))
-   Fix: dark mode inconsistencies in v2.0.0 beta.rc1 [@shamoon](https://github.com/shamoon) ([#4669](https://github.com/paperless-ngx/paperless-ngx/pull/4669))
-   Fix: dashboard saved view mobile width in v.2.0.0 beta.rc1 [@shamoon](https://github.com/shamoon) ([#4660](https://github.com/paperless-ngx/paperless-ngx/pull/4660))
-   Fix: Miscellaneous visual fixes in v2.0.0-beta.rc1 2 [@shamoon](https://github.com/shamoon) ([#4635](https://github.com/paperless-ngx/paperless-ngx/pull/4635))
-   Fix: Delay consumption after MODIFY inotify events [@frozenbrain](https://github.com/frozenbrain) ([#4626](https://github.com/paperless-ngx/paperless-ngx/pull/4626))
-   Fix: Import of split-manifests can fail [@stumpylog](https://github.com/stumpylog) ([#4623](https://github.com/paperless-ngx/paperless-ngx/pull/4623))
-   Fix: sidebar views dont update after creation in v2.0.0-beta.rc1 [@shamoon](https://github.com/shamoon) ([#4619](https://github.com/paperless-ngx/paperless-ngx/pull/4619))
-   Fix: Prevent text wrap on consumption template label [@shamoon](https://github.com/shamoon) ([#4616](https://github.com/paperless-ngx/paperless-ngx/pull/4616))
-   Fix: increase width of labels in default perms settings [@shamoon](https://github.com/shamoon) ([#4612](https://github.com/paperless-ngx/paperless-ngx/pull/4612))
-   Fix: note deletion fails in v2.0.0-beta.rc1 [@shamoon](https://github.com/shamoon) ([#4602](https://github.com/paperless-ngx/paperless-ngx/pull/4602))
-   Fix: Handle override lists being None [@stumpylog](https://github.com/stumpylog) ([#4598](https://github.com/paperless-ngx/paperless-ngx/pull/4598))
-   Fix: Miscellaneous v2.0 visual fixes [@shamoon](https://github.com/shamoon) ([#4576](https://github.com/paperless-ngx/paperless-ngx/pull/4576))
-   Fix: Force UTF-8 for exporter manifests and don't allow escaping [@stumpylog](https://github.com/stumpylog) ([#4574](https://github.com/paperless-ngx/paperless-ngx/pull/4574))
-   Feature: compact notifications [@shamoon](https://github.com/shamoon) ([#4545](https://github.com/paperless-ngx/paperless-ngx/pull/4545))
-   Chore: Backend bulk updates [@stumpylog](https://github.com/stumpylog) ([#4509](https://github.com/paperless-ngx/paperless-ngx/pull/4509))
-   Fix: plain text preview overflows [@shamoon](https://github.com/shamoon) ([#4555](https://github.com/paperless-ngx/paperless-ngx/pull/4555))
-   Feature: Hungarian translation [@shamoon](https://github.com/shamoon) ([#4552](https://github.com/paperless-ngx/paperless-ngx/pull/4552))
-   Chore: Cleanup command arguments and standardize process count handling [@stumpylog](https://github.com/stumpylog) ([#4541](https://github.com/paperless-ngx/paperless-ngx/pull/4541))
-   Chore: API support for id args for documents \& objects [@shamoon](https://github.com/shamoon) ([#4519](https://github.com/paperless-ngx/paperless-ngx/pull/4519))
-   Fix: add permissions for custom fields with migration [@shamoon](https://github.com/shamoon) ([#4513](https://github.com/paperless-ngx/paperless-ngx/pull/4513))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4479](https://github.com/paperless-ngx/paperless-ngx/pull/4479))
-   Bump [@<!---->playwright/test from 1.38.1 to 1.39.0 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.38.1 to 1.39.0 in /src-ui @dependabot) ([#4480](https://github.com/paperless-ngx/paperless-ngx/pull/4480))
-   Bump concurrently from 8.2.1 to 8.2.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4481](https://github.com/paperless-ngx/paperless-ngx/pull/4481))
-   Bump the frontend-jest-dependencies group in /src-ui with 1 update [@dependabot](https://github.com/dependabot) ([#4478](https://github.com/paperless-ngx/paperless-ngx/pull/4478))
-   Bump the frontend-angular-dependencies group in /src-ui with 14 updates [@dependabot](https://github.com/dependabot) ([#4477](https://github.com/paperless-ngx/paperless-ngx/pull/4477))
-   Fix: visually hidden text breaks delete button wrap [@shamoon](https://github.com/shamoon) ([#4462](https://github.com/paperless-ngx/paperless-ngx/pull/4462))
-   Fix: API statistics document_file_type_counts return type [@shamoon](https://github.com/shamoon) ([#4464](https://github.com/paperless-ngx/paperless-ngx/pull/4464))
-   Fix: Always return a list for audit log check [@shamoon](https://github.com/shamoon) ([#4463](https://github.com/paperless-ngx/paperless-ngx/pull/4463))
-   Feature: Audit Trail [@nanokatz](https://github.com/nanokatz) ([#4425](https://github.com/paperless-ngx/paperless-ngx/pull/4425))
-   Fix: Only create a Correspondent if the email matches rule filters [@stumpylog](https://github.com/stumpylog) ([#4431](https://github.com/paperless-ngx/paperless-ngx/pull/4431))
-   Fix: Combination of consume template with recursive tagging [@stumpylog](https://github.com/stumpylog) ([#4442](https://github.com/paperless-ngx/paperless-ngx/pull/4442))
-   Feature: Add ahead of time compression of the static files for x86_64 [@stumpylog](https://github.com/stumpylog) ([#4390](https://github.com/paperless-ngx/paperless-ngx/pull/4390))
-   Feature: sort sidebar views [@shamoon](https://github.com/shamoon) ([#4381](https://github.com/paperless-ngx/paperless-ngx/pull/4381))
-   Feature: Switches to a new client to handle communication with Gotenberg [@stumpylog](https://github.com/stumpylog) ([#4391](https://github.com/paperless-ngx/paperless-ngx/pull/4391))
-   barcode logic: strip non-numeric characters from detected ASN string [@queaker](https://github.com/queaker) ([#4379](https://github.com/paperless-ngx/paperless-ngx/pull/4379))
-   Bump [@<!---->babel/traverse from 7.22.11 to 7.23.2 in /src-ui @dependabot](https://github.com/<!---->babel/traverse from 7.22.11 to 7.23.2 in /src-ui @dependabot) ([#4389](https://github.com/paperless-ngx/paperless-ngx/pull/4389))
-   Fix: replace drag drop \& clipboard deps with angular cdk [@shamoon](https://github.com/shamoon) ([#4362](https://github.com/paperless-ngx/paperless-ngx/pull/4362))
-   Fix: update document modified time on note creation / deletion [@shamoon](https://github.com/shamoon) ([#4374](https://github.com/paperless-ngx/paperless-ngx/pull/4374))
-   Fix: correct set owner API location in docs, additional test [@shamoon](https://github.com/shamoon) ([#4366](https://github.com/paperless-ngx/paperless-ngx/pull/4366))
-   Fix: get highest ASN regardless of user [@shamoon](https://github.com/shamoon) ([#4326](https://github.com/paperless-ngx/paperless-ngx/pull/4326))
-   Bump postcss from 8.4.12 to 8.4.31 in /src/paperless_mail/templates [@dependabot](https://github.com/dependabot) ([#4318](https://github.com/paperless-ngx/paperless-ngx/pull/4318))
-   CI: speed-up frontend tests on ci [@shamoon](https://github.com/shamoon) ([#4316](https://github.com/paperless-ngx/paperless-ngx/pull/4316))
-   Bump [@<!---->types/node from 20.7.0 to 20.8.0 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.7.0 to 20.8.0 in /src-ui @dependabot) ([#4303](https://github.com/paperless-ngx/paperless-ngx/pull/4303))
-   Bump the frontend-angular-dependencies group in /src-ui with 8 updates [@dependabot](https://github.com/dependabot) ([#4302](https://github.com/paperless-ngx/paperless-ngx/pull/4302))
-   Feature: password reset [@shamoon](https://github.com/shamoon) ([#4289](https://github.com/paperless-ngx/paperless-ngx/pull/4289))
-   Enhancement: dashboard improvements, drag-n-drop reorder dashboard views [@shamoon](https://github.com/shamoon) ([#4252](https://github.com/paperless-ngx/paperless-ngx/pull/4252))
-   Fix: long notes cause visual overflow [@shamoon](https://github.com/shamoon) ([#4287](https://github.com/paperless-ngx/paperless-ngx/pull/4287))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4283](https://github.com/paperless-ngx/paperless-ngx/pull/4283))
-   Bump the frontend-angular-dependencies group in /src-ui with 10 updates [@dependabot](https://github.com/dependabot) ([#4282](https://github.com/paperless-ngx/paperless-ngx/pull/4282))
-   Bump [@<!---->types/node from 20.6.3 to 20.7.0 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.6.3 to 20.7.0 in /src-ui @dependabot) ([#4284](https://github.com/paperless-ngx/paperless-ngx/pull/4284))
-   Fix: Ensures all old connections are closed in certain long lived places [@stumpylog](https://github.com/stumpylog) ([#4265](https://github.com/paperless-ngx/paperless-ngx/pull/4265))
-   Change: update translation string for tasks dialog [@shamoon](https://github.com/shamoon) ([#4263](https://github.com/paperless-ngx/paperless-ngx/pull/4263))
-   Enhancement: settings reorganization \& improvements, separate admin section [@shamoon](https://github.com/shamoon) ([#4251](https://github.com/paperless-ngx/paperless-ngx/pull/4251))
-   Chore: Standardizes the imports across all the files and modules [@stumpylog](https://github.com/stumpylog) ([#4248](https://github.com/paperless-ngx/paperless-ngx/pull/4248))
-   Feature: consumption templates [@shamoon](https://github.com/shamoon) ([#4196](https://github.com/paperless-ngx/paperless-ngx/pull/4196))
-   Enhancement: support default permissions for object creation via frontend [@shamoon](https://github.com/shamoon) ([#4233](https://github.com/paperless-ngx/paperless-ngx/pull/4233))
-   Fix: Set a non-zero polling internal when inotify cannot import [@stumpylog](https://github.com/stumpylog) ([#4230](https://github.com/paperless-ngx/paperless-ngx/pull/4230))
-   Bump zone.js from 0.13.1 to 0.13.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#4223](https://github.com/paperless-ngx/paperless-ngx/pull/4223))
-   Bump [@<!---->types/node from 20.5.8 to 20.6.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.5.8 to 20.6.3 in /src-ui @dependabot) ([#4224](https://github.com/paperless-ngx/paperless-ngx/pull/4224))
-   Bump the frontend-angular-dependencies group in /src-ui with 2 updates [@dependabot](https://github.com/dependabot) ([#4222](https://github.com/paperless-ngx/paperless-ngx/pull/4222))
-   Bump bootstrap from 5.3.1 to 5.3.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4217](https://github.com/paperless-ngx/paperless-ngx/pull/4217))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4215](https://github.com/paperless-ngx/paperless-ngx/pull/4215))
-   Bump the frontend-jest-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#4218](https://github.com/paperless-ngx/paperless-ngx/pull/4218))
-   Bump uuid from 9.0.0 to 9.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#4216](https://github.com/paperless-ngx/paperless-ngx/pull/4216))
-   Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#4213](https://github.com/paperless-ngx/paperless-ngx/pull/4213))
-   Enhancement: bulk edit object permissions [@shamoon](https://github.com/shamoon) ([#4176](https://github.com/paperless-ngx/paperless-ngx/pull/4176))
-   Fix: completely hide upload widget if user does not have permissions [@nawramm](https://github.com/nawramm) ([#4198](https://github.com/paperless-ngx/paperless-ngx/pull/4198))
-   Fix: application of theme color vars at root [@shamoon](https://github.com/shamoon) ([#4193](https://github.com/paperless-ngx/paperless-ngx/pull/4193))
-   Enhancement: Allow the user the specify the export zip file name [@stumpylog](https://github.com/stumpylog) ([#4189](https://github.com/paperless-ngx/paperless-ngx/pull/4189))
-   Feature: Share links [@shamoon](https://github.com/shamoon) ([#3996](https://github.com/paperless-ngx/paperless-ngx/pull/3996))
-   Chore: change dark mode to use Bootstrap's color modes [@lkster](https://github.com/lkster) ([#4174](https://github.com/paperless-ngx/paperless-ngx/pull/4174))
-   Fix: support storage path placeholder via API [@shamoon](https://github.com/shamoon) ([#4179](https://github.com/paperless-ngx/paperless-ngx/pull/4179))
-   Fix: Logs the errors during thumbnail generation [@stumpylog](https://github.com/stumpylog) ([#4171](https://github.com/paperless-ngx/paperless-ngx/pull/4171))
-   Feature: New management command for fuzzy matching document content [@stumpylog](https://github.com/stumpylog) ([#4160](https://github.com/paperless-ngx/paperless-ngx/pull/4160))
-   Breaking: Drop support for Python 3.8 [@stumpylog](https://github.com/stumpylog) ([#4156](https://github.com/paperless-ngx/paperless-ngx/pull/4156))
-   Fix: dashboard widget card borders hidden by bkgd color [@shamoon](https://github.com/shamoon) ([#4155](https://github.com/paperless-ngx/paperless-ngx/pull/4155))
-   Enhancement: frontend better handle slow backend requests [@shamoon](https://github.com/shamoon) ([#4055](https://github.com/paperless-ngx/paperless-ngx/pull/4055))
-   Chore: Extend the live service utility for handling 503 errors [@stumpylog](https://github.com/stumpylog) ([#4143](https://github.com/paperless-ngx/paperless-ngx/pull/4143))
-   Chore: update docker image \& ci testing node to v18 [@shamoon](https://github.com/shamoon) ([#4149](https://github.com/paperless-ngx/paperless-ngx/pull/4149))
-   Fix: hide entire add user / group buttons if insufficient permissions [@shamoon](https://github.com/shamoon) ([#4133](https://github.com/paperless-ngx/paperless-ngx/pull/4133))
-   Enhancement: Improved error notifications [@shamoon](https://github.com/shamoon) ([#4062](https://github.com/paperless-ngx/paperless-ngx/pull/4062))
-   Feature: Official support for Python 3.11 [@stumpylog](https://github.com/stumpylog) ([#4146](https://github.com/paperless-ngx/paperless-ngx/pull/4146))
-   Chore: Unlock dependencies \& update them all [@stumpylog](https://github.com/stumpylog) ([#4142](https://github.com/paperless-ngx/paperless-ngx/pull/4142))
-   Change: PWA Manifest to Standalone Display [@swoga](https://github.com/swoga) ([#4129](https://github.com/paperless-ngx/paperless-ngx/pull/4129))
-   Enhancement: add --id-range for document_retagger [@kamilkosek](https://github.com/kamilkosek) ([#4080](https://github.com/paperless-ngx/paperless-ngx/pull/4080))
-   Enhancement: Add Afrikaans, Greek \& Norwegian languages [@shamoon](https://github.com/shamoon) ([#4088](https://github.com/paperless-ngx/paperless-ngx/pull/4088))
-   Enhancement: add task id to pre/post consume script as env [@andreheuer](https://github.com/andreheuer) ([#4037](https://github.com/paperless-ngx/paperless-ngx/pull/4037))
-   Enhancement: update bootstrap to v5.3.1 for backend static pages [@shamoon](https://github.com/shamoon) ([#4060](https://github.com/paperless-ngx/paperless-ngx/pull/4060))
-   Bump the frontend-jest-dependencies group in /src-ui with 4 updates [@dependabot](https://github.com/dependabot) ([#4112](https://github.com/paperless-ngx/paperless-ngx/pull/4112))
-   Bump tslib from 2.6.1 to 2.6.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#4108](https://github.com/paperless-ngx/paperless-ngx/pull/4108))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#4106](https://github.com/paperless-ngx/paperless-ngx/pull/4106))
-   Bump concurrently from 8.2.0 to 8.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#4111](https://github.com/paperless-ngx/paperless-ngx/pull/4111))
-   Bump [@<!---->types/node from 20.4.5 to 20.5.8 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.4.5 to 20.5.8 in /src-ui @dependabot) ([#4110](https://github.com/paperless-ngx/paperless-ngx/pull/4110))
-   Bump the frontend-angular-dependencies group in /src-ui with 19 updates [@dependabot](https://github.com/dependabot) ([#4104](https://github.com/paperless-ngx/paperless-ngx/pull/4104))
</details>

## paperless-ngx 1.17.4

### Bug Fixes

-   Fix: ghostscript rendering error doesn't trigger frontend failure message [@shamoon](https://github.com/shamoon) ([#4092](https://github.com/paperless-ngx/paperless-ngx/pull/4092))

### All App Changes

-   Fix: ghostscript rendering error doesn't trigger frontend failure message [@shamoon](https://github.com/shamoon) ([#4092](https://github.com/paperless-ngx/paperless-ngx/pull/4092))

## paperless-ngx 1.17.3

### Bug Fixes

-   Fix: When PDF/A rendering fails, add a consideration for the user to add args to override [@stumpylog](https://github.com/stumpylog) ([#4083](https://github.com/paperless-ngx/paperless-ngx/pull/4083))

### Dependencies

-   Chore: update frontend PDF viewer (including pdf-js) [@shamoon](https://github.com/shamoon) ([#4065](https://github.com/paperless-ngx/paperless-ngx/pull/4065))

### Maintenance

-   Dev: Upload code coverage in the same job [@stumpylog](https://github.com/stumpylog) ([#4084](https://github.com/paperless-ngx/paperless-ngx/pull/4084))

### All App Changes

<details>
<summary>3 changes</summary>

-   Fix: When PDF/A rendering fails, add a consideration for the user to add args to override [@stumpylog](https://github.com/stumpylog) ([#4083](https://github.com/paperless-ngx/paperless-ngx/pull/4083))
-   Chore: update frontend PDF viewer (including pdf-js) [@shamoon](https://github.com/shamoon) ([#4065](https://github.com/paperless-ngx/paperless-ngx/pull/4065))
-   Chore: Prepare for Python 3.11 support [@stumpylog](https://github.com/stumpylog) ([#4066](https://github.com/paperless-ngx/paperless-ngx/pull/4066))
</details>

## paperless-ngx 1.17.2

### Features

-   Enhancement: Allow to set a prefix for keys and channels in redis [@amo13](https://github.com/amo13) ([#3993](https://github.com/paperless-ngx/paperless-ngx/pull/3993))

### Bug Fixes

-   Fix: Increase the HTTP timeouts for Tika/Gotenberg to maximum task time [@stumpylog](https://github.com/stumpylog) ([#4061](https://github.com/paperless-ngx/paperless-ngx/pull/4061))
-   Fix: Allow adding an SSL certificate for IMAP SSL context [@stumpylog](https://github.com/stumpylog) ([#4048](https://github.com/paperless-ngx/paperless-ngx/pull/4048))
-   Fix: tag creation sometimes retained search text [@shamoon](https://github.com/shamoon) ([#4038](https://github.com/paperless-ngx/paperless-ngx/pull/4038))
-   Fix: enforce permissions on bulk_edit operations [@shamoon](https://github.com/shamoon) ([#4007](https://github.com/paperless-ngx/paperless-ngx/pull/4007))

### All App Changes

<details>
<summary>6 changes</summary>

-   Fix: Increase the HTTP timeouts for Tika/Gotenberg to maximum task time [@stumpylog](https://github.com/stumpylog) ([#4061](https://github.com/paperless-ngx/paperless-ngx/pull/4061))
-   Enhancement: disable / hide some UI buttons / elements if insufficient permissions, show errors [@shamoon](https://github.com/shamoon) ([#4014](https://github.com/paperless-ngx/paperless-ngx/pull/4014))
-   Fix: Allow adding an SSL certificate for IMAP SSL context [@stumpylog](https://github.com/stumpylog) ([#4048](https://github.com/paperless-ngx/paperless-ngx/pull/4048))
-   Fix: tag creation sometimes retained search text [@shamoon](https://github.com/shamoon) ([#4038](https://github.com/paperless-ngx/paperless-ngx/pull/4038))
-   Fix: enforce permissions on bulk_edit operations [@shamoon](https://github.com/shamoon) ([#4007](https://github.com/paperless-ngx/paperless-ngx/pull/4007))
-   Enhancement: Allow to set a prefix for keys and channels in redis [@amo13](https://github.com/amo13) ([#3993](https://github.com/paperless-ngx/paperless-ngx/pull/3993))
</details>

## paperless-ngx 1.17.1

### Features

-   Fix / Enhancement: restrict status messages by owner if set \& improve 404 page [@shamoon](https://github.com/shamoon) ([#3959](https://github.com/paperless-ngx/paperless-ngx/pull/3959))
-   Feature: Add Ukrainian translation [@shamoon](https://github.com/shamoon) ([#3941](https://github.com/paperless-ngx/paperless-ngx/pull/3941))

### Bug Fixes

-   Fix: handle ASN = 0 on frontend cards [@shamoon](https://github.com/shamoon) ([#3988](https://github.com/paperless-ngx/paperless-ngx/pull/3988))
-   Fix: improve light color filled primary button text legibility [@shamoon](https://github.com/shamoon) ([#3980](https://github.com/paperless-ngx/paperless-ngx/pull/3980))
-   Fix / Enhancement: restrict status messages by owner if set \& improve 404 page [@shamoon](https://github.com/shamoon) ([#3959](https://github.com/paperless-ngx/paperless-ngx/pull/3959))
-   Fix: handle very old date strings in correspondent list [@shamoon](https://github.com/shamoon) ([#3953](https://github.com/paperless-ngx/paperless-ngx/pull/3953))

### Documentation

-   docs(bare-metal): add new dependency [@bin101](https://github.com/bin101) ([#3931](https://github.com/paperless-ngx/paperless-ngx/pull/3931))

### Dependencies

-   Chore: Loosen Pipfile restriction on some packages and update them [@stumpylog](https://github.com/stumpylog) ([#3972](https://github.com/paperless-ngx/paperless-ngx/pull/3972))

### All App Changes

<details>
<summary>6 changes</summary>

-   Fix: handle ASN = 0 on frontend cards [@shamoon](https://github.com/shamoon) ([#3988](https://github.com/paperless-ngx/paperless-ngx/pull/3988))
-   Fix: improve light color filled primary button text legibility [@shamoon](https://github.com/shamoon) ([#3980](https://github.com/paperless-ngx/paperless-ngx/pull/3980))
-   Fix / Enhancement: restrict status messages by owner if set \& improve 404 page [@shamoon](https://github.com/shamoon) ([#3959](https://github.com/paperless-ngx/paperless-ngx/pull/3959))
-   Fix: handle very old date strings in correspondent list [@shamoon](https://github.com/shamoon) ([#3953](https://github.com/paperless-ngx/paperless-ngx/pull/3953))
-   Chore: Reduces the 2 mail tests flakiness [@stumpylog](https://github.com/stumpylog) ([#3949](https://github.com/paperless-ngx/paperless-ngx/pull/3949))
-   Feature: Add Ukrainian translation [@shamoon](https://github.com/shamoon) ([#3941](https://github.com/paperless-ngx/paperless-ngx/pull/3941))
</details>

## paperless-ngx 1.17.0

### Features

-   Add support for additional UK date formats [@brainrecursion](https://github.com/brainrecursion) ([#3887](https://github.com/paperless-ngx/paperless-ngx/pull/3887))
-   Add 'doc_pk' to PAPERLESS_FILENAME_FORMAT handling [@mechanarchy](https://github.com/mechanarchy) ([#3861](https://github.com/paperless-ngx/paperless-ngx/pull/3861))
-   Feature: hover buttons for saved view widgets [@shamoon](https://github.com/shamoon) ([#3875](https://github.com/paperless-ngx/paperless-ngx/pull/3875))
-   Feature: collate two single-sided multipage scans [@brakhane](https://github.com/brakhane) ([#3784](https://github.com/paperless-ngx/paperless-ngx/pull/3784))
-   Feature: include global and object-level permissions in export / import [@shamoon](https://github.com/shamoon) ([#3672](https://github.com/paperless-ngx/paperless-ngx/pull/3672))
-   Enhancement / Fix: Migrate encrypted png thumbnails to webp [@shamoon](https://github.com/shamoon) ([#3719](https://github.com/paperless-ngx/paperless-ngx/pull/3719))
-   Feature: Add Slovak translation [@shamoon](https://github.com/shamoon) ([#3722](https://github.com/paperless-ngx/paperless-ngx/pull/3722))

### Bug Fixes

-   Fix: cancel possibly slow queries on doc details [@shamoon](https://github.com/shamoon) ([#3925](https://github.com/paperless-ngx/paperless-ngx/pull/3925))
-   Fix: note creation / deletion should respect doc permissions [@shamoon](https://github.com/shamoon) ([#3903](https://github.com/paperless-ngx/paperless-ngx/pull/3903))
-   Fix: notes show persistent scrollbars [@shamoon](https://github.com/shamoon) ([#3904](https://github.com/paperless-ngx/paperless-ngx/pull/3904))
-   Fix: Provide SSL context to IMAP client [@stumpylog](https://github.com/stumpylog) ([#3886](https://github.com/paperless-ngx/paperless-ngx/pull/3886))
-   Fix/enhancement: permissions for mail rules \& accounts [@shamoon](https://github.com/shamoon) ([#3869](https://github.com/paperless-ngx/paperless-ngx/pull/3869))
-   Fix: Classifier special case when no items are set to automatic matching [@stumpylog](https://github.com/stumpylog) ([#3858](https://github.com/paperless-ngx/paperless-ngx/pull/3858))
-   Fix: issues with copy2 or copystat and SELinux permissions [@stumpylog](https://github.com/stumpylog) ([#3847](https://github.com/paperless-ngx/paperless-ngx/pull/3847))
-   Fix: Parsing office document timestamps [@stumpylog](https://github.com/stumpylog) ([#3836](https://github.com/paperless-ngx/paperless-ngx/pull/3836))
-   Fix: Add warning to install script need for permissions [@shamoon](https://github.com/shamoon) ([#3835](https://github.com/paperless-ngx/paperless-ngx/pull/3835))
-   Fix interaction between API and barcode archive serial number [@stumpylog](https://github.com/stumpylog) ([#3834](https://github.com/paperless-ngx/paperless-ngx/pull/3834))
-   Enhancement / Fix: Migrate encrypted png thumbnails to webp [@shamoon](https://github.com/shamoon) ([#3719](https://github.com/paperless-ngx/paperless-ngx/pull/3719))
-   Fix: add UI tour step padding [@hakimio](https://github.com/hakimio) ([#3791](https://github.com/paperless-ngx/paperless-ngx/pull/3791))
-   Fix: translate file tasks types in footer [@shamoon](https://github.com/shamoon) ([#3749](https://github.com/paperless-ngx/paperless-ngx/pull/3749))
-   Fix: limit ng-select size for addition of filter button [@shamoon](https://github.com/shamoon) ([#3731](https://github.com/paperless-ngx/paperless-ngx/pull/3731))

### Documentation

-   Documentation: improvements to grammar, spelling, indentation [@mechanarchy](https://github.com/mechanarchy) ([#3844](https://github.com/paperless-ngx/paperless-ngx/pull/3844))

### Maintenance

-   Bump stumpylog/image-cleaner-action from 0.1.0 to 0.2.0 [@dependabot](https://github.com/dependabot) ([#3910](https://github.com/paperless-ngx/paperless-ngx/pull/3910))
-   Chore: group frontend angular dependabot updates [@shamoon](https://github.com/shamoon) ([#3750](https://github.com/paperless-ngx/paperless-ngx/pull/3750))

### Dependencies

<details>
<summary>17 changes</summary>

-   Chore: Bump the frontend-angular-dependencies group in /src-ui with 11 updates [@shamoon](https://github.com/shamoon) ([#3918](https://github.com/paperless-ngx/paperless-ngx/pull/3918))
-   Bump stumpylog/image-cleaner-action from 0.1.0 to 0.2.0 [@dependabot](https://github.com/dependabot) ([#3910](https://github.com/paperless-ngx/paperless-ngx/pull/3910))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#3911](https://github.com/paperless-ngx/paperless-ngx/pull/3911))
-   Bump tslib from 2.6.0 to 2.6.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3909](https://github.com/paperless-ngx/paperless-ngx/pull/3909))
-   Bump jest-environment-jsdom from 29.5.0 to 29.6.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3916](https://github.com/paperless-ngx/paperless-ngx/pull/3916))
-   Bump [@<!---->types/node from 20.3.3 to 20.4.5 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.3.3 to 20.4.5 in /src-ui @dependabot) ([#3915](https://github.com/paperless-ngx/paperless-ngx/pull/3915))
-   Bump bootstrap from 5.3.0 to 5.3.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3914](https://github.com/paperless-ngx/paperless-ngx/pull/3914))
-   Bump [@<!---->playwright/test from 1.36.1 to 1.36.2 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.36.1 to 1.36.2 in /src-ui @dependabot) ([#3912](https://github.com/paperless-ngx/paperless-ngx/pull/3912))
-   Bump the frontend-jest-dependencies group in /src-ui with 1 update [@dependabot](https://github.com/dependabot) ([#3906](https://github.com/paperless-ngx/paperless-ngx/pull/3906))
-   Chore: Update dependencies [@stumpylog](https://github.com/stumpylog) ([#3883](https://github.com/paperless-ngx/paperless-ngx/pull/3883))
-   Chore: Update Python dependencies [@stumpylog](https://github.com/stumpylog) ([#3842](https://github.com/paperless-ngx/paperless-ngx/pull/3842))
-   Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#3826](https://github.com/paperless-ngx/paperless-ngx/pull/3826))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.60.1 to 6.1.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.60.1 to 6.1.0 in /src-ui @dependabot) ([#3829](https://github.com/paperless-ngx/paperless-ngx/pull/3829))
-   Bump jest and [@<!---->types/jest in /src-ui @dependabot](https://github.com/<!---->types/jest in /src-ui @dependabot) ([#3828](https://github.com/paperless-ngx/paperless-ngx/pull/3828))
-   Bump [@<!---->playwright/test from 1.36.0 to 1.36.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.36.0 to 1.36.1 in /src-ui @dependabot) ([#3827](https://github.com/paperless-ngx/paperless-ngx/pull/3827))
-   Bump semver from 5.7.1 to 5.7.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3793](https://github.com/paperless-ngx/paperless-ngx/pull/3793))
-   Chore: Bump Angular to v16 and other frontend packages [@dependabot](https://github.com/dependabot) ([#3727](https://github.com/paperless-ngx/paperless-ngx/pull/3727))
</details>

### All App Changes

<details>
<summary>35 changes</summary>

-   Fix: cancel possibly slow queries on doc details [@shamoon](https://github.com/shamoon) ([#3925](https://github.com/paperless-ngx/paperless-ngx/pull/3925))
-   [BUG] Set office document creation date with timezone, if it is naive [@a17t](https://github.com/a17t) ([#3760](https://github.com/paperless-ngx/paperless-ngx/pull/3760))
-   Fix: note creation / deletion should respect doc permissions [@shamoon](https://github.com/shamoon) ([#3903](https://github.com/paperless-ngx/paperless-ngx/pull/3903))
-   Chore: Bump the frontend-angular-dependencies group in /src-ui with 11 updates [@shamoon](https://github.com/shamoon) ([#3918](https://github.com/paperless-ngx/paperless-ngx/pull/3918))
-   Bump the frontend-eslint-dependencies group in /src-ui with 3 updates [@dependabot](https://github.com/dependabot) ([#3911](https://github.com/paperless-ngx/paperless-ngx/pull/3911))
-   Bump tslib from 2.6.0 to 2.6.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3909](https://github.com/paperless-ngx/paperless-ngx/pull/3909))
-   Bump jest-environment-jsdom from 29.5.0 to 29.6.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3916](https://github.com/paperless-ngx/paperless-ngx/pull/3916))
-   Bump [@<!---->types/node from 20.3.3 to 20.4.5 in /src-ui @dependabot](https://github.com/<!---->types/node from 20.3.3 to 20.4.5 in /src-ui @dependabot) ([#3915](https://github.com/paperless-ngx/paperless-ngx/pull/3915))
-   Bump bootstrap from 5.3.0 to 5.3.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3914](https://github.com/paperless-ngx/paperless-ngx/pull/3914))
-   Bump [@<!---->playwright/test from 1.36.1 to 1.36.2 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.36.1 to 1.36.2 in /src-ui @dependabot) ([#3912](https://github.com/paperless-ngx/paperless-ngx/pull/3912))
-   Bump the frontend-jest-dependencies group in /src-ui with 1 update [@dependabot](https://github.com/dependabot) ([#3906](https://github.com/paperless-ngx/paperless-ngx/pull/3906))
-   Fix: notes show persistent scrollbars [@shamoon](https://github.com/shamoon) ([#3904](https://github.com/paperless-ngx/paperless-ngx/pull/3904))
-   Add support for additional UK date formats [@brainrecursion](https://github.com/brainrecursion) ([#3887](https://github.com/paperless-ngx/paperless-ngx/pull/3887))
-   Add 'doc_pk' to PAPERLESS_FILENAME_FORMAT handling [@mechanarchy](https://github.com/mechanarchy) ([#3861](https://github.com/paperless-ngx/paperless-ngx/pull/3861))
-   Fix: Provide SSL context to IMAP client [@stumpylog](https://github.com/stumpylog) ([#3886](https://github.com/paperless-ngx/paperless-ngx/pull/3886))
-   Feature: hover buttons for saved view widgets [@shamoon](https://github.com/shamoon) ([#3875](https://github.com/paperless-ngx/paperless-ngx/pull/3875))
-   Fix/enhancement: permissions for mail rules \& accounts [@shamoon](https://github.com/shamoon) ([#3869](https://github.com/paperless-ngx/paperless-ngx/pull/3869))
-   Chore: typing improvements [@stumpylog](https://github.com/stumpylog) ([#3860](https://github.com/paperless-ngx/paperless-ngx/pull/3860))
-   Fix: Classifier special case when no items are set to automatic matching [@stumpylog](https://github.com/stumpylog) ([#3858](https://github.com/paperless-ngx/paperless-ngx/pull/3858))
-   Fix: issues with copy2 or copystat and SELinux permissions [@stumpylog](https://github.com/stumpylog) ([#3847](https://github.com/paperless-ngx/paperless-ngx/pull/3847))
-   Chore: Update Python dependencies [@stumpylog](https://github.com/stumpylog) ([#3842](https://github.com/paperless-ngx/paperless-ngx/pull/3842))
-   Feature: include global and object-level permissions in export / import [@shamoon](https://github.com/shamoon) ([#3672](https://github.com/paperless-ngx/paperless-ngx/pull/3672))
-   Fix: Parsing office document timestamps [@stumpylog](https://github.com/stumpylog) ([#3836](https://github.com/paperless-ngx/paperless-ngx/pull/3836))
-   Fix interaction between API and barcode archive serial number [@stumpylog](https://github.com/stumpylog) ([#3834](https://github.com/paperless-ngx/paperless-ngx/pull/3834))
-   Bump the frontend-angular-dependencies group in /src-ui with 16 updates [@dependabot](https://github.com/dependabot) ([#3826](https://github.com/paperless-ngx/paperless-ngx/pull/3826))
-   Enhancement / Fix: Migrate encrypted png thumbnails to webp [@shamoon](https://github.com/shamoon) ([#3719](https://github.com/paperless-ngx/paperless-ngx/pull/3719))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.60.1 to 6.1.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.60.1 to 6.1.0 in /src-ui @dependabot) ([#3829](https://github.com/paperless-ngx/paperless-ngx/pull/3829))
-   Bump jest and [@<!---->types/jest in /src-ui @dependabot](https://github.com/<!---->types/jest in /src-ui @dependabot) ([#3828](https://github.com/paperless-ngx/paperless-ngx/pull/3828))
-   Bump [@<!---->playwright/test from 1.36.0 to 1.36.1 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.36.0 to 1.36.1 in /src-ui @dependabot) ([#3827](https://github.com/paperless-ngx/paperless-ngx/pull/3827))
-   Bump semver from 5.7.1 to 5.7.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3793](https://github.com/paperless-ngx/paperless-ngx/pull/3793))
-   Fix: add UI tour step padding [@hakimio](https://github.com/hakimio) ([#3791](https://github.com/paperless-ngx/paperless-ngx/pull/3791))
-   Fix: translate file tasks types in footer [@shamoon](https://github.com/shamoon) ([#3749](https://github.com/paperless-ngx/paperless-ngx/pull/3749))
-   Feature: Add Slovak translation [@shamoon](https://github.com/shamoon) ([#3722](https://github.com/paperless-ngx/paperless-ngx/pull/3722))
-   Fix: limit ng-select size for addition of filter button [@shamoon](https://github.com/shamoon) ([#3731](https://github.com/paperless-ngx/paperless-ngx/pull/3731))
-   Chore: Bump Angular to v16 and other frontend packages [@dependabot](https://github.com/dependabot) ([#3727](https://github.com/paperless-ngx/paperless-ngx/pull/3727))
</details>

## paperless-ngx 1.16.5

### Features

-   Feature: support barcode upscaling for better detection of small barcodes [@bmachek](https://github.com/bmachek) ([#3655](https://github.com/paperless-ngx/paperless-ngx/pull/3655))

### Bug Fixes

-   Fix: owner removed when set_permissions passed on object create [@shamoon](https://github.com/shamoon) ([#3702](https://github.com/paperless-ngx/paperless-ngx/pull/3702))

### All App Changes

<details>
<summary>2 changes</summary>

-   Feature: support barcode upscaling for better detection of small barcodes [@bmachek](https://github.com/bmachek) ([#3655](https://github.com/paperless-ngx/paperless-ngx/pull/3655))
-   Fix: owner removed when set_permissions passed on object create [@shamoon](https://github.com/shamoon) ([#3702](https://github.com/paperless-ngx/paperless-ngx/pull/3702))
</details>

## paperless-ngx 1.16.4

### Bug Fixes

-   Fix: prevent button wrapping when sidebar narrows in MS Edge [@shamoon](https://github.com/shamoon) ([#3682](https://github.com/paperless-ngx/paperless-ngx/pull/3682))
-   Fix: Handling for filenames with non-ascii and no content attribute [@stumpylog](https://github.com/stumpylog) ([#3695](https://github.com/paperless-ngx/paperless-ngx/pull/3695))
-   Fix: Generation of thumbnails for existing stored emails [@stumpylog](https://github.com/stumpylog) ([#3696](https://github.com/paperless-ngx/paperless-ngx/pull/3696))
-   Fix: Use row gap for filter editor [@kleinweby](https://github.com/kleinweby) ([#3662](https://github.com/paperless-ngx/paperless-ngx/pull/3662))

### Documentation

-   Documentation: update API docs re permissions [@shamoon](https://github.com/shamoon) ([#3697](https://github.com/paperless-ngx/paperless-ngx/pull/3697))

### Maintenance

-   Chore: Updates codecov configuration for the flag settings and notification delay [@stumpylog](https://github.com/stumpylog) ([#3656](https://github.com/paperless-ngx/paperless-ngx/pull/3656))

### All App Changes

<details>
<summary>4 changes</summary>

-   Fix: prevent button wrapping when sidebar narrows in MS Edge [@shamoon](https://github.com/shamoon) ([#3682](https://github.com/paperless-ngx/paperless-ngx/pull/3682))
-   Fix: Handling for filenames with non-ascii and no content attribute [@stumpylog](https://github.com/stumpylog) ([#3695](https://github.com/paperless-ngx/paperless-ngx/pull/3695))
-   Fix: Generation of thumbnails for existing stored emails [@stumpylog](https://github.com/stumpylog) ([#3696](https://github.com/paperless-ngx/paperless-ngx/pull/3696))
-   Fix: Use row gap for filter editor [@kleinweby](https://github.com/kleinweby) ([#3662](https://github.com/paperless-ngx/paperless-ngx/pull/3662))
</details>

## paperless-ngx 1.16.3

### Bug Fixes

-   Fix: Set user and home environment through supervisord [@stumpylog](https://github.com/stumpylog) ([#3638](https://github.com/paperless-ngx/paperless-ngx/pull/3638))
-   Fix: Ignore errors when trying to copy the original file's stats [@stumpylog](https://github.com/stumpylog) ([#3652](https://github.com/paperless-ngx/paperless-ngx/pull/3652))
-   Fix: Copy default thumbnail if thumbnail generation fails [@plu](https://github.com/plu) ([#3632](https://github.com/paperless-ngx/paperless-ngx/pull/3632))
-   Fix: Set user and home environment through supervisord [@stumpylog](https://github.com/stumpylog) ([#3638](https://github.com/paperless-ngx/paperless-ngx/pull/3638))
-   Fix: Fix quick install with external database not being fully ready [@stumpylog](https://github.com/stumpylog) ([#3637](https://github.com/paperless-ngx/paperless-ngx/pull/3637))

### Maintenance

-   Chore: Update default Postgres version for new installs [@stumpylog](https://github.com/stumpylog) ([#3640](https://github.com/paperless-ngx/paperless-ngx/pull/3640))

### All App Changes

<details>
<summary>2 changes</summary>

-   Fix: Ignore errors when trying to copy the original file's stats [@stumpylog](https://github.com/stumpylog) ([#3652](https://github.com/paperless-ngx/paperless-ngx/pull/3652))
-   Fix: Copy default thumbnail if thumbnail generation fails [@plu](https://github.com/plu) ([#3632](https://github.com/paperless-ngx/paperless-ngx/pull/3632))
</details>

## paperless-ngx 1.16.2

### Bug Fixes

-   Fix: Increase httpx operation timeouts to 30s [@stumpylog](https://github.com/stumpylog) ([#3627](https://github.com/paperless-ngx/paperless-ngx/pull/3627))
-   Fix: Better error handling and checking when parsing documents via Tika [@stumpylog](https://github.com/stumpylog) ([#3617](https://github.com/paperless-ngx/paperless-ngx/pull/3617))

### Development

-   Development: frontend unit testing [@shamoon](https://github.com/shamoon) ([#3597](https://github.com/paperless-ngx/paperless-ngx/pull/3597))

### Maintenance

-   Chore: Bumps the CI/Docker pipenv version [@stumpylog](https://github.com/stumpylog) ([#3622](https://github.com/paperless-ngx/paperless-ngx/pull/3622))
-   Chore: Set CI artifact retention days [@stumpylog](https://github.com/stumpylog) ([#3621](https://github.com/paperless-ngx/paperless-ngx/pull/3621))

### All App Changes

<details>
<summary>3 changes</summary>

-   Fix: Increase httpx operation timeouts to 30s [@stumpylog](https://github.com/stumpylog) ([#3627](https://github.com/paperless-ngx/paperless-ngx/pull/3627))
-   Fix: Better error handling and checking when parsing documents via Tika [@stumpylog](https://github.com/stumpylog) ([#3617](https://github.com/paperless-ngx/paperless-ngx/pull/3617))
-   Development: frontend unit testing [@shamoon](https://github.com/shamoon) ([#3597](https://github.com/paperless-ngx/paperless-ngx/pull/3597))
</details>

## paperless-ngx 1.16.1

### Bug Fixes

-   Fix: PIL ImportError on ARM devices with Docker [@stumpylog](https://github.com/stumpylog) ([#3605](https://github.com/paperless-ngx/paperless-ngx/pull/3605))

### Maintenance

-   Chore: Enable the image cleanup action [@stumpylog](https://github.com/stumpylog) ([#3606](https://github.com/paperless-ngx/paperless-ngx/pull/3606))

## paperless-ngx 1.16.0

### Notable Changes

-   Chore: Update base image to Debian bookworm [@stumpylog](https://github.com/stumpylog) ([#3469](https://github.com/paperless-ngx/paperless-ngx/pull/3469))

### Features

-   Feature: Update to a simpler Tika library [@stumpylog](https://github.com/stumpylog) ([#3517](https://github.com/paperless-ngx/paperless-ngx/pull/3517))
-   Feature: Allow to filter documents by original filename and checksum [@jayme-github](https://github.com/jayme-github) ([#3485](https://github.com/paperless-ngx/paperless-ngx/pull/3485))

### Bug Fixes

-   Fix: return user first / last name from backend [@shamoon](https://github.com/shamoon) ([#3579](https://github.com/paperless-ngx/paperless-ngx/pull/3579))
-   Fix use of `PAPERLESS_DB_TIMEOUT` for all db types [@shamoon](https://github.com/shamoon) ([#3576](https://github.com/paperless-ngx/paperless-ngx/pull/3576))
-   Fix: handle mail rules with no filters on some imap servers [@shamoon](https://github.com/shamoon) ([#3554](https://github.com/paperless-ngx/paperless-ngx/pull/3554))

### Dependencies

-   Chore: Python dependency updates (celery 5.3.0 in particular) [@stumpylog](https://github.com/stumpylog) ([#3584](https://github.com/paperless-ngx/paperless-ngx/pull/3584))

### All App Changes

<details>
<summary>8 changes</summary>

-   Chore: Python dependency updates (celery 5.3.0 in particular) [@stumpylog](https://github.com/stumpylog) ([#3584](https://github.com/paperless-ngx/paperless-ngx/pull/3584))
-   Fix: return user first / last name from backend [@shamoon](https://github.com/shamoon) ([#3579](https://github.com/paperless-ngx/paperless-ngx/pull/3579))
-   Fix use of `PAPERLESS_DB_TIMEOUT` for all db types [@shamoon](https://github.com/shamoon) ([#3576](https://github.com/paperless-ngx/paperless-ngx/pull/3576))
-   Fix: handle mail rules with no filters on some imap servers [@shamoon](https://github.com/shamoon) ([#3554](https://github.com/paperless-ngx/paperless-ngx/pull/3554))
-   Chore: Copy file stats from original file [@stumpylog](https://github.com/stumpylog) ([#3551](https://github.com/paperless-ngx/paperless-ngx/pull/3551))
-   Chore: Adds test for barcode ASN when it already exists [@stumpylog](https://github.com/stumpylog) ([#3550](https://github.com/paperless-ngx/paperless-ngx/pull/3550))
-   Feature: Update to a simpler Tika library [@stumpylog](https://github.com/stumpylog) ([#3517](https://github.com/paperless-ngx/paperless-ngx/pull/3517))
-   Feature: Allow to filter documents by original filename and checksum [@jayme-github](https://github.com/jayme-github) ([#3485](https://github.com/paperless-ngx/paperless-ngx/pull/3485))
</details>

## paperless-ngx 1.15.1

### Bug Fixes

-   Fix incorrect colors in v1.15.0 [@shamoon](https://github.com/shamoon) ([#3523](https://github.com/paperless-ngx/paperless-ngx/pull/3523))

### All App Changes

-   Fix incorrect colors in v1.15.0 [@shamoon](https://github.com/shamoon) ([#3523](https://github.com/paperless-ngx/paperless-ngx/pull/3523))

## paperless-ngx 1.15.0

### Features

-   Feature: quick filters from document detail [@shamoon](https://github.com/shamoon) ([#3476](https://github.com/paperless-ngx/paperless-ngx/pull/3476))
-   Feature: Add explanations to relative dates [@shamoon](https://github.com/shamoon) ([#3471](https://github.com/paperless-ngx/paperless-ngx/pull/3471))
-   Enhancement: paginate frontend tasks [@shamoon](https://github.com/shamoon) ([#3445](https://github.com/paperless-ngx/paperless-ngx/pull/3445))
-   Feature: Better encapsulation of barcode logic [@stumpylog](https://github.com/stumpylog) ([#3425](https://github.com/paperless-ngx/paperless-ngx/pull/3425))
-   Enhancement: Improve frontend error handling [@shamoon](https://github.com/shamoon) ([#3413](https://github.com/paperless-ngx/paperless-ngx/pull/3413))

### Bug Fixes

-   Fix: KeyError error on unauthenticated API calls \& persist authentication when enabled [@ajgon](https://github.com/ajgon) ([#3516](https://github.com/paperless-ngx/paperless-ngx/pull/3516))
-   Fix: exclude consumer \& AnonymousUser users from export manifest [@shamoon](https://github.com/shamoon) ([#3487](https://github.com/paperless-ngx/paperless-ngx/pull/3487))
-   Fix: prevent date suggestion search if disabled [@shamoon](https://github.com/shamoon) ([#3472](https://github.com/paperless-ngx/paperless-ngx/pull/3472))
-   Sync Pipfile.lock based on latest Pipfile [@adamantike](https://github.com/adamantike) ([#3475](https://github.com/paperless-ngx/paperless-ngx/pull/3475))
-   Fix: DocumentSerializer should return correct original filename [@jayme-github](https://github.com/jayme-github) ([#3473](https://github.com/paperless-ngx/paperless-ngx/pull/3473))
-   consumer.py: read from original file (instead of temp copy) [@chrisblech](https://github.com/chrisblech) ([#3466](https://github.com/paperless-ngx/paperless-ngx/pull/3466))
-   Bugfix: Catch an nltk AttributeError and handle it [@stumpylog](https://github.com/stumpylog) ([#3453](https://github.com/paperless-ngx/paperless-ngx/pull/3453))

### Documentation

-   Adding doc on how to setup Fail2ban [@GuillaumeHullin](https://github.com/GuillaumeHullin) ([#3414](https://github.com/paperless-ngx/paperless-ngx/pull/3414))
-   Docs: Fix typo [@MarcelBochtler](https://github.com/MarcelBochtler) ([#3437](https://github.com/paperless-ngx/paperless-ngx/pull/3437))
-   [Documentation] Move nginx [@shamoon](https://github.com/shamoon) ([#3420](https://github.com/paperless-ngx/paperless-ngx/pull/3420))
-   Documentation: Note possible dependency removal for bare metal [@stumpylog](https://github.com/stumpylog) ([#3408](https://github.com/paperless-ngx/paperless-ngx/pull/3408))

### Development

-   Development: migrate frontend tests to playwright [@shamoon](https://github.com/shamoon) ([#3401](https://github.com/paperless-ngx/paperless-ngx/pull/3401))

### Dependencies

<details>
<summary>10 changes</summary>

-   Bump eslint from 8.39.0 to 8.41.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3513](https://github.com/paperless-ngx/paperless-ngx/pull/3513))
-   Bump concurrently from 8.0.1 to 8.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3510](https://github.com/paperless-ngx/paperless-ngx/pull/3510))
-   Bump [@<!---->ng-bootstrap/ng-bootstrap from 14.1.0 to 14.2.0 in /src-ui @dependabot](https://github.com/<!---->ng-bootstrap/ng-bootstrap from 14.1.0 to 14.2.0 in /src-ui @dependabot) ([#3507](https://github.com/paperless-ngx/paperless-ngx/pull/3507))
-   Bump [@<!---->popperjs/core from 2.11.7 to 2.11.8 in /src-ui @dependabot](https://github.com/<!---->popperjs/core from 2.11.7 to 2.11.8 in /src-ui @dependabot) ([#3508](https://github.com/paperless-ngx/paperless-ngx/pull/3508))
-   Bump [@<!---->typescript-eslint/parser from 5.59.2 to 5.59.8 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.59.2 to 5.59.8 in /src-ui @dependabot) ([#3505](https://github.com/paperless-ngx/paperless-ngx/pull/3505))
-   Bump bootstrap from 5.2.3 to 5.3.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3497](https://github.com/paperless-ngx/paperless-ngx/pull/3497))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.59.2 to 5.59.8 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.59.2 to 5.59.8 in /src-ui @dependabot) ([#3500](https://github.com/paperless-ngx/paperless-ngx/pull/3500))
-   Bump tslib from 2.5.0 to 2.5.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3501](https://github.com/paperless-ngx/paperless-ngx/pull/3501))
-   Bump [@<!---->types/node from 18.16.3 to 20.2.5 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.16.3 to 20.2.5 in /src-ui @dependabot) ([#3498](https://github.com/paperless-ngx/paperless-ngx/pull/3498))
-   Bump [@<!---->playwright/test from 1.33.0 to 1.34.3 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.33.0 to 1.34.3 in /src-ui @dependabot) ([#3499](https://github.com/paperless-ngx/paperless-ngx/pull/3499))
</details>

### All App Changes

<details>
<summary>22 changes</summary>

-   Fix: KeyError error on unauthenticated API calls \& persist authentication when enabled [@ajgon](https://github.com/ajgon) ([#3516](https://github.com/paperless-ngx/paperless-ngx/pull/3516))
-   Bump eslint from 8.39.0 to 8.41.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3513](https://github.com/paperless-ngx/paperless-ngx/pull/3513))
-   Bump concurrently from 8.0.1 to 8.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3510](https://github.com/paperless-ngx/paperless-ngx/pull/3510))
-   Bump [@<!---->ng-bootstrap/ng-bootstrap from 14.1.0 to 14.2.0 in /src-ui @dependabot](https://github.com/<!---->ng-bootstrap/ng-bootstrap from 14.1.0 to 14.2.0 in /src-ui @dependabot) ([#3507](https://github.com/paperless-ngx/paperless-ngx/pull/3507))
-   Bump [@<!---->popperjs/core from 2.11.7 to 2.11.8 in /src-ui @dependabot](https://github.com/<!---->popperjs/core from 2.11.7 to 2.11.8 in /src-ui @dependabot) ([#3508](https://github.com/paperless-ngx/paperless-ngx/pull/3508))
-   Bump [@<!---->typescript-eslint/parser from 5.59.2 to 5.59.8 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.59.2 to 5.59.8 in /src-ui @dependabot) ([#3505](https://github.com/paperless-ngx/paperless-ngx/pull/3505))
-   Bump bootstrap from 5.2.3 to 5.3.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3497](https://github.com/paperless-ngx/paperless-ngx/pull/3497))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.59.2 to 5.59.8 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.59.2 to 5.59.8 in /src-ui @dependabot) ([#3500](https://github.com/paperless-ngx/paperless-ngx/pull/3500))
-   Bump tslib from 2.5.0 to 2.5.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#3501](https://github.com/paperless-ngx/paperless-ngx/pull/3501))
-   Bump [@<!---->types/node from 18.16.3 to 20.2.5 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.16.3 to 20.2.5 in /src-ui @dependabot) ([#3498](https://github.com/paperless-ngx/paperless-ngx/pull/3498))
-   Bump [@<!---->playwright/test from 1.33.0 to 1.34.3 in /src-ui @dependabot](https://github.com/<!---->playwright/test from 1.33.0 to 1.34.3 in /src-ui @dependabot) ([#3499](https://github.com/paperless-ngx/paperless-ngx/pull/3499))
-   Feature: quick filters from document detail [@shamoon](https://github.com/shamoon) ([#3476](https://github.com/paperless-ngx/paperless-ngx/pull/3476))
-   Fix: exclude consumer \& AnonymousUser users from export manifest [@shamoon](https://github.com/shamoon) ([#3487](https://github.com/paperless-ngx/paperless-ngx/pull/3487))
-   Fix: prevent date suggestion search if disabled [@shamoon](https://github.com/shamoon) ([#3472](https://github.com/paperless-ngx/paperless-ngx/pull/3472))
-   Feature: Add explanations to relative dates [@shamoon](https://github.com/shamoon) ([#3471](https://github.com/paperless-ngx/paperless-ngx/pull/3471))
-   Fix: DocumentSerializer should return correct original filename [@jayme-github](https://github.com/jayme-github) ([#3473](https://github.com/paperless-ngx/paperless-ngx/pull/3473))
-   consumer.py: read from original file (instead of temp copy) [@chrisblech](https://github.com/chrisblech) ([#3466](https://github.com/paperless-ngx/paperless-ngx/pull/3466))
-   Bugfix: Catch an nltk AttributeError and handle it [@stumpylog](https://github.com/stumpylog) ([#3453](https://github.com/paperless-ngx/paperless-ngx/pull/3453))
-   Chore: Improves the logging mixin and allows it to be typed better [@stumpylog](https://github.com/stumpylog) ([#3451](https://github.com/paperless-ngx/paperless-ngx/pull/3451))
-   Enhancement: paginate frontend tasks [@shamoon](https://github.com/shamoon) ([#3445](https://github.com/paperless-ngx/paperless-ngx/pull/3445))
-   Add SSL Support for MariaDB [@kimdre](https://github.com/kimdre) ([#3444](https://github.com/paperless-ngx/paperless-ngx/pull/3444))
-   Enhancement: Improve frontend error handling [@shamoon](https://github.com/shamoon) ([#3413](https://github.com/paperless-ngx/paperless-ngx/pull/3413))
</details>

## paperless-ngx 1.14.5

### Features

-   Feature: owner filtering [@shamoon](https://github.com/shamoon) ([#3309](https://github.com/paperless-ngx/paperless-ngx/pull/3309))
-   Enhancement: dynamic counts include all pages, hide for Any [@shamoon](https://github.com/shamoon) ([#3329](https://github.com/paperless-ngx/paperless-ngx/pull/3329))
-   Enhancement: save tour completion, hide welcome widget [@shamoon](https://github.com/shamoon) ([#3321](https://github.com/paperless-ngx/paperless-ngx/pull/3321))

### Bug Fixes

-   Fix: Adds better handling for files with invalid utf8 content [@stumpylog](https://github.com/stumpylog) ([#3387](https://github.com/paperless-ngx/paperless-ngx/pull/3387))
-   Fix: respect permissions for autocomplete suggestions [@shamoon](https://github.com/shamoon) ([#3359](https://github.com/paperless-ngx/paperless-ngx/pull/3359))
-   Fix: Transition to new library for finding IPs for failed logins [@stumpylog](https://github.com/stumpylog) ([#3382](https://github.com/paperless-ngx/paperless-ngx/pull/3382))
-   [Security] Render frontend text as plain text [@shamoon](https://github.com/shamoon) ([#3366](https://github.com/paperless-ngx/paperless-ngx/pull/3366))
-   Fix: default frontend to current owner, allow setting no owner on create [@shamoon](https://github.com/shamoon) ([#3347](https://github.com/paperless-ngx/paperless-ngx/pull/3347))
-   Fix: dont perform mail actions when rule filename filter not met [@shamoon](https://github.com/shamoon) ([#3336](https://github.com/paperless-ngx/paperless-ngx/pull/3336))
-   Fix: permission-aware bulk editing in 1.14.1+ [@shamoon](https://github.com/shamoon) ([#3345](https://github.com/paperless-ngx/paperless-ngx/pull/3345))

### Maintenance

-   Chore: Rework workflows [@stumpylog](https://github.com/stumpylog) ([#3242](https://github.com/paperless-ngx/paperless-ngx/pull/3242))

### Dependencies

-   Chore: Upgrade channels to v4 [@stumpylog](https://github.com/stumpylog) ([#3383](https://github.com/paperless-ngx/paperless-ngx/pull/3383))
-   Chore: Upgrades Python dependencies to their latest allowed versions [@stumpylog](https://github.com/stumpylog) ([#3365](https://github.com/paperless-ngx/paperless-ngx/pull/3365))

### All App Changes

<details>
<summary>13 changes</summary>

-   Fix: Adds better handling for files with invalid utf8 content [@stumpylog](https://github.com/stumpylog) ([#3387](https://github.com/paperless-ngx/paperless-ngx/pull/3387))
-   Fix: respect permissions for autocomplete suggestions [@shamoon](https://github.com/shamoon) ([#3359](https://github.com/paperless-ngx/paperless-ngx/pull/3359))
-   Chore: Upgrade channels to v4 [@stumpylog](https://github.com/stumpylog) ([#3383](https://github.com/paperless-ngx/paperless-ngx/pull/3383))
-   Fix: Transition to new library for finding IPs for failed logins [@stumpylog](https://github.com/stumpylog) ([#3382](https://github.com/paperless-ngx/paperless-ngx/pull/3382))
-   Feature: owner filtering [@shamoon](https://github.com/shamoon) ([#3309](https://github.com/paperless-ngx/paperless-ngx/pull/3309))
-   [Security] Render frontend text as plain text [@shamoon](https://github.com/shamoon) ([#3366](https://github.com/paperless-ngx/paperless-ngx/pull/3366))
-   Enhancement: dynamic counts include all pages, hide for Any [@shamoon](https://github.com/shamoon) ([#3329](https://github.com/paperless-ngx/paperless-ngx/pull/3329))
-   Fix: default frontend to current owner, allow setting no owner on create [@shamoon](https://github.com/shamoon) ([#3347](https://github.com/paperless-ngx/paperless-ngx/pull/3347))
-   [Fix] Position:fixed for .global-dropzone-overlay [@denilsonsa](https://github.com/denilsonsa) ([#3367](https://github.com/paperless-ngx/paperless-ngx/pull/3367))
-   Fix: dont perform mail actions when rule filename filter not met [@shamoon](https://github.com/shamoon) ([#3336](https://github.com/paperless-ngx/paperless-ngx/pull/3336))
-   Enhancement: save tour completion, hide welcome widget [@shamoon](https://github.com/shamoon) ([#3321](https://github.com/paperless-ngx/paperless-ngx/pull/3321))
-   Fix: permission-aware bulk editing in 1.14.1+ [@shamoon](https://github.com/shamoon) ([#3345](https://github.com/paperless-ngx/paperless-ngx/pull/3345))
-   Fix: Add proper testing for \*\_\_id\_\_in testing [@shamoon](https://github.com/shamoon) ([#3315](https://github.com/paperless-ngx/paperless-ngx/pull/3315))
</details>

## paperless-ngx 1.14.4

### Bug Fixes

-   Fix: Inversion in tagged mail searching [@stumpylog](https://github.com/stumpylog) ([#3305](https://github.com/paperless-ngx/paperless-ngx/pull/3305))
-   Fix dynamic count labels hidden in light mode [@shamoon](https://github.com/shamoon) ([#3303](https://github.com/paperless-ngx/paperless-ngx/pull/3303))

### All App Changes

<details>
<summary>3 changes</summary>

-   New Crowdin updates [@paperlessngx-bot](https://github.com/paperlessngx-bot) ([#3298](https://github.com/paperless-ngx/paperless-ngx/pull/3298))
-   Fix: Inversion in tagged mail searching [@stumpylog](https://github.com/stumpylog) ([#3305](https://github.com/paperless-ngx/paperless-ngx/pull/3305))
-   Fix dynamic count labels hidden in light mode [@shamoon](https://github.com/shamoon) ([#3303](https://github.com/paperless-ngx/paperless-ngx/pull/3303))
</details>

## paperless-ngx 1.14.3

### Features

-   Enhancement: better keyboard nav for filter/edit dropdowns [@shamoon](https://github.com/shamoon) ([#3227](https://github.com/paperless-ngx/paperless-ngx/pull/3227))

### Bug Fixes

-   Bump filelock from 3.10.2 to 3.12.0 to fix permissions bug [@rbrownwsws](https://github.com/rbrownwsws) ([#3282](https://github.com/paperless-ngx/paperless-ngx/pull/3282))
-   Fix: Handle cases where media files aren't all in the same filesystem [@stumpylog](https://github.com/stumpylog) ([#3261](https://github.com/paperless-ngx/paperless-ngx/pull/3261))
-   Fix: Prevent erroneous warning when starting container [@stumpylog](https://github.com/stumpylog) ([#3262](https://github.com/paperless-ngx/paperless-ngx/pull/3262))
-   Retain doc changes on tab switch after refresh doc [@shamoon](https://github.com/shamoon) ([#3243](https://github.com/paperless-ngx/paperless-ngx/pull/3243))
-   Fix: Don't send Gmail related setting if the server doesn't support it [@stumpylog](https://github.com/stumpylog) ([#3240](https://github.com/paperless-ngx/paperless-ngx/pull/3240))
-   Fix: close all docs on logout [@shamoon](https://github.com/shamoon) ([#3232](https://github.com/paperless-ngx/paperless-ngx/pull/3232))
-   Fix: Respect superuser for advanced queries, test coverage for object perms [@shamoon](https://github.com/shamoon) ([#3222](https://github.com/paperless-ngx/paperless-ngx/pull/3222))
-   Fix: ALLOWED_HOSTS logic being overwritten when \* is set [@ikaruswill](https://github.com/ikaruswill) ([#3218](https://github.com/paperless-ngx/paperless-ngx/pull/3218))

### Dependencies

<details>
<summary>7 changes</summary>

-   Bump eslint from 8.38.0 to 8.39.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3276](https://github.com/paperless-ngx/paperless-ngx/pull/3276))
-   Bump [@<!---->typescript-eslint/parser from 5.58.0 to 5.59.2 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.58.0 to 5.59.2 in /src-ui @dependabot) ([#3278](https://github.com/paperless-ngx/paperless-ngx/pull/3278))
-   Bump [@<!---->types/node from 18.15.11 to 18.16.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.15.11 to 18.16.3 in /src-ui @dependabot) ([#3275](https://github.com/paperless-ngx/paperless-ngx/pull/3275))
-   Bump rxjs from 7.8.0 to 7.8.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3277](https://github.com/paperless-ngx/paperless-ngx/pull/3277))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.58.0 to 5.59.2 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.58.0 to 5.59.2 in /src-ui @dependabot) ([#3274](https://github.com/paperless-ngx/paperless-ngx/pull/3274))
-   Bump cypress from 12.9.0 to 12.11.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3268](https://github.com/paperless-ngx/paperless-ngx/pull/3268))
-   Bulk bump angular packages to 15.2.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#3270](https://github.com/paperless-ngx/paperless-ngx/pull/3270))
</details>

### All App Changes

<details>
<summary>14 changes</summary>

-   Bump eslint from 8.38.0 to 8.39.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3276](https://github.com/paperless-ngx/paperless-ngx/pull/3276))
-   Bump [@<!---->typescript-eslint/parser from 5.58.0 to 5.59.2 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.58.0 to 5.59.2 in /src-ui @dependabot) ([#3278](https://github.com/paperless-ngx/paperless-ngx/pull/3278))
-   Bump [@<!---->types/node from 18.15.11 to 18.16.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.15.11 to 18.16.3 in /src-ui @dependabot) ([#3275](https://github.com/paperless-ngx/paperless-ngx/pull/3275))
-   Bump rxjs from 7.8.0 to 7.8.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#3277](https://github.com/paperless-ngx/paperless-ngx/pull/3277))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.58.0 to 5.59.2 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.58.0 to 5.59.2 in /src-ui @dependabot) ([#3274](https://github.com/paperless-ngx/paperless-ngx/pull/3274))
-   Bump cypress from 12.9.0 to 12.11.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#3268](https://github.com/paperless-ngx/paperless-ngx/pull/3268))
-   Bulk bump angular packages to 15.2.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#3270](https://github.com/paperless-ngx/paperless-ngx/pull/3270))
-   Fix: Handle cases where media files aren't all in the same filesystem [@stumpylog](https://github.com/stumpylog) ([#3261](https://github.com/paperless-ngx/paperless-ngx/pull/3261))
-   Retain doc changes on tab switch after refresh doc [@shamoon](https://github.com/shamoon) ([#3243](https://github.com/paperless-ngx/paperless-ngx/pull/3243))
-   Fix: Don't send Gmail related setting if the server doesn't support it [@stumpylog](https://github.com/stumpylog) ([#3240](https://github.com/paperless-ngx/paperless-ngx/pull/3240))
-   Fix: close all docs on logout [@shamoon](https://github.com/shamoon) ([#3232](https://github.com/paperless-ngx/paperless-ngx/pull/3232))
-   Enhancement: better keyboard nav for filter/edit dropdowns [@shamoon](https://github.com/shamoon) ([#3227](https://github.com/paperless-ngx/paperless-ngx/pull/3227))
-   Fix: Respect superuser for advanced queries, test coverage for object perms [@shamoon](https://github.com/shamoon) ([#3222](https://github.com/paperless-ngx/paperless-ngx/pull/3222))
-   Fix: ALLOWED_HOSTS logic being overwritten when \* is set [@ikaruswill](https://github.com/ikaruswill) ([#3218](https://github.com/paperless-ngx/paperless-ngx/pull/3218))
</details>

## paperless-ngx 1.14.2

### Features

-   Feature: Finnish translation [@shamoon](https://github.com/shamoon) ([#3215](https://github.com/paperless-ngx/paperless-ngx/pull/3215))

### Bug Fixes

-   Fix: Load saved views from app frame, not dashboard [@shamoon](https://github.com/shamoon) ([#3211](https://github.com/paperless-ngx/paperless-ngx/pull/3211))
-   Fix: advanced search or date searching + doc type/correspondent/storage path broken [@shamoon](https://github.com/shamoon) ([#3209](https://github.com/paperless-ngx/paperless-ngx/pull/3209))
-   Fix MixedContentTypeError in add_inbox_tags handler [@e1mo](https://github.com/e1mo) ([#3212](https://github.com/paperless-ngx/paperless-ngx/pull/3212))

### All App Changes

<details>
<summary>4 changes</summary>

-   Feature: Finnish translation [@shamoon](https://github.com/shamoon) ([#3215](https://github.com/paperless-ngx/paperless-ngx/pull/3215))
-   Fix: Load saved views from app frame, not dashboard [@shamoon](https://github.com/shamoon) ([#3211](https://github.com/paperless-ngx/paperless-ngx/pull/3211))
-   Fix: advanced search or date searching + doc type/correspondent/storage path broken [@shamoon](https://github.com/shamoon) ([#3209](https://github.com/paperless-ngx/paperless-ngx/pull/3209))
-   Fix MixedContentTypeError in add_inbox_tags handler [@e1mo](https://github.com/e1mo) ([#3212](https://github.com/paperless-ngx/paperless-ngx/pull/3212))
</details>

## paperless-ngx 1.14.1

### Bug Fixes

-   Fix: reduce frequency of permissions queries to speed up v1.14.0 [@shamoon](https://github.com/shamoon) ([#3201](https://github.com/paperless-ngx/paperless-ngx/pull/3201))
-   Fix: permissions-aware statistics [@shamoon](https://github.com/shamoon) ([#3199](https://github.com/paperless-ngx/paperless-ngx/pull/3199))
-   Fix: Use document owner for matching if set [@shamoon](https://github.com/shamoon) ([#3198](https://github.com/paperless-ngx/paperless-ngx/pull/3198))
-   Fix: respect permissions on document view actions [@shamoon](https://github.com/shamoon) ([#3174](https://github.com/paperless-ngx/paperless-ngx/pull/3174))
-   Increment API version for 1.14.1+ [@shamoon](https://github.com/shamoon) ([#3191](https://github.com/paperless-ngx/paperless-ngx/pull/3191))
-   Fix: dropdown Private items with empty set [@shamoon](https://github.com/shamoon) ([#3189](https://github.com/paperless-ngx/paperless-ngx/pull/3189))
-   Documentation: add note for macOS [@shamoon](https://github.com/shamoon) ([#3190](https://github.com/paperless-ngx/paperless-ngx/pull/3190))
-   Fix: make the importer a little more robust against some errors [@stumpylog](https://github.com/stumpylog) ([#3188](https://github.com/paperless-ngx/paperless-ngx/pull/3188))
-   Fix: Specify backend for auto-login [@shamoon](https://github.com/shamoon) ([#3163](https://github.com/paperless-ngx/paperless-ngx/pull/3163))
-   Fix: StoragePath missing the owned or granted filter [@stumpylog](https://github.com/stumpylog) ([#3180](https://github.com/paperless-ngx/paperless-ngx/pull/3180))
-   Fix: Redis socket connections fail due to redis-py [@stumpylog](https://github.com/stumpylog) ([#3176](https://github.com/paperless-ngx/paperless-ngx/pull/3176))
-   Fix: Handle delete mail action with no filters [@shamoon](https://github.com/shamoon) ([#3161](https://github.com/paperless-ngx/paperless-ngx/pull/3161))
-   Fix typos and wrong version number in doc [@FizzyMUC](https://github.com/FizzyMUC) ([#3171](https://github.com/paperless-ngx/paperless-ngx/pull/3171))

### Documentation

-   Documentation: add note for macOS [@shamoon](https://github.com/shamoon) ([#3190](https://github.com/paperless-ngx/paperless-ngx/pull/3190))
-   Fix typos and wrong version number in doc [@FizzyMUC](https://github.com/FizzyMUC) ([#3171](https://github.com/paperless-ngx/paperless-ngx/pull/3171))

### Maintenance

-   Chore: Fix isort not running, upgrade to the latest black [@stumpylog](https://github.com/stumpylog) ([#3177](https://github.com/paperless-ngx/paperless-ngx/pull/3177))

### All App Changes

<details>
<summary>11 changes</summary>

-   Fix: reduce frequency of permissions queries to speed up v1.14.0 [@shamoon](https://github.com/shamoon) ([#3201](https://github.com/paperless-ngx/paperless-ngx/pull/3201))
-   Fix: permissions-aware statistics [@shamoon](https://github.com/shamoon) ([#3199](https://github.com/paperless-ngx/paperless-ngx/pull/3199))
-   Fix: Use document owner for matching if set [@shamoon](https://github.com/shamoon) ([#3198](https://github.com/paperless-ngx/paperless-ngx/pull/3198))
-   Chore: Fix isort not running, upgrade to the latest black [@stumpylog](https://github.com/stumpylog) ([#3177](https://github.com/paperless-ngx/paperless-ngx/pull/3177))
-   Fix: respect permissions on document view actions [@shamoon](https://github.com/shamoon) ([#3174](https://github.com/paperless-ngx/paperless-ngx/pull/3174))
-   Increment API version for 1.14.1+ [@shamoon](https://github.com/shamoon) ([#3191](https://github.com/paperless-ngx/paperless-ngx/pull/3191))
-   Fix: dropdown Private items with empty set [@shamoon](https://github.com/shamoon) ([#3189](https://github.com/paperless-ngx/paperless-ngx/pull/3189))
-   Fix: make the importer a little more robust against some errors [@stumpylog](https://github.com/stumpylog) ([#3188](https://github.com/paperless-ngx/paperless-ngx/pull/3188))
-   Fix: Specify backend for auto-login [@shamoon](https://github.com/shamoon) ([#3163](https://github.com/paperless-ngx/paperless-ngx/pull/3163))
-   Fix: StoragePath missing the owned or granted filter [@stumpylog](https://github.com/stumpylog) ([#3180](https://github.com/paperless-ngx/paperless-ngx/pull/3180))
-   Fix: Handle delete mail action with no filters [@shamoon](https://github.com/shamoon) ([#3161](https://github.com/paperless-ngx/paperless-ngx/pull/3161))
</details>

## paperless-ngx 1.14.0

### Notable Changes

-   Feature: multi-user permissions [@shamoon](https://github.com/shamoon) ([#2147](https://github.com/paperless-ngx/paperless-ngx/pull/2147))

### Features

-   Feature: Stronger typing for file consumption [@stumpylog](https://github.com/stumpylog) ([#2744](https://github.com/paperless-ngx/paperless-ngx/pull/2744))
-   Feature: double-click docs [@shamoon](https://github.com/shamoon) ([#2966](https://github.com/paperless-ngx/paperless-ngx/pull/2966))
-   feature: Add support for zxing as barcode scanning lib [@margau](https://github.com/margau) ([#2907](https://github.com/paperless-ngx/paperless-ngx/pull/2907))
-   Feature: Enable images to be released on Quay.io [@stumpylog](https://github.com/stumpylog) ([#2972](https://github.com/paperless-ngx/paperless-ngx/pull/2972))
-   Feature: test mail account [@shamoon](https://github.com/shamoon) ([#2949](https://github.com/paperless-ngx/paperless-ngx/pull/2949))
-   Feature: Capture celery and kombu logs to a file [@stumpylog](https://github.com/stumpylog) ([#2954](https://github.com/paperless-ngx/paperless-ngx/pull/2954))
-   Fix: Resolve Redis connection issues with ACLs [@stumpylog](https://github.com/stumpylog) ([#2939](https://github.com/paperless-ngx/paperless-ngx/pull/2939))
-   Feature: Allow mail account to use access tokens [@stumpylog](https://github.com/stumpylog) ([#2930](https://github.com/paperless-ngx/paperless-ngx/pull/2930))
-   Fix: Consumer polling could overwhelm database [@stumpylog](https://github.com/stumpylog) ([#2922](https://github.com/paperless-ngx/paperless-ngx/pull/2922))
-   Feature: Improved statistics widget [@shamoon](https://github.com/shamoon) ([#2910](https://github.com/paperless-ngx/paperless-ngx/pull/2910))
-   Enhancement: rename comments to notes and improve notes UI [@shamoon](https://github.com/shamoon) ([#2904](https://github.com/paperless-ngx/paperless-ngx/pull/2904))
-   Allow psql client certificate authentication [@Ongy](https://github.com/Ongy) ([#2899](https://github.com/paperless-ngx/paperless-ngx/pull/2899))
-   Enhancement: support filtering multiple correspondents, doctypes \& storage paths [@shamoon](https://github.com/shamoon) ([#2893](https://github.com/paperless-ngx/paperless-ngx/pull/2893))
-   Feature: Change celery serializer to pickle [@stumpylog](https://github.com/stumpylog) ([#2861](https://github.com/paperless-ngx/paperless-ngx/pull/2861))
-   Feature: Allow naming to include owner and original name [@stumpylog](https://github.com/stumpylog) ([#2873](https://github.com/paperless-ngx/paperless-ngx/pull/2873))
-   Feature: Allows filtering email by the TO value(s) as well [@stumpylog](https://github.com/stumpylog) ([#2871](https://github.com/paperless-ngx/paperless-ngx/pull/2871))
-   Feature: owner-aware unique model name constraint [@shamoon](https://github.com/shamoon) ([#2827](https://github.com/paperless-ngx/paperless-ngx/pull/2827))
-   Feature/2396 better mail actions [@jonaswinkler](https://github.com/jonaswinkler) ([#2718](https://github.com/paperless-ngx/paperless-ngx/pull/2718))
-   Feature: Reduce classifier memory usage somewhat during training [@stumpylog](https://github.com/stumpylog) ([#2733](https://github.com/paperless-ngx/paperless-ngx/pull/2733))
-   Feature: Add PAPERLESS_OCR_SKIP_ARCHIVE_FILE config setting [@bdr99](https://github.com/bdr99) ([#2743](https://github.com/paperless-ngx/paperless-ngx/pull/2743))
-   Feature: dynamic document counts in dropdowns [@shamoon](https://github.com/shamoon) ([#2704](https://github.com/paperless-ngx/paperless-ngx/pull/2704))
-   Allow setting the ASN on document upload [@stumpylog](https://github.com/stumpylog) ([#2713](https://github.com/paperless-ngx/paperless-ngx/pull/2713))
-   Feature: Log failed login attempts [@shamoon](https://github.com/shamoon) ([#2359](https://github.com/paperless-ngx/paperless-ngx/pull/2359))
-   Feature: Rename documents when storage path format changes [@stumpylog](https://github.com/stumpylog) ([#2696](https://github.com/paperless-ngx/paperless-ngx/pull/2696))
-   Feature: update error message colors \& show on document failures [@shamoon](https://github.com/shamoon) ([#2689](https://github.com/paperless-ngx/paperless-ngx/pull/2689))
-   Feature: multi-user permissions [@shamoon](https://github.com/shamoon) ([#2147](https://github.com/paperless-ngx/paperless-ngx/pull/2147))

### Bug Fixes

-   Fix: Allow setting additional Django settings for proxies [@stumpylog](https://github.com/stumpylog) ([#3135](https://github.com/paperless-ngx/paperless-ngx/pull/3135))
-   Fix: Use exclude instead of difference for mariadb [@shamoon](https://github.com/shamoon) ([#2983](https://github.com/paperless-ngx/paperless-ngx/pull/2983))
-   Fix: permissions display should not show users with inherited permissions \& unable to change owner [@shamoon](https://github.com/shamoon) ([#2818](https://github.com/paperless-ngx/paperless-ngx/pull/2818))
-   Fix: Resolve Redis connection issues with ACLs [@stumpylog](https://github.com/stumpylog) ([#2939](https://github.com/paperless-ngx/paperless-ngx/pull/2939))
-   Fix: unable to edit correspondents (in ) [@shamoon](https://github.com/shamoon) ([#2938](https://github.com/paperless-ngx/paperless-ngx/pull/2938))
-   Fix: Consumer polling could overwhelm database [@stumpylog](https://github.com/stumpylog) ([#2922](https://github.com/paperless-ngx/paperless-ngx/pull/2922))
-   Fix: Chrome struggles with commas [@stumpylog](https://github.com/stumpylog) ([#2892](https://github.com/paperless-ngx/paperless-ngx/pull/2892))
-   Fix formatting in Setup documentation page [@igrybkov](https://github.com/igrybkov) ([#2880](https://github.com/paperless-ngx/paperless-ngx/pull/2880))
-   Fix: logout on change password via frontend [@shamoon](https://github.com/shamoon) ([#2863](https://github.com/paperless-ngx/paperless-ngx/pull/2863))
-   Fix: give superuser full doc perms [@shamoon](https://github.com/shamoon) ([#2820](https://github.com/paperless-ngx/paperless-ngx/pull/2820))
-   Fix: Append Gmail labels instead of replacing [@stumpylog](https://github.com/stumpylog) ([#2860](https://github.com/paperless-ngx/paperless-ngx/pull/2860))
-   Fix: Ensure email date is made aware during action processing [@stumpylog](https://github.com/stumpylog) ([#2837](https://github.com/paperless-ngx/paperless-ngx/pull/2837))
-   Fix: disable bulk edit dialog buttons during operation [@shamoon](https://github.com/shamoon) ([#2819](https://github.com/paperless-ngx/paperless-ngx/pull/2819))
-   fix database locked error [@jonaswinkler](https://github.com/jonaswinkler) ([#2808](https://github.com/paperless-ngx/paperless-ngx/pull/2808))
-   Fix: Disable suggestions for read-only docs [@shamoon](https://github.com/shamoon) ([#2813](https://github.com/paperless-ngx/paperless-ngx/pull/2813))
-   Update processed mail migration [@shamoon](https://github.com/shamoon) ([#2804](https://github.com/paperless-ngx/paperless-ngx/pull/2804))
-   Fix: Ensure scratch directory exists before using [@stumpylog](https://github.com/stumpylog) ([#2775](https://github.com/paperless-ngx/paperless-ngx/pull/2775))
-   Don't submit owner via API on document upload [@jonaswinkler](https://github.com/jonaswinkler) ([#2777](https://github.com/paperless-ngx/paperless-ngx/pull/2777))
-   Fix: only offer log files that exist [@shamoon](https://github.com/shamoon) ([#2739](https://github.com/paperless-ngx/paperless-ngx/pull/2739))
-   Fix: permissions editing and initial view issues [@shamoon](https://github.com/shamoon) ([#2717](https://github.com/paperless-ngx/paperless-ngx/pull/2717))
-   Fix: reset saved view ID on quickFilter [@shamoon](https://github.com/shamoon) ([#2703](https://github.com/paperless-ngx/paperless-ngx/pull/2703))
-   Fix: bulk edit reset apply button state [@shamoon](https://github.com/shamoon) ([#2701](https://github.com/paperless-ngx/paperless-ngx/pull/2701))
-   Fix: add missing i18n for mobile preview tab title [@nathanaelhoun](https://github.com/nathanaelhoun) ([#2692](https://github.com/paperless-ngx/paperless-ngx/pull/2692))

### Documentation

-   Whitespace changes, making sure the example is correctly aligned [@denilsonsa](https://github.com/denilsonsa) ([#3089](https://github.com/paperless-ngx/paperless-ngx/pull/3089))
-   Docs: Include additional information about barcodes [@stumpylog](https://github.com/stumpylog) ([#2889](https://github.com/paperless-ngx/paperless-ngx/pull/2889))
-   Fix formatting in Setup documentation page [@igrybkov](https://github.com/igrybkov) ([#2880](https://github.com/paperless-ngx/paperless-ngx/pull/2880))
-   [Documentation] Update docker-compose steps to support podman [@white-gecko](https://github.com/white-gecko) ([#2855](https://github.com/paperless-ngx/paperless-ngx/pull/2855))
-   docs: better language code help [@tooomm](https://github.com/tooomm) ([#2830](https://github.com/paperless-ngx/paperless-ngx/pull/2830))
-   Feature: Add an option to disable matching [@bdr99](https://github.com/bdr99) ([#2727](https://github.com/paperless-ngx/paperless-ngx/pull/2727))
-   Docs: Remove outdated PAPERLESS_WORKER_RETRY [@shamoon](https://github.com/shamoon) ([#2694](https://github.com/paperless-ngx/paperless-ngx/pull/2694))
-   Fix: add missing i18n for mobile preview tab title [@nathanaelhoun](https://github.com/nathanaelhoun) ([#2692](https://github.com/paperless-ngx/paperless-ngx/pull/2692))

### Maintenance

-   Chore: Configure ruff as the primary linter for Python [@stumpylog](https://github.com/stumpylog) ([#2988](https://github.com/paperless-ngx/paperless-ngx/pull/2988))
-   Feature: Enable images to be released on Quay.io [@stumpylog](https://github.com/stumpylog) ([#2972](https://github.com/paperless-ngx/paperless-ngx/pull/2972))
-   Chore: Updates locked pipenv to latest version [@stumpylog](https://github.com/stumpylog) ([#2943](https://github.com/paperless-ngx/paperless-ngx/pull/2943))
-   Chore: Properly collapse section in releases [@tooomm](https://github.com/tooomm) ([#2838](https://github.com/paperless-ngx/paperless-ngx/pull/2838))
-   Chore: Don't include changelog PR for different releases [@tooomm](https://github.com/tooomm) ([#2832](https://github.com/paperless-ngx/paperless-ngx/pull/2832))
-   Chore: Speed up frontend CI testing [@stumpylog](https://github.com/stumpylog) ([#2796](https://github.com/paperless-ngx/paperless-ngx/pull/2796))
-   Bump leonsteinhaeuser/project-beta-automations from 2.0.1 to 2.1.0 [@dependabot](https://github.com/dependabot) ([#2789](https://github.com/paperless-ngx/paperless-ngx/pull/2789))

### Dependencies

<details>
<summary>15 changes</summary>

-   Bump ng2-pdf-viewer from 9.1.4 to 9.1.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#3109](https://github.com/paperless-ngx/paperless-ngx/pull/3109))
-   Grouped bump angular packages from 15.2.6 to 15.2.7 in /src-ui [@dependabot](https://github.com/dependabot) ([#3108](https://github.com/paperless-ngx/paperless-ngx/pull/3108))
-   Bump typescript from 4.8.4 to 4.9.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#3071](https://github.com/paperless-ngx/paperless-ngx/pull/3071))
-   Bulk Bump npm packages 04.23 [@dependabot](https://github.com/dependabot) ([#3068](https://github.com/paperless-ngx/paperless-ngx/pull/3068))
-   Bump wait-on from 6.0.1 to 7.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#2990](https://github.com/paperless-ngx/paperless-ngx/pull/2990))
-   Bulk bump angular packages to 15.2.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#2991](https://github.com/paperless-ngx/paperless-ngx/pull/2991))
-   Bump [@<!---->types/node from 18.11.18 to 18.15.11 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.11.18 to 18.15.11 in /src-ui @dependabot) ([#2993](https://github.com/paperless-ngx/paperless-ngx/pull/2993))
-   Bump [@<!---->ng-select/ng-select from 10.0.3 to 10.0.4 in /src-ui @dependabot](https://github.com/<!---->ng-select/ng-select from 10.0.3 to 10.0.4 in /src-ui @dependabot) ([#2992](https://github.com/paperless-ngx/paperless-ngx/pull/2992))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.50.0 to 5.57.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.50.0 to 5.57.0 in /src-ui @dependabot) ([#2989](https://github.com/paperless-ngx/paperless-ngx/pull/2989))
-   Chore: Update cryptography to latest version [@stumpylog](https://github.com/stumpylog) ([#2891](https://github.com/paperless-ngx/paperless-ngx/pull/2891))
-   Chore: Update to qpdf 11.3.0 in Docker image [@stumpylog](https://github.com/stumpylog) ([#2862](https://github.com/paperless-ngx/paperless-ngx/pull/2862))
-   Bump leonsteinhaeuser/project-beta-automations from 2.0.1 to 2.1.0 [@dependabot](https://github.com/dependabot) ([#2789](https://github.com/paperless-ngx/paperless-ngx/pull/2789))
-   Bump zone.js from 0.11.8 to 0.12.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#2793](https://github.com/paperless-ngx/paperless-ngx/pull/2793))
-   Bump [@<!---->typescript-eslint/parser from 5.50.0 to 5.54.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.50.0 to 5.54.0 in /src-ui @dependabot) ([#2792](https://github.com/paperless-ngx/paperless-ngx/pull/2792))
-   Bulk Bump angular packages to 15.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#2788](https://github.com/paperless-ngx/paperless-ngx/pull/2788))
</details>

### All App Changes

<details>
<summary>72 changes</summary>

-   Feature: Catalan translation [@shamoon](https://github.com/shamoon) ([#3146](https://github.com/paperless-ngx/paperless-ngx/pull/3146))
-   Fix: Allow setting additional Django settings for proxies [@stumpylog](https://github.com/stumpylog) ([#3135](https://github.com/paperless-ngx/paperless-ngx/pull/3135))
-   Fix: Increase mail account password field length [@stumpylog](https://github.com/stumpylog) ([#3134](https://github.com/paperless-ngx/paperless-ngx/pull/3134))
-   Fix: respect permissions for matching suggestions [@shamoon](https://github.com/shamoon) ([#3103](https://github.com/paperless-ngx/paperless-ngx/pull/3103))
-   Bump ng2-pdf-viewer from 9.1.4 to 9.1.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#3109](https://github.com/paperless-ngx/paperless-ngx/pull/3109))
-   Grouped bump angular packages from 15.2.6 to 15.2.7 in /src-ui [@dependabot](https://github.com/dependabot) ([#3108](https://github.com/paperless-ngx/paperless-ngx/pull/3108))
-   Fix: update PaperlessTask on hard failures [@shamoon](https://github.com/shamoon) ([#3062](https://github.com/paperless-ngx/paperless-ngx/pull/3062))
-   Bump typescript from 4.8.4 to 4.9.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#3071](https://github.com/paperless-ngx/paperless-ngx/pull/3071))
-   Bulk Bump npm packages 04.23 [@dependabot](https://github.com/dependabot) ([#3068](https://github.com/paperless-ngx/paperless-ngx/pull/3068))
-   Fix: Hide UI tour steps if user doesn't have permissions [@shamoon](https://github.com/shamoon) ([#3060](https://github.com/paperless-ngx/paperless-ngx/pull/3060))
-   Fix: Hide Permissions tab if user cannot view users [@shamoon](https://github.com/shamoon) ([#3061](https://github.com/paperless-ngx/paperless-ngx/pull/3061))
-   v1.14.0 delete document fixes [@shamoon](https://github.com/shamoon) ([#3020](https://github.com/paperless-ngx/paperless-ngx/pull/3020))
-   Bump wait-on from 6.0.1 to 7.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#2990](https://github.com/paperless-ngx/paperless-ngx/pull/2990))
-   Fix: inline plaintext docs to enforce styling [@shamoon](https://github.com/shamoon) ([#3013](https://github.com/paperless-ngx/paperless-ngx/pull/3013))
-   Chore: Configure ruff as the primary linter for Python [@stumpylog](https://github.com/stumpylog) ([#2988](https://github.com/paperless-ngx/paperless-ngx/pull/2988))
-   Bulk bump angular packages to 15.2.5 in /src-ui [@dependabot](https://github.com/dependabot) ([#2991](https://github.com/paperless-ngx/paperless-ngx/pull/2991))
-   Bump [@<!---->types/node from 18.11.18 to 18.15.11 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.11.18 to 18.15.11 in /src-ui @dependabot) ([#2993](https://github.com/paperless-ngx/paperless-ngx/pull/2993))
-   Bump [@<!---->ng-select/ng-select from 10.0.3 to 10.0.4 in /src-ui @dependabot](https://github.com/<!---->ng-select/ng-select from 10.0.3 to 10.0.4 in /src-ui @dependabot) ([#2992](https://github.com/paperless-ngx/paperless-ngx/pull/2992))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.50.0 to 5.57.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.50.0 to 5.57.0 in /src-ui @dependabot) ([#2989](https://github.com/paperless-ngx/paperless-ngx/pull/2989))
-   Feature: Stronger typing for file consumption [@stumpylog](https://github.com/stumpylog) ([#2744](https://github.com/paperless-ngx/paperless-ngx/pull/2744))
-   Fix: Use exclude instead of difference for mariadb [@shamoon](https://github.com/shamoon) ([#2983](https://github.com/paperless-ngx/paperless-ngx/pull/2983))
-   Fix: permissions display should not show users with inherited permissions \& unable to change owner [@shamoon](https://github.com/shamoon) ([#2818](https://github.com/paperless-ngx/paperless-ngx/pull/2818))
-   Feature: double-click docs [@shamoon](https://github.com/shamoon) ([#2966](https://github.com/paperless-ngx/paperless-ngx/pull/2966))
-   feature: Add support for zxing as barcode scanning lib [@margau](https://github.com/margau) ([#2907](https://github.com/paperless-ngx/paperless-ngx/pull/2907))
-   Feature: test mail account [@shamoon](https://github.com/shamoon) ([#2949](https://github.com/paperless-ngx/paperless-ngx/pull/2949))
-   Feature: Capture celery and kombu logs to a file [@stumpylog](https://github.com/stumpylog) ([#2954](https://github.com/paperless-ngx/paperless-ngx/pull/2954))
-   Fix: Resolve Redis connection issues with ACLs [@stumpylog](https://github.com/stumpylog) ([#2939](https://github.com/paperless-ngx/paperless-ngx/pull/2939))
-   Feature: Allow mail account to use access tokens [@stumpylog](https://github.com/stumpylog) ([#2930](https://github.com/paperless-ngx/paperless-ngx/pull/2930))
-   Fix: Consumer polling could overwhelm database [@stumpylog](https://github.com/stumpylog) ([#2922](https://github.com/paperless-ngx/paperless-ngx/pull/2922))
-   Feature: Improved statistics widget [@shamoon](https://github.com/shamoon) ([#2910](https://github.com/paperless-ngx/paperless-ngx/pull/2910))
-   Enhancement: rename comments to notes and improve notes UI [@shamoon](https://github.com/shamoon) ([#2904](https://github.com/paperless-ngx/paperless-ngx/pull/2904))
-   Allow psql client certificate authentication [@Ongy](https://github.com/Ongy) ([#2899](https://github.com/paperless-ngx/paperless-ngx/pull/2899))
-   Enhancement: support filtering multiple correspondents, doctypes \& storage paths [@shamoon](https://github.com/shamoon) ([#2893](https://github.com/paperless-ngx/paperless-ngx/pull/2893))
-   Fix: frontend handle private tags, doctypes, correspondents [@shamoon](https://github.com/shamoon) ([#2839](https://github.com/paperless-ngx/paperless-ngx/pull/2839))
-   Fix: Chrome struggles with commas [@stumpylog](https://github.com/stumpylog) ([#2892](https://github.com/paperless-ngx/paperless-ngx/pull/2892))
-   Feature: Change celery serializer to pickle [@stumpylog](https://github.com/stumpylog) ([#2861](https://github.com/paperless-ngx/paperless-ngx/pull/2861))
-   Feature: Allow naming to include owner and original name [@stumpylog](https://github.com/stumpylog) ([#2873](https://github.com/paperless-ngx/paperless-ngx/pull/2873))
-   Feature: Allows filtering email by the TO value(s) as well [@stumpylog](https://github.com/stumpylog) ([#2871](https://github.com/paperless-ngx/paperless-ngx/pull/2871))
-   Fix: logout on change password via frontend [@shamoon](https://github.com/shamoon) ([#2863](https://github.com/paperless-ngx/paperless-ngx/pull/2863))
-   Fix: give superuser full doc perms [@shamoon](https://github.com/shamoon) ([#2820](https://github.com/paperless-ngx/paperless-ngx/pull/2820))
-   Fix: Append Gmail labels instead of replacing [@stumpylog](https://github.com/stumpylog) ([#2860](https://github.com/paperless-ngx/paperless-ngx/pull/2860))
-   Feature: owner-aware unique model name constraint [@shamoon](https://github.com/shamoon) ([#2827](https://github.com/paperless-ngx/paperless-ngx/pull/2827))
-   Chore: Create list parsing utility for settings [@stumpylog](https://github.com/stumpylog) ([#2816](https://github.com/paperless-ngx/paperless-ngx/pull/2816))
-   Fix: Ensure email date is made aware during action processing [@stumpylog](https://github.com/stumpylog) ([#2837](https://github.com/paperless-ngx/paperless-ngx/pull/2837))
-   Chore: Convert more code to pathlib [@stumpylog](https://github.com/stumpylog) ([#2817](https://github.com/paperless-ngx/paperless-ngx/pull/2817))
-   Fix: disable bulk edit dialog buttons during operation [@shamoon](https://github.com/shamoon) ([#2819](https://github.com/paperless-ngx/paperless-ngx/pull/2819))
-   fix database locked error [@jonaswinkler](https://github.com/jonaswinkler) ([#2808](https://github.com/paperless-ngx/paperless-ngx/pull/2808))
-   Fix: Disable suggestions for read-only docs [@shamoon](https://github.com/shamoon) ([#2813](https://github.com/paperless-ngx/paperless-ngx/pull/2813))
-   update django.po messages [@jonaswinkler](https://github.com/jonaswinkler) ([#2806](https://github.com/paperless-ngx/paperless-ngx/pull/2806))
-   Update processed mail migration [@shamoon](https://github.com/shamoon) ([#2804](https://github.com/paperless-ngx/paperless-ngx/pull/2804))
-   Feature/2396 better mail actions [@jonaswinkler](https://github.com/jonaswinkler) ([#2718](https://github.com/paperless-ngx/paperless-ngx/pull/2718))
-   Bump zone.js from 0.11.8 to 0.12.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#2793](https://github.com/paperless-ngx/paperless-ngx/pull/2793))
-   Bump [@<!---->typescript-eslint/parser from 5.50.0 to 5.54.0 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.50.0 to 5.54.0 in /src-ui @dependabot) ([#2792](https://github.com/paperless-ngx/paperless-ngx/pull/2792))
-   Bulk Bump angular packages to 15.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#2788](https://github.com/paperless-ngx/paperless-ngx/pull/2788))
-   Fix: Ensure scratch directory exists before using [@stumpylog](https://github.com/stumpylog) ([#2775](https://github.com/paperless-ngx/paperless-ngx/pull/2775))
-   Don't submit owner via API on document upload [@jonaswinkler](https://github.com/jonaswinkler) ([#2777](https://github.com/paperless-ngx/paperless-ngx/pull/2777))
-   Feature: Reduce classifier memory usage somewhat during training [@stumpylog](https://github.com/stumpylog) ([#2733](https://github.com/paperless-ngx/paperless-ngx/pull/2733))
-   Chore: Setup for mypy typing checks [@stumpylog](https://github.com/stumpylog) ([#2742](https://github.com/paperless-ngx/paperless-ngx/pull/2742))
-   Feature: Add PAPERLESS_OCR_SKIP_ARCHIVE_FILE config setting [@bdr99](https://github.com/bdr99) ([#2743](https://github.com/paperless-ngx/paperless-ngx/pull/2743))
-   Fix: only offer log files that exist [@shamoon](https://github.com/shamoon) ([#2739](https://github.com/paperless-ngx/paperless-ngx/pull/2739))
-   Feature: dynamic document counts in dropdowns [@shamoon](https://github.com/shamoon) ([#2704](https://github.com/paperless-ngx/paperless-ngx/pull/2704))
-   Fix: permissions editing and initial view issues [@shamoon](https://github.com/shamoon) ([#2717](https://github.com/paperless-ngx/paperless-ngx/pull/2717))
-   Fix: reset saved view ID on quickFilter [@shamoon](https://github.com/shamoon) ([#2703](https://github.com/paperless-ngx/paperless-ngx/pull/2703))
-   Feature: Add an option to disable matching [@bdr99](https://github.com/bdr99) ([#2727](https://github.com/paperless-ngx/paperless-ngx/pull/2727))
-   Chore: Improve clarity of some test asserting [@stumpylog](https://github.com/stumpylog) ([#2714](https://github.com/paperless-ngx/paperless-ngx/pull/2714))
-   Allow setting the ASN on document upload [@stumpylog](https://github.com/stumpylog) ([#2713](https://github.com/paperless-ngx/paperless-ngx/pull/2713))
-   Fix: bulk edit reset apply button state [@shamoon](https://github.com/shamoon) ([#2701](https://github.com/paperless-ngx/paperless-ngx/pull/2701))
-   Feature: Log failed login attempts [@shamoon](https://github.com/shamoon) ([#2359](https://github.com/paperless-ngx/paperless-ngx/pull/2359))
-   Feature: Rename documents when storage path format changes [@stumpylog](https://github.com/stumpylog) ([#2696](https://github.com/paperless-ngx/paperless-ngx/pull/2696))
-   Feature: update error message colors \& show on document failures [@shamoon](https://github.com/shamoon) ([#2689](https://github.com/paperless-ngx/paperless-ngx/pull/2689))
-   Feature: multi-user permissions [@shamoon](https://github.com/shamoon) ([#2147](https://github.com/paperless-ngx/paperless-ngx/pull/2147))
-   Fix: add missing i18n for mobile preview tab title [@nathanaelhoun](https://github.com/nathanaelhoun) ([#2692](https://github.com/paperless-ngx/paperless-ngx/pull/2692))
</details>

## paperless-ngx 1.13.0

### Features

-   Feature: allow disable warn on close saved view with changes [@shamoon](https://github.com/shamoon) ([#2681](https://github.com/paperless-ngx/paperless-ngx/pull/2681))
-   Feature: Add option to enable response compression [@stumpylog](https://github.com/stumpylog) ([#2621](https://github.com/paperless-ngx/paperless-ngx/pull/2621))
-   Feature: split documents on ASN barcode [@muued](https://github.com/muued) ([#2554](https://github.com/paperless-ngx/paperless-ngx/pull/2554))

### Bug Fixes

-   Fix: Ignore path filtering didn't handle sub directories [@stumpylog](https://github.com/stumpylog) ([#2674](https://github.com/paperless-ngx/paperless-ngx/pull/2674))
-   Bugfix: Generation of secret key hangs during install script [@stumpylog](https://github.com/stumpylog) ([#2657](https://github.com/paperless-ngx/paperless-ngx/pull/2657))
-   Fix: Remove files produced by barcode splitting when completed [@stumpylog](https://github.com/stumpylog) ([#2648](https://github.com/paperless-ngx/paperless-ngx/pull/2648))
-   Fix: add missing storage path placeholders [@shamoon](https://github.com/shamoon) ([#2651](https://github.com/paperless-ngx/paperless-ngx/pull/2651))
-   Fix long dropdown contents break document detail column view [@shamoon](https://github.com/shamoon) ([#2638](https://github.com/paperless-ngx/paperless-ngx/pull/2638))
-   Fix: tags dropdown should stay closed when removing [@shamoon](https://github.com/shamoon) ([#2625](https://github.com/paperless-ngx/paperless-ngx/pull/2625))
-   Bugfix: Configure scheduled tasks to expire after some time [@stumpylog](https://github.com/stumpylog) ([#2614](https://github.com/paperless-ngx/paperless-ngx/pull/2614))
-   Bugfix: Limit management list pagination maxSize to 5 [@Kaaybi](https://github.com/Kaaybi) ([#2618](https://github.com/paperless-ngx/paperless-ngx/pull/2618))
-   Fix: Don't crash on bad ASNs during indexing [@stumpylog](https://github.com/stumpylog) ([#2586](https://github.com/paperless-ngx/paperless-ngx/pull/2586))
-   Fix: Prevent mktime OverflowError except in even more rare caes [@stumpylog](https://github.com/stumpylog) ([#2574](https://github.com/paperless-ngx/paperless-ngx/pull/2574))
-   Bugfix: Whoosh relative date queries weren't handling timezones [@stumpylog](https://github.com/stumpylog) ([#2566](https://github.com/paperless-ngx/paperless-ngx/pull/2566))
-   Fix importing files with non-ascii names [@Kexogg](https://github.com/Kexogg) ([#2555](https://github.com/paperless-ngx/paperless-ngx/pull/2555))

### Documentation

-   Chore: update recommended Gotenberg to 7.8, docs note possible incompatibility [@shamoon](https://github.com/shamoon) ([#2608](https://github.com/paperless-ngx/paperless-ngx/pull/2608))
-   [Documentation] Add v1.12.2 changelog [@github-actions](https://github.com/github-actions) ([#2553](https://github.com/paperless-ngx/paperless-ngx/pull/2553))

### Maintenance

-   Chore: Faster Docker image cleanup [@stumpylog](https://github.com/stumpylog) ([#2687](https://github.com/paperless-ngx/paperless-ngx/pull/2687))
-   Chore: Remove duplicated folder [@stumpylog](https://github.com/stumpylog) ([#2561](https://github.com/paperless-ngx/paperless-ngx/pull/2561))
-   Chore: Switch test coverage to Codecov [@stumpylog](https://github.com/stumpylog) ([#2582](https://github.com/paperless-ngx/paperless-ngx/pull/2582))
-   Bump docker/build-push-action from 3 to 4 [@dependabot](https://github.com/dependabot) ([#2576](https://github.com/paperless-ngx/paperless-ngx/pull/2576))
-   Chore: Run tests which require convert in the CI [@stumpylog](https://github.com/stumpylog) ([#2570](https://github.com/paperless-ngx/paperless-ngx/pull/2570))

-   Feature: split documents on ASN barcode [@muued](https://github.com/muued) ([#2554](https://github.com/paperless-ngx/paperless-ngx/pull/2554))
-   Bugfix: Whoosh relative date queries weren't handling timezones [@stumpylog](https://github.com/stumpylog) ([#2566](https://github.com/paperless-ngx/paperless-ngx/pull/2566))
-   Fix importing files with non-ascii names [@Kexogg](https://github.com/Kexogg) ([#2555](https://github.com/paperless-ngx/paperless-ngx/pull/2555))

## paperless-ngx 1.12.2

_Note: Version 1.12.x introduced searching of comments which will work for comments added after the upgrade but a reindex of the search index is required in order to be able to search
older comments. The Docker image will automatically perform this reindex, bare metal installations will have to perform this manually, see [the docs](https://docs.paperless-ngx.com/administration/#index)._

### Bug Fixes

-   Bugfix: Allow pre-consume scripts to modify incoming file [@stumpylog](https://github.com/stumpylog) ([#2547](https://github.com/paperless-ngx/paperless-ngx/pull/2547))
-   Bugfix: Return to page based barcode scanning [@stumpylog](https://github.com/stumpylog) ([#2544](https://github.com/paperless-ngx/paperless-ngx/pull/2544))
-   Fix: Try to prevent title debounce overwriting [@shamoon](https://github.com/shamoon) ([#2543](https://github.com/paperless-ngx/paperless-ngx/pull/2543))
-   Fix comment search highlight + multi-word search [@shamoon](https://github.com/shamoon) ([#2542](https://github.com/paperless-ngx/paperless-ngx/pull/2542))
-   Bugfix: Request PDF/A format from Gotenberg [@stumpylog](https://github.com/stumpylog) ([#2530](https://github.com/paperless-ngx/paperless-ngx/pull/2530))
-   Fix: Trigger reindex for pre-existing comments [@shamoon](https://github.com/shamoon) ([#2519](https://github.com/paperless-ngx/paperless-ngx/pull/2519))

### Documentation

-   Bugfix: Allow pre-consume scripts to modify incoming file [@stumpylog](https://github.com/stumpylog) ([#2547](https://github.com/paperless-ngx/paperless-ngx/pull/2547))
-   Fix: Trigger reindex for pre-existing comments [@shamoon](https://github.com/shamoon) ([#2519](https://github.com/paperless-ngx/paperless-ngx/pull/2519))
-   Minor updates to development documentation [@clemensrieder](https://github.com/clemensrieder) ([#2474](https://github.com/paperless-ngx/paperless-ngx/pull/2474))
-   [Documentation] Add v1.12.1 changelog [@github-actions](https://github.com/github-actions) ([#2515](https://github.com/paperless-ngx/paperless-ngx/pull/2515))

### Maintenance

-   Chore: Fix tag cleaner to work with attestations [@stumpylog](https://github.com/stumpylog) ([#2532](https://github.com/paperless-ngx/paperless-ngx/pull/2532))
-   Chore: Make installers statically versioned [@stumpylog](https://github.com/stumpylog) ([#2517](https://github.com/paperless-ngx/paperless-ngx/pull/2517))

### All App Changes

-   Bugfix: Allow pre-consume scripts to modify incoming file [@stumpylog](https://github.com/stumpylog) ([#2547](https://github.com/paperless-ngx/paperless-ngx/pull/2547))
-   Bugfix: Return to page based barcode scanning [@stumpylog](https://github.com/stumpylog) ([#2544](https://github.com/paperless-ngx/paperless-ngx/pull/2544))
-   Fix: Try to prevent title debounce overwriting [@shamoon](https://github.com/shamoon) ([#2543](https://github.com/paperless-ngx/paperless-ngx/pull/2543))
-   Fix comment search highlight + multi-word search [@shamoon](https://github.com/shamoon) ([#2542](https://github.com/paperless-ngx/paperless-ngx/pull/2542))
-   Bugfix: Request PDF/A format from Gotenberg [@stumpylog](https://github.com/stumpylog) ([#2530](https://github.com/paperless-ngx/paperless-ngx/pull/2530))

## paperless-ngx 1.12.1

### Bug Fixes

-   Fix: comments not showing in search until after manual reindex in v1.12 [@shamoon](https://github.com/shamoon) ([#2513](https://github.com/paperless-ngx/paperless-ngx/pull/2513))
-   Fix: date range search broken in 1.12 [@shamoon](https://github.com/shamoon) ([#2509](https://github.com/paperless-ngx/paperless-ngx/pull/2509))

### Documentation

-   [Documentation] Add v1.12.0 changelog [@github-actions](https://github.com/github-actions) ([#2507](https://github.com/paperless-ngx/paperless-ngx/pull/2507))

### Maintenance

-   Moves back to the main release-drafter now that it does what we wanted [@stumpylog](https://github.com/stumpylog) ([#2503](https://github.com/paperless-ngx/paperless-ngx/pull/2503))

### All App Changes

-   Fix: comments not showing in search until after manual reindex in v1.12 [@shamoon](https://github.com/shamoon) ([#2513](https://github.com/paperless-ngx/paperless-ngx/pull/2513))
-   Fix: date range search broken in 1.12 [@shamoon](https://github.com/shamoon) ([#2509](https://github.com/paperless-ngx/paperless-ngx/pull/2509))

## paperless-ngx 1.12.0

### Features

-   New document_exporter options [@mhelleboid](https://github.com/mhelleboid) ([#2448](https://github.com/paperless-ngx/paperless-ngx/pull/2448))
-   Read ASN from barcode on page [@peterkappelt](https://github.com/peterkappelt) ([#2437](https://github.com/paperless-ngx/paperless-ngx/pull/2437))
-   Add AppleMail color tag support [@clemensrieder](https://github.com/clemensrieder) ([#2407](https://github.com/paperless-ngx/paperless-ngx/pull/2407))
-   Feature: Retain original filename on upload [@stumpylog](https://github.com/stumpylog) ([#2404](https://github.com/paperless-ngx/paperless-ngx/pull/2404))
-   Feature: Control scheduled tasks via cron expressions [@stumpylog](https://github.com/stumpylog) ([#2403](https://github.com/paperless-ngx/paperless-ngx/pull/2403))
-   Simplify json parsing in build scripts [@tribut](https://github.com/tribut) ([#2370](https://github.com/paperless-ngx/paperless-ngx/pull/2370))
-   Feature: include comments in advanced search [@shamoon](https://github.com/shamoon) ([#2351](https://github.com/paperless-ngx/paperless-ngx/pull/2351))

### Bug Fixes

-   Fix: limit asn integer size [@shamoon](https://github.com/shamoon) ([#2498](https://github.com/paperless-ngx/paperless-ngx/pull/2498))
-   Bugfix: Rescales images for better barcode locating [@stumpylog](https://github.com/stumpylog) ([#2468](https://github.com/paperless-ngx/paperless-ngx/pull/2468))
-   Fix: fix downgrade migration [@shamoon](https://github.com/shamoon) ([#2494](https://github.com/paperless-ngx/paperless-ngx/pull/2494))
-   Fix: Allow setting mailrule order from frontend [@shamoon](https://github.com/shamoon) ([#2459](https://github.com/paperless-ngx/paperless-ngx/pull/2459))
-   Fix: tag color ordering [@shamoon](https://github.com/shamoon) ([#2456](https://github.com/paperless-ngx/paperless-ngx/pull/2456))
-   Fix: Better Handle arbitrary ISO 8601 strings after celery serializing [@shamoon](https://github.com/shamoon) ([#2441](https://github.com/paperless-ngx/paperless-ngx/pull/2441))
-   Use correct canonical path for nltk_data [@amo13](https://github.com/amo13) ([#2429](https://github.com/paperless-ngx/paperless-ngx/pull/2429))
-   Fix: Include optional socket file in release [@stumpylog](https://github.com/stumpylog) ([#2409](https://github.com/paperless-ngx/paperless-ngx/pull/2409))
-   Fix: display rtl content in correct direction [@shamoon](https://github.com/shamoon) ([#2302](https://github.com/paperless-ngx/paperless-ngx/pull/2302))
-   Fixed endpoint count in Docs The REST API [@PascalSenn](https://github.com/PascalSenn) ([#2386](https://github.com/paperless-ngx/paperless-ngx/pull/2386))
-   Fix subpath for websockets [@tribut](https://github.com/tribut) ([#2371](https://github.com/paperless-ngx/paperless-ngx/pull/2371))
-   Fix: Make missing environment from file files informational only [@stumpylog](https://github.com/stumpylog) ([#2368](https://github.com/paperless-ngx/paperless-ngx/pull/2368))
-   Bugfix: Backend tests weren't using correct Python version [@stumpylog](https://github.com/stumpylog) ([#2363](https://github.com/paperless-ngx/paperless-ngx/pull/2363))
-   Fix: preview content remains hidden on mobile [@shamoon](https://github.com/shamoon) ([#2346](https://github.com/paperless-ngx/paperless-ngx/pull/2346))
-   Bugfix: Removal of alpha channel truncates multipage TIFFs [@stumpylog](https://github.com/stumpylog) ([#2335](https://github.com/paperless-ngx/paperless-ngx/pull/2335))
-   Documentation: update build instructions to remove deprecated [@shamoon](https://github.com/shamoon) ([#2334](https://github.com/paperless-ngx/paperless-ngx/pull/2334))

### Documentation

-   Docs: Fix typo - docker-compose.yml file name in setup doc [@muli](https://github.com/muli) ([#2477](https://github.com/paperless-ngx/paperless-ngx/pull/2477))
-   document existence of document_thumbnails [@frrad](https://github.com/frrad) ([#2470](https://github.com/paperless-ngx/paperless-ngx/pull/2470))
-   Add optional sudo command to bare metal docs [@shamoon](https://github.com/shamoon) ([#2464](https://github.com/paperless-ngx/paperless-ngx/pull/2464))
-   Fix link [@edenhaus](https://github.com/edenhaus) ([#2458](https://github.com/paperless-ngx/paperless-ngx/pull/2458))
-   Documentation: Fix comment re bare metal runserver command [@shamoon](https://github.com/shamoon) ([#2420](https://github.com/paperless-ngx/paperless-ngx/pull/2420))
-   Fix formatting of config variable in docs [@peterkappelt](https://github.com/peterkappelt) ([#2445](https://github.com/paperless-ngx/paperless-ngx/pull/2445))
-   Update docs nginx reverse proxy example [@Sprinterfreak](https://github.com/Sprinterfreak) ([#2443](https://github.com/paperless-ngx/paperless-ngx/pull/2443))
-   [Documentation] Add note re for dev server [@shamoon](https://github.com/shamoon) ([#2387](https://github.com/paperless-ngx/paperless-ngx/pull/2387))
-   Fixed endpoint count in Docs The REST API [@PascalSenn](https://github.com/PascalSenn) ([#2386](https://github.com/paperless-ngx/paperless-ngx/pull/2386))
-   [ Docs] Update bare metal setup instructions [@natrius](https://github.com/natrius) ([#2281](https://github.com/paperless-ngx/paperless-ngx/pull/2281))
-   [Docs] Add Paperless Mobile app to docs [@astubenbord](https://github.com/astubenbord) ([#2378](https://github.com/paperless-ngx/paperless-ngx/pull/2378))
-   Tiny spelling change [@veverkap](https://github.com/veverkap) ([#2369](https://github.com/paperless-ngx/paperless-ngx/pull/2369))
-   Documentation: update build instructions to remove deprecated [@shamoon](https://github.com/shamoon) ([#2334](https://github.com/paperless-ngx/paperless-ngx/pull/2334))
-   [Documentation] Add note that PAPERLESS_URL can't contain a path [@shamoon](https://github.com/shamoon) ([#2319](https://github.com/paperless-ngx/paperless-ngx/pull/2319))
-   [Documentation] Add v1.11.3 changelog [@github-actions](https://github.com/github-actions) ([#2311](https://github.com/paperless-ngx/paperless-ngx/pull/2311))

### Maintenance

-   Fix: Include optional socket file in release [@stumpylog](https://github.com/stumpylog) ([#2409](https://github.com/paperless-ngx/paperless-ngx/pull/2409))
-   Chore: remove helm chart code [@shamoon](https://github.com/shamoon) ([#2388](https://github.com/paperless-ngx/paperless-ngx/pull/2388))
-   Simplify json parsing in build scripts [@tribut](https://github.com/tribut) ([#2370](https://github.com/paperless-ngx/paperless-ngx/pull/2370))
-   Bugfix: Backend tests weren't using correct Python version [@stumpylog](https://github.com/stumpylog) ([#2363](https://github.com/paperless-ngx/paperless-ngx/pull/2363))
-   Bump tj-actions/changed-files from 34 to 35 [@dependabot](https://github.com/dependabot) ([#2303](https://github.com/paperless-ngx/paperless-ngx/pull/2303))

### Dependencies

<details>
<summary>4 changes</summary>

-   Chore: Backend library updates [@stumpylog](https://github.com/stumpylog) ([#2401](https://github.com/paperless-ngx/paperless-ngx/pull/2401))
-   Bump tj-actions/changed-files from 34 to 35 [@dependabot](https://github.com/dependabot) ([#2303](https://github.com/paperless-ngx/paperless-ngx/pull/2303))
-   Bump [@<!---->typescript-eslint/parser from 5.43.0 to 5.47.1 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.43.0 to 5.47.1 in /src-ui @dependabot) ([#2306](https://github.com/paperless-ngx/paperless-ngx/pull/2306))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.43.0 to 5.47.1 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.43.0 to 5.47.1 in /src-ui @dependabot) ([#2308](https://github.com/paperless-ngx/paperless-ngx/pull/2308))
</details>

### All App Changes

-   New document_exporter options [@mhelleboid](https://github.com/mhelleboid) ([#2448](https://github.com/paperless-ngx/paperless-ngx/pull/2448))
-   Fix: limit asn integer size [@shamoon](https://github.com/shamoon) ([#2498](https://github.com/paperless-ngx/paperless-ngx/pull/2498))
-   Fix: fix downgrade migration [@shamoon](https://github.com/shamoon) ([#2494](https://github.com/paperless-ngx/paperless-ngx/pull/2494))
-   Read ASN from barcode on page [@peterkappelt](https://github.com/peterkappelt) ([#2437](https://github.com/paperless-ngx/paperless-ngx/pull/2437))
-   Fix: Allow setting mailrule order from frontend [@shamoon](https://github.com/shamoon) ([#2459](https://github.com/paperless-ngx/paperless-ngx/pull/2459))
-   Chore: Update to Angular 15 \& associated frontend deps [@shamoon](https://github.com/shamoon) ([#2411](https://github.com/paperless-ngx/paperless-ngx/pull/2411))
-   Fix: tag color ordering [@shamoon](https://github.com/shamoon) ([#2456](https://github.com/paperless-ngx/paperless-ngx/pull/2456))
-   Fix: Better Handle arbitrary ISO 8601 strings after celery serializing [@shamoon](https://github.com/shamoon) ([#2441](https://github.com/paperless-ngx/paperless-ngx/pull/2441))
-   Use correct canonical path for nltk_data [@amo13](https://github.com/amo13) ([#2429](https://github.com/paperless-ngx/paperless-ngx/pull/2429))
-   Add AppleMail color tag support [@clemensrieder](https://github.com/clemensrieder) ([#2407](https://github.com/paperless-ngx/paperless-ngx/pull/2407))
-   Chore: Convert document exporter to use pathlib [@stumpylog](https://github.com/stumpylog) ([#2416](https://github.com/paperless-ngx/paperless-ngx/pull/2416))
-   Feature: Retain original filename on upload [@stumpylog](https://github.com/stumpylog) ([#2404](https://github.com/paperless-ngx/paperless-ngx/pull/2404))
-   Feature: Control scheduled tasks via cron expressions [@stumpylog](https://github.com/stumpylog) ([#2403](https://github.com/paperless-ngx/paperless-ngx/pull/2403))
-   Fix: display rtl content in correct direction [@shamoon](https://github.com/shamoon) ([#2302](https://github.com/paperless-ngx/paperless-ngx/pull/2302))
-   Fix subpath for websockets [@tribut](https://github.com/tribut) ([#2371](https://github.com/paperless-ngx/paperless-ngx/pull/2371))
-   Bugfix: Backend tests weren't using correct Python version [@stumpylog](https://github.com/stumpylog) ([#2363](https://github.com/paperless-ngx/paperless-ngx/pull/2363))
-   Feature: include comments in advanced search [@shamoon](https://github.com/shamoon) ([#2351](https://github.com/paperless-ngx/paperless-ngx/pull/2351))
-   Chore: More frontend tests [@shamoon](https://github.com/shamoon) ([#2352](https://github.com/paperless-ngx/paperless-ngx/pull/2352))
-   Chore: Fixing up some minor annoyances [@stumpylog](https://github.com/stumpylog) ([#2348](https://github.com/paperless-ngx/paperless-ngx/pull/2348))
-   Bugfix: Removal of alpha channel truncates multipage TIFFs [@stumpylog](https://github.com/stumpylog) ([#2335](https://github.com/paperless-ngx/paperless-ngx/pull/2335))
-   Documentation: update build instructions to remove deprecated [@shamoon](https://github.com/shamoon) ([#2334](https://github.com/paperless-ngx/paperless-ngx/pull/2334))
-   Add Arabic language to frontend [@KhaledEmad7](https://github.com/KhaledEmad7) ([#2313](https://github.com/paperless-ngx/paperless-ngx/pull/2313))
-   Bump [@<!---->typescript-eslint/parser from 5.43.0 to 5.47.1 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/parser from 5.43.0 to 5.47.1 in /src-ui @dependabot) ([#2306](https://github.com/paperless-ngx/paperless-ngx/pull/2306))
-   Bump [@<!---->typescript-eslint/eslint-plugin from 5.43.0 to 5.47.1 in /src-ui @dependabot](https://github.com/<!---->typescript-eslint/eslint-plugin from 5.43.0 to 5.47.1 in /src-ui @dependabot) ([#2308](https://github.com/paperless-ngx/paperless-ngx/pull/2308))

## paperless-ngx 1.11.3

### Breaking Changes

_Note: PR #2279 could represent a breaking change to the API which may affect third party applications that were only checking the `post_document` endpoint for e.g. result = 'OK' as opposed to e.g. HTTP status = 200_

-   Bugfix: Return created task ID when posting document to API [@stumpylog](https://github.com/stumpylog) ([#2279](https://github.com/paperless-ngx/paperless-ngx/pull/2279))

### Bug Fixes

-   Bugfix: Fix no content when processing some RTL files [@stumpylog](https://github.com/stumpylog) ([#2295](https://github.com/paperless-ngx/paperless-ngx/pull/2295))
-   Bugfix: Handle email dates maybe being naive [@stumpylog](https://github.com/stumpylog) ([#2293](https://github.com/paperless-ngx/paperless-ngx/pull/2293))
-   Fix: live filterable dropdowns broken in 1.11.x [@shamoon](https://github.com/shamoon) ([#2292](https://github.com/paperless-ngx/paperless-ngx/pull/2292))
-   Bugfix: Reading environment from files didn't work for management commands [@stumpylog](https://github.com/stumpylog) ([#2261](https://github.com/paperless-ngx/paperless-ngx/pull/2261))
-   Bugfix: Return created task ID when posting document to API [@stumpylog](https://github.com/stumpylog) ([#2279](https://github.com/paperless-ngx/paperless-ngx/pull/2279))

### All App Changes

-   Bugfix: Fix no content when processing some RTL files [@stumpylog](https://github.com/stumpylog) ([#2295](https://github.com/paperless-ngx/paperless-ngx/pull/2295))
-   Bugfix: Handle email dates maybe being naive [@stumpylog](https://github.com/stumpylog) ([#2293](https://github.com/paperless-ngx/paperless-ngx/pull/2293))
-   Fix: live filterable dropdowns broken in 1.11.x [@shamoon](https://github.com/shamoon) ([#2292](https://github.com/paperless-ngx/paperless-ngx/pull/2292))
-   Bugfix: Return created task ID when posting document to API [@stumpylog](https://github.com/stumpylog) ([#2279](https://github.com/paperless-ngx/paperless-ngx/pull/2279))

## paperless-ngx 1.11.2

Versions 1.11.1 and 1.11.2 contain bug fixes from v1.11.0 that prevented use of the new email consumption feature

### Bug Fixes

-   Fix frontend mailrule missing consumption scope parameter [@shamoon](https://github.com/shamoon) ([#2280](https://github.com/paperless-ngx/paperless-ngx/pull/2280))
-   Fix: missing frontend email attachment options [@shamoon](https://github.com/shamoon) ([#2272](https://github.com/paperless-ngx/paperless-ngx/pull/2272))
-   Fix: edit dialog creation in v1.11.0 [@shamoon](https://github.com/shamoon) ([#2273](https://github.com/paperless-ngx/paperless-ngx/pull/2273))

### All App Changes

-   Fix frontend mailrule missing consumption scope parameter [@shamoon](https://github.com/shamoon) ([#2280](https://github.com/paperless-ngx/paperless-ngx/pull/2280))
-   Fix: missing frontend email attachment options [@shamoon](https://github.com/shamoon) ([#2272](https://github.com/paperless-ngx/paperless-ngx/pull/2272))
-   Fix: edit dialog creation in v1.11.0 [@shamoon](https://github.com/shamoon) ([#2273](https://github.com/paperless-ngx/paperless-ngx/pull/2273))

## paperless-ngx 1.11.0

### Notable Changes

-   Feature: frontend paperless mail [@shamoon](https://github.com/shamoon) ([#2000](https://github.com/paperless-ngx/paperless-ngx/pull/2000))
-   Feature: Ability to consume mails and eml files [@p-h-a-i-l](https://github.com/p-h-a-i-l) ([#848](https://github.com/paperless-ngx/paperless-ngx/pull/848))

### Features

-   Chore: Downgrade hiredis to 2.0.0 [@stumpylog](https://github.com/stumpylog) ([#2262](https://github.com/paperless-ngx/paperless-ngx/pull/2262))
-   Add ability to provide the configuration file path using an env variable [@hashworks](https://github.com/hashworks) ([#2241](https://github.com/paperless-ngx/paperless-ngx/pull/2241))
-   Feature: Adds option to allow a user to export directly to a zipfile [@stumpylog](https://github.com/stumpylog) ([#2004](https://github.com/paperless-ngx/paperless-ngx/pull/2004))
-   Feature: Adds PaperlessTask admin page interface [@stumpylog](https://github.com/stumpylog) ([#2184](https://github.com/paperless-ngx/paperless-ngx/pull/2184))
-   Feature: speed up frontend by truncating content [@shamoon](https://github.com/shamoon) ([#2028](https://github.com/paperless-ngx/paperless-ngx/pull/2028))
-   Feature: Allow bulk download API to follow file name formatting [@stumpylog](https://github.com/stumpylog) ([#2003](https://github.com/paperless-ngx/paperless-ngx/pull/2003))
-   Feature: Bake NLTK into Docker image [@stumpylog](https://github.com/stumpylog) ([#2129](https://github.com/paperless-ngx/paperless-ngx/pull/2129))
-   Feature: frontend paperless mail [@shamoon](https://github.com/shamoon) ([#2000](https://github.com/paperless-ngx/paperless-ngx/pull/2000))
-   Feature: Ability to consume mails and eml files [@p-h-a-i-l](https://github.com/p-h-a-i-l) ([#848](https://github.com/paperless-ngx/paperless-ngx/pull/848))

### Bug Fixes

-   Bugfix: Handle RTL languages better [@stumpylog](https://github.com/stumpylog) ([#1665](https://github.com/paperless-ngx/paperless-ngx/pull/1665))
-   Fixed typo in docs [@mendelk](https://github.com/mendelk) ([#2256](https://github.com/paperless-ngx/paperless-ngx/pull/2256))
-   Fix: support in advanced search, fix tags filter badge count for excluded [@shamoon](https://github.com/shamoon) ([#2205](https://github.com/paperless-ngx/paperless-ngx/pull/2205))
-   Bugfix: Don't run system checks on migrate [@stumpylog](https://github.com/stumpylog) ([#2183](https://github.com/paperless-ngx/paperless-ngx/pull/2183))
-   Bugfix: Decoding task signals could fail on datetime type [@stumpylog](https://github.com/stumpylog) ([#2058](https://github.com/paperless-ngx/paperless-ngx/pull/2058))

### Documentation

-   Fixed typo in docs [@mendelk](https://github.com/mendelk) ([#2256](https://github.com/paperless-ngx/paperless-ngx/pull/2256))
-   Docs: More fixes and improvements [@tooomm](https://github.com/tooomm) ([#2203](https://github.com/paperless-ngx/paperless-ngx/pull/2203))
-   Docs: Fix leftover issues from conversion [@tooomm](https://github.com/tooomm) ([#2172](https://github.com/paperless-ngx/paperless-ngx/pull/2172))
-   Docs: Fix broken internal links [@tooomm](https://github.com/tooomm) ([#2165](https://github.com/paperless-ngx/paperless-ngx/pull/2165))
-   Update setup.md [@Weltraumschaf](https://github.com/Weltraumschaf) ([#2157](https://github.com/paperless-ngx/paperless-ngx/pull/2157))
-   Chore: Cleanup of new documentation [@stumpylog](https://github.com/stumpylog) ([#2137](https://github.com/paperless-ngx/paperless-ngx/pull/2137))
-   [Documentation] Add v1.10.2 changelog [@github-actions](https://github.com/github-actions) ([#2114](https://github.com/paperless-ngx/paperless-ngx/pull/2114))

### Maintenance

-   Chore: Adds notable label for release drafter [@stumpylog](https://github.com/stumpylog) ([#2200](https://github.com/paperless-ngx/paperless-ngx/pull/2200))
-   Chore: Prevent forks from having failing CI runs by default [@tooomm](https://github.com/tooomm) ([#2166](https://github.com/paperless-ngx/paperless-ngx/pull/2166))
-   Chore: migrate to eslint [@shamoon](https://github.com/shamoon) ([#2199](https://github.com/paperless-ngx/paperless-ngx/pull/2199))
-   Feature: Adds PaperlessTask admin page interface [@stumpylog](https://github.com/stumpylog) ([#2184](https://github.com/paperless-ngx/paperless-ngx/pull/2184))
-   Chore: Changes qpdf to be cross compiled for large speed up [@stumpylog](https://github.com/stumpylog) ([#2181](https://github.com/paperless-ngx/paperless-ngx/pull/2181))
-   Chore: Decrease time to build pikepdf [@stumpylog](https://github.com/stumpylog) ([#2178](https://github.com/paperless-ngx/paperless-ngx/pull/2178))
-   Chore: Minor CI cleanups [@stumpylog](https://github.com/stumpylog) ([#2175](https://github.com/paperless-ngx/paperless-ngx/pull/2175))

### All App Changes

-   Add ability to provide the configuration file path using an env variable [@hashworks](https://github.com/hashworks) ([#2241](https://github.com/paperless-ngx/paperless-ngx/pull/2241))
-   Fix: support in advanced search, fix tags filter badge count for excluded [@shamoon](https://github.com/shamoon) ([#2205](https://github.com/paperless-ngx/paperless-ngx/pull/2205))
-   Chore: migrate to eslint [@shamoon](https://github.com/shamoon) ([#2199](https://github.com/paperless-ngx/paperless-ngx/pull/2199))
-   Feature: Adds option to allow a user to export directly to a zipfile [@stumpylog](https://github.com/stumpylog) ([#2004](https://github.com/paperless-ngx/paperless-ngx/pull/2004))
-   Feature: Adds PaperlessTask admin page interface [@stumpylog](https://github.com/stumpylog) ([#2184](https://github.com/paperless-ngx/paperless-ngx/pull/2184))
-   Bugfix: Decoding task signals could fail on datetime type [@stumpylog](https://github.com/stumpylog) ([#2058](https://github.com/paperless-ngx/paperless-ngx/pull/2058))
-   Feature: speed up frontend by truncating content [@shamoon](https://github.com/shamoon) ([#2028](https://github.com/paperless-ngx/paperless-ngx/pull/2028))
-   Feature: Allow bulk download API to follow file name formatting [@stumpylog](https://github.com/stumpylog) ([#2003](https://github.com/paperless-ngx/paperless-ngx/pull/2003))
-   Feature: Bake NLTK into Docker image [@stumpylog](https://github.com/stumpylog) ([#2129](https://github.com/paperless-ngx/paperless-ngx/pull/2129))
-   Chore: Apply live testing backoff logic to new mail tests [@stumpylog](https://github.com/stumpylog) ([#2134](https://github.com/paperless-ngx/paperless-ngx/pull/2134))
-   Feature: frontend paperless mail [@shamoon](https://github.com/shamoon) ([#2000](https://github.com/paperless-ngx/paperless-ngx/pull/2000))
-   Feature: Ability to consume mails and eml files [@p-h-a-i-l](https://github.com/p-h-a-i-l) ([#848](https://github.com/paperless-ngx/paperless-ngx/pull/848))

## paperless-ngx 1.10.2

### Features

-   Take ownership of k8s-at-home Helm chart [@alexander-bauer](https://github.com/alexander-bauer) ([#1947](https://github.com/paperless-ngx/paperless-ngx/pull/1947))

### Bug Fixes

-   Bugfix: Language code checks around two part languages [@stumpylog](https://github.com/stumpylog) ([#2112](https://github.com/paperless-ngx/paperless-ngx/pull/2112))
-   Bugfix: Redis socket compatibility didn't handle URLs with ports [@stumpylog](https://github.com/stumpylog) ([#2109](https://github.com/paperless-ngx/paperless-ngx/pull/2109))
-   Bugfix: Incompatible URL schemes for socket based Redis [@stumpylog](https://github.com/stumpylog) ([#2092](https://github.com/paperless-ngx/paperless-ngx/pull/2092))
-   Fix doc links in contributing [@tooomm](https://github.com/tooomm) ([#2102](https://github.com/paperless-ngx/paperless-ngx/pull/2102))

### Documentation

-   Docs: Some more small MkDocs updates [@tooomm](https://github.com/tooomm) ([#2106](https://github.com/paperless-ngx/paperless-ngx/pull/2106))
-   Chore: Cleans up documentation links [@stumpylog](https://github.com/stumpylog) ([#2104](https://github.com/paperless-ngx/paperless-ngx/pull/2104))
-   Feature: Move docs to material-mkdocs [@shamoon](https://github.com/shamoon) ([#2067](https://github.com/paperless-ngx/paperless-ngx/pull/2067))
-   Chore: Add v1.10.1 changelong [@shamoon](https://github.com/shamoon) ([#2082](https://github.com/paperless-ngx/paperless-ngx/pull/2082))

### Maintenance

-   Take ownership of k8s-at-home Helm chart [@alexander-bauer](https://github.com/alexander-bauer) ([#1947](https://github.com/paperless-ngx/paperless-ngx/pull/1947))

### All App Changes

-   Bugfix: Language code checks around two part languages [@stumpylog](https://github.com/stumpylog) ([#2112](https://github.com/paperless-ngx/paperless-ngx/pull/2112))
-   Bugfix: Redis socket compatibility didn't handle URLs with ports [@stumpylog](https://github.com/stumpylog) ([#2109](https://github.com/paperless-ngx/paperless-ngx/pull/2109))
-   Bugfix: Incompatible URL schemes for socket based Redis [@stumpylog](https://github.com/stumpylog) ([#2092](https://github.com/paperless-ngx/paperless-ngx/pull/2092))

## paperless-ngx 1.10.1

### Features

-   Feature: Allows documents in WebP format [@stumpylog](https://github.com/stumpylog) ([#1984](https://github.com/paperless-ngx/paperless-ngx/pull/1984))

### Bug Fixes

-   Fix: frontend tasks display in 1.10.0 [@shamoon](https://github.com/shamoon) ([#2073](https://github.com/paperless-ngx/paperless-ngx/pull/2073))
-   Bugfix: Custom startup commands weren't run as root [@stumpylog](https://github.com/stumpylog) ([#2069](https://github.com/paperless-ngx/paperless-ngx/pull/2069))
-   Bugfix: Add libatomic for armv7 compatibility [@stumpylog](https://github.com/stumpylog) ([#2066](https://github.com/paperless-ngx/paperless-ngx/pull/2066))
-   Bugfix: Don't silence an exception when trying to handle file naming [@stumpylog](https://github.com/stumpylog) ([#2062](https://github.com/paperless-ngx/paperless-ngx/pull/2062))
-   Bugfix: Some tesseract languages aren't detected as installed. [@stumpylog](https://github.com/stumpylog) ([#2057](https://github.com/paperless-ngx/paperless-ngx/pull/2057))

### Maintenance

-   Chore: Use a maintained upload-release-asset [@stumpylog](https://github.com/stumpylog) ([#2055](https://github.com/paperless-ngx/paperless-ngx/pull/2055))

### Dependencies

  <details>
  <summary>5 changes</summary>

-   Bump tslib from 2.4.0 to 2.4.1 in /src-ui @dependabot ([#2076](https://github.com/paperless-ngx/paperless-ngx/pull/2076))
-   Bump @<!---->angular-builders/jest from 14.0.1 to 14.1.0 in /src-ui @dependabot ([#2079](https://github.com/paperless-ngx/paperless-ngx/pull/2079))
-   Bump jest-preset-angular from 12.2.2 to 12.2.3 in /src-ui @dependabot ([#2078](https://github.com/paperless-ngx/paperless-ngx/pull/2078))
-   Bump ngx-file-drop from 14.0.1 to 14.0.2 in /src-ui @dependabot ([#2080](https://github.com/paperless-ngx/paperless-ngx/pull/2080))
-   Bump @<!---->ngneat/dirty-check-forms from 3.0.2 to 3.0.3 in /src-ui @dependabot ([#2077](https://github.com/paperless-ngx/paperless-ngx/pull/2077))
</details>

### All App Changes

-   Bump tslib from 2.4.0 to 2.4.1 in /src-ui @dependabot ([#2076](https://github.com/paperless-ngx/paperless-ngx/pull/2076))
-   Bump @<!---->angular-builders/jest from 14.0.1 to 14.1.0 in /src-ui @dependabot ([#2079](https://github.com/paperless-ngx/paperless-ngx/pull/2079))
-   Bump jest-preset-angular from 12.2.2 to 12.2.3 in /src-ui @dependabot ([#2078](https://github.com/paperless-ngx/paperless-ngx/pull/2078))
-   Bump ngx-file-drop from 14.0.1 to 14.0.2 in /src-ui @dependabot ([#2080](https://github.com/paperless-ngx/paperless-ngx/pull/2080))
-   Bump @<!---->ngneat/dirty-check-forms from 3.0.2 to 3.0.3 in /src-ui @dependabot ([#2077](https://github.com/paperless-ngx/paperless-ngx/pull/2077))
-   Fix: frontend tasks display in 1.10.0 [@shamoon](https://github.com/shamoon) ([#2073](https://github.com/paperless-ngx/paperless-ngx/pull/2073))
-   Bugfix: Don't silence an exception when trying to handle file naming [@stumpylog](https://github.com/stumpylog) ([#2062](https://github.com/paperless-ngx/paperless-ngx/pull/2062))
-   Bugfix: Some tesseract languages aren't detected as installed. [@stumpylog](https://github.com/stumpylog) ([#2057](https://github.com/paperless-ngx/paperless-ngx/pull/2057))

## paperless-ngx 1.10.0

### Features

-   Feature: Capture stdout \& stderr of the pre/post consume scripts [@stumpylog](https://github.com/stumpylog) ([#1967](https://github.com/paperless-ngx/paperless-ngx/pull/1967))
-   Feature: Allow running custom container initialization scripts [@stumpylog](https://github.com/stumpylog) ([#1838](https://github.com/paperless-ngx/paperless-ngx/pull/1838))
-   Feature: Add more file name formatting options [@stumpylog](https://github.com/stumpylog) ([#1906](https://github.com/paperless-ngx/paperless-ngx/pull/1906))
-   Feature: 1.9.2 UI tweaks [@shamoon](https://github.com/shamoon) ([#1886](https://github.com/paperless-ngx/paperless-ngx/pull/1886))
-   Feature: Optional celery monitoring with Flower [@stumpylog](https://github.com/stumpylog) ([#1810](https://github.com/paperless-ngx/paperless-ngx/pull/1810))
-   Feature: Save pending tasks for frontend [@stumpylog](https://github.com/stumpylog) ([#1816](https://github.com/paperless-ngx/paperless-ngx/pull/1816))
-   Feature: Improved processing for automatic matching [@stumpylog](https://github.com/stumpylog) ([#1609](https://github.com/paperless-ngx/paperless-ngx/pull/1609))
-   Feature: Transition to celery for background tasks [@stumpylog](https://github.com/stumpylog) ([#1648](https://github.com/paperless-ngx/paperless-ngx/pull/1648))
-   Feature: UI Welcome Tour [@shamoon](https://github.com/shamoon) ([#1644](https://github.com/paperless-ngx/paperless-ngx/pull/1644))
-   Feature: slim sidebar [@shamoon](https://github.com/shamoon) ([#1641](https://github.com/paperless-ngx/paperless-ngx/pull/1641))
-   change default matching algo to auto and move to constant [@NiFNi](https://github.com/NiFNi) ([#1754](https://github.com/paperless-ngx/paperless-ngx/pull/1754))
-   Feature: Enable end to end Tika testing in CI [@stumpylog](https://github.com/stumpylog) ([#1757](https://github.com/paperless-ngx/paperless-ngx/pull/1757))
-   Feature: frontend update checking settings [@shamoon](https://github.com/shamoon) ([#1692](https://github.com/paperless-ngx/paperless-ngx/pull/1692))
-   Feature: Upgrade to qpdf 11, pikepdf 6 \& ocrmypdf 14 [@stumpylog](https://github.com/stumpylog) ([#1642](https://github.com/paperless-ngx/paperless-ngx/pull/1642))

### Bug Fixes

-   Bugfix: Fix created_date being a string [@stumpylog](https://github.com/stumpylog) ([#2023](https://github.com/paperless-ngx/paperless-ngx/pull/2023))
-   Bugfix: Fixes an issue with mixed text and images when redoing OCR [@stumpylog](https://github.com/stumpylog) ([#2017](https://github.com/paperless-ngx/paperless-ngx/pull/2017))
-   Bugfix: Always re-try barcodes with pdf2image [@stumpylog](https://github.com/stumpylog) ([#1953](https://github.com/paperless-ngx/paperless-ngx/pull/1953))
-   Fix: using `CONSUMER_SUBDIRS_AS_TAGS` causes failure with Celery in `dev` [@shamoon](https://github.com/shamoon) ([#1942](https://github.com/paperless-ngx/paperless-ngx/pull/1942))
-   Fix mail consumption broken in `dev` after move to celery [@shamoon](https://github.com/shamoon) ([#1934](https://github.com/paperless-ngx/paperless-ngx/pull/1934))
-   Bugfix: Prevent file handling from running with stale data [@stumpylog](https://github.com/stumpylog) ([#1905](https://github.com/paperless-ngx/paperless-ngx/pull/1905))
-   Chore: Reduce nuisance CI test failures [@stumpylog](https://github.com/stumpylog) ([#1922](https://github.com/paperless-ngx/paperless-ngx/pull/1922))
-   Bugfix: Unintentional deletion of feature tagged Docker images [@stumpylog](https://github.com/stumpylog) ([#1896](https://github.com/paperless-ngx/paperless-ngx/pull/1896))
-   Fix: independent control of saved views [@shamoon](https://github.com/shamoon) ([#1868](https://github.com/paperless-ngx/paperless-ngx/pull/1868))
-   Fix: frontend relative date searches [@shamoon](https://github.com/shamoon) ([#1865](https://github.com/paperless-ngx/paperless-ngx/pull/1865))
-   Chore: Fixes pipenv issues [@stumpylog](https://github.com/stumpylog) ([#1873](https://github.com/paperless-ngx/paperless-ngx/pull/1873))
-   Bugfix: Handle password protected PDFs during barcode detection [@stumpylog](https://github.com/stumpylog) ([#1858](https://github.com/paperless-ngx/paperless-ngx/pull/1858))
-   Fix: Allows configuring barcodes with pdf2image instead of pikepdf [@stumpylog](https://github.com/stumpylog) ([#1857](https://github.com/paperless-ngx/paperless-ngx/pull/1857))
-   Bugfix: Reverts the change around skip_noarchive [@stumpylog](https://github.com/stumpylog) ([#1829](https://github.com/paperless-ngx/paperless-ngx/pull/1829))
-   Fix: missing loadViewConfig breaks loading saved view [@shamoon](https://github.com/shamoon) ([#1792](https://github.com/paperless-ngx/paperless-ngx/pull/1792))
-   Bugfix: Fallback to pdf2image if pikepdf fails [@stumpylog](https://github.com/stumpylog) ([#1745](https://github.com/paperless-ngx/paperless-ngx/pull/1745))
-   Fix: creating new storage path on document edit fails to update menu [@shamoon](https://github.com/shamoon) ([#1777](https://github.com/paperless-ngx/paperless-ngx/pull/1777))
-   Bugfix: Files containing barcodes uploaded via web are not consumed after splitting [@stumpylog](https://github.com/stumpylog) ([#1762](https://github.com/paperless-ngx/paperless-ngx/pull/1762))
-   Bugfix: Fix email labeling for non-Gmail servers [@stumpylog](https://github.com/stumpylog) ([#1755](https://github.com/paperless-ngx/paperless-ngx/pull/1755))
-   Fix: allow preview for .csv files [@shamoon](https://github.com/shamoon) ([#1744](https://github.com/paperless-ngx/paperless-ngx/pull/1744))
-   Bugfix: csv recognition by consumer [@bin101](https://github.com/bin101) ([#1726](https://github.com/paperless-ngx/paperless-ngx/pull/1726))
-   Bugfix: Include document title when a duplicate is detected [@stumpylog](https://github.com/stumpylog) ([#1696](https://github.com/paperless-ngx/paperless-ngx/pull/1696))
-   Bugfix: Set MySql charset [@stumpylog](https://github.com/stumpylog) ([#1687](https://github.com/paperless-ngx/paperless-ngx/pull/1687))
-   Mariadb compose files should use `PAPERLESS_DBPASS` [@shamoon](https://github.com/shamoon) ([#1683](https://github.com/paperless-ngx/paperless-ngx/pull/1683))

### Documentation

-   Documentation: Update MariaDB docs to note some potential issues [@stumpylog](https://github.com/stumpylog) ([#2016](https://github.com/paperless-ngx/paperless-ngx/pull/2016))
-   Documentation: Add note re MS exchange servers [@shamoon](https://github.com/shamoon) ([#1780](https://github.com/paperless-ngx/paperless-ngx/pull/1780))
-   Chore: Updates Gotenberg versions [@stumpylog](https://github.com/stumpylog) ([#1768](https://github.com/paperless-ngx/paperless-ngx/pull/1768))
-   Documentation: Tweak LinuxServer [@stumpylog](https://github.com/stumpylog) ([#1761](https://github.com/paperless-ngx/paperless-ngx/pull/1761))
-   Documentation: Adds troubleshooting note about Kubernetes and ports [@stumpylog](https://github.com/stumpylog) ([#1731](https://github.com/paperless-ngx/paperless-ngx/pull/1731))
-   Documentation: LinuxServer.io Migration [@stumpylog](https://github.com/stumpylog) ([#1733](https://github.com/paperless-ngx/paperless-ngx/pull/1733))
-   [Documentation] Add v1.9.2 changelog [@github-actions](https://github.com/github-actions) ([#1671](https://github.com/paperless-ngx/paperless-ngx/pull/1671))

### Maintenance

-   Bump tj-actions/changed-files from 32 to 34 [@dependabot](https://github.com/dependabot) ([#1915](https://github.com/paperless-ngx/paperless-ngx/pull/1915))
-   Chore: Fix `dev` trying to build Pillow or lxml [@stumpylog](https://github.com/stumpylog) ([#1909](https://github.com/paperless-ngx/paperless-ngx/pull/1909))
-   Chore: Fixes pipenv issues [@stumpylog](https://github.com/stumpylog) ([#1873](https://github.com/paperless-ngx/paperless-ngx/pull/1873))
-   Chore: Simplified registry cleanup [@stumpylog](https://github.com/stumpylog) ([#1812](https://github.com/paperless-ngx/paperless-ngx/pull/1812))
-   Chore: Fixing deprecated workflow commands [@stumpylog](https://github.com/stumpylog) ([#1786](https://github.com/paperless-ngx/paperless-ngx/pull/1786))
-   Chore: Python library update + test fixes [@stumpylog](https://github.com/stumpylog) ([#1773](https://github.com/paperless-ngx/paperless-ngx/pull/1773))
-   Chore: Updates Gotenberg versions [@stumpylog](https://github.com/stumpylog) ([#1768](https://github.com/paperless-ngx/paperless-ngx/pull/1768))
-   Bump leonsteinhaeuser/project-beta-automations from 1.3.0 to 2.0.1 [@dependabot](https://github.com/dependabot) ([#1703](https://github.com/paperless-ngx/paperless-ngx/pull/1703))
-   Bump tj-actions/changed-files from 29.0.2 to 31.0.2 [@dependabot](https://github.com/dependabot) ([#1702](https://github.com/paperless-ngx/paperless-ngx/pull/1702))
-   Bump actions/checkout from 2 to 3 [@dependabot](https://github.com/dependabot) ([#1704](https://github.com/paperless-ngx/paperless-ngx/pull/1704))
-   Bump actions/setup-python from 3 to 4 [@dependabot](https://github.com/dependabot) ([#1705](https://github.com/paperless-ngx/paperless-ngx/pull/1705))

### Dependencies

<details>
<summary>31 changes</summary>

-   Bugfix: Downgrade cryptography for armv7 compatibility [@stumpylog](https://github.com/stumpylog) ([#1954](https://github.com/paperless-ngx/paperless-ngx/pull/1954))
-   Chore: Bulk library updates + loosen restrictions [@stumpylog](https://github.com/stumpylog) ([#1949](https://github.com/paperless-ngx/paperless-ngx/pull/1949))
-   Bump tj-actions/changed-files from 32 to 34 [@dependabot](https://github.com/dependabot) ([#1915](https://github.com/paperless-ngx/paperless-ngx/pull/1915))
-   Bump scikit-learn from 1.1.2 to 1.1.3 [@dependabot](https://github.com/dependabot) ([#1903](https://github.com/paperless-ngx/paperless-ngx/pull/1903))
-   Bump angular packages as bundle [@dependabot](https://github.com/dependabot) ([#1910](https://github.com/paperless-ngx/paperless-ngx/pull/1910))
-   Bump ngx-ui-tour-ng-bootstrap from 11.0.0 to 11.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1911](https://github.com/paperless-ngx/paperless-ngx/pull/1911))
-   Bump jest-environment-jsdom from 29.1.2 to 29.2.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1914](https://github.com/paperless-ngx/paperless-ngx/pull/1914))
-   Bump pillow from 9.2.0 to 9.3.0 [@dependabot](https://github.com/dependabot) ([#1904](https://github.com/paperless-ngx/paperless-ngx/pull/1904))
-   Bump pytest from 7.1.3 to 7.2.0 [@dependabot](https://github.com/dependabot) ([#1902](https://github.com/paperless-ngx/paperless-ngx/pull/1902))
-   Bump tox from 3.26.0 to 3.27.0 [@dependabot](https://github.com/dependabot) ([#1901](https://github.com/paperless-ngx/paperless-ngx/pull/1901))
-   Bump zipp from 3.9.0 to 3.10.0 [@dependabot](https://github.com/dependabot) ([#1860](https://github.com/paperless-ngx/paperless-ngx/pull/1860))
-   Bump pytest-env from 0.6.2 to 0.8.1 [@dependabot](https://github.com/dependabot) ([#1859](https://github.com/paperless-ngx/paperless-ngx/pull/1859))
-   Bump sphinx from 5.2.3 to 5.3.0 [@dependabot](https://github.com/dependabot) ([#1817](https://github.com/paperless-ngx/paperless-ngx/pull/1817))
-   Chore: downgrade channels-redis [@stumpylog](https://github.com/stumpylog) ([#1802](https://github.com/paperless-ngx/paperless-ngx/pull/1802))
-   Chore: Update to qpdf 11.1.1 and update backend libraries [@stumpylog](https://github.com/stumpylog) ([#1749](https://github.com/paperless-ngx/paperless-ngx/pull/1749))
-   Bump myst-parser from 0.18.0 to 0.18.1 [@dependabot](https://github.com/dependabot) ([#1738](https://github.com/paperless-ngx/paperless-ngx/pull/1738))
-   Bump leonsteinhaeuser/project-beta-automations from 1.3.0 to 2.0.1 [@dependabot](https://github.com/dependabot) ([#1703](https://github.com/paperless-ngx/paperless-ngx/pull/1703))
-   Bump tj-actions/changed-files from 29.0.2 to 31.0.2 [@dependabot](https://github.com/dependabot) ([#1702](https://github.com/paperless-ngx/paperless-ngx/pull/1702))
-   Bump actions/checkout from 2 to 3 [@dependabot](https://github.com/dependabot) ([#1704](https://github.com/paperless-ngx/paperless-ngx/pull/1704))
-   Bump actions/setup-python from 3 to 4 [@dependabot](https://github.com/dependabot) ([#1705](https://github.com/paperless-ngx/paperless-ngx/pull/1705))
-   Bump rxjs from 7.5.6 to 7.5.7 in /src-ui [@dependabot](https://github.com/dependabot) ([#1720](https://github.com/paperless-ngx/paperless-ngx/pull/1720))
-   Bump uuid from 8.3.2 to 9.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1716](https://github.com/paperless-ngx/paperless-ngx/pull/1716))
-   Bump ng2-pdf-viewer from 9.1.0 to 9.1.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1717](https://github.com/paperless-ngx/paperless-ngx/pull/1717))
-   Bump ngx-color from 8.0.2 to 8.0.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#1715](https://github.com/paperless-ngx/paperless-ngx/pull/1715))
-   Bump concurrently from 7.3.0 to 7.4.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1719](https://github.com/paperless-ngx/paperless-ngx/pull/1719))
-   Bump [@<!---->types/node from 18.7.14 to 18.7.23 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.7.14 to 18.7.23 in /src-ui @dependabot) ([#1718](https://github.com/paperless-ngx/paperless-ngx/pull/1718))
-   Bump jest-environment-jsdom from 29.0.1 to 29.1.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1714](https://github.com/paperless-ngx/paperless-ngx/pull/1714))
-   Bump [@<!---->angular/cli @<!---->angular/core @dependabot](https://github.com/<!---->angular/cli @<!---->angular/core @dependabot) ([#1708](https://github.com/paperless-ngx/paperless-ngx/pull/1708))
-   Bump cypress from 10.7.0 to 10.9.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1707](https://github.com/paperless-ngx/paperless-ngx/pull/1707))
-   Bump bootstrap from 5.2.0 to 5.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1710](https://github.com/paperless-ngx/paperless-ngx/pull/1710))
-   Bump typescript from 4.7.4 to 4.8.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#1706](https://github.com/paperless-ngx/paperless-ngx/pull/1706))
</details>

### All App Changes

-   Add info that re-do OCR doesn't automatically refresh content [@shamoon](https://github.com/shamoon) ([#2025](https://github.com/paperless-ngx/paperless-ngx/pull/2025))
-   Bugfix: Fix created_date being a string [@stumpylog](https://github.com/stumpylog) ([#2023](https://github.com/paperless-ngx/paperless-ngx/pull/2023))
-   Bugfix: Fixes an issue with mixed text and images when redoing OCR [@stumpylog](https://github.com/stumpylog) ([#2017](https://github.com/paperless-ngx/paperless-ngx/pull/2017))
-   Bugfix: Don't allow exceptions during date parsing to fail consume [@stumpylog](https://github.com/stumpylog) ([#1998](https://github.com/paperless-ngx/paperless-ngx/pull/1998))
-   Feature: Capture stdout \& stderr of the pre/post consume scripts [@stumpylog](https://github.com/stumpylog) ([#1967](https://github.com/paperless-ngx/paperless-ngx/pull/1967))
-   Bugfix: Always re-try barcodes with pdf2image [@stumpylog](https://github.com/stumpylog) ([#1953](https://github.com/paperless-ngx/paperless-ngx/pull/1953))
-   Fix: using `CONSUMER_SUBDIRS_AS_TAGS` causes failure with Celery in `dev` [@shamoon](https://github.com/shamoon) ([#1942](https://github.com/paperless-ngx/paperless-ngx/pull/1942))
-   Fix mail consumption broken in `dev` after move to celery [@shamoon](https://github.com/shamoon) ([#1934](https://github.com/paperless-ngx/paperless-ngx/pull/1934))
-   Bugfix: Prevent file handling from running with stale data [@stumpylog](https://github.com/stumpylog) ([#1905](https://github.com/paperless-ngx/paperless-ngx/pull/1905))
-   Chore: Reduce nuisance CI test failures [@stumpylog](https://github.com/stumpylog) ([#1922](https://github.com/paperless-ngx/paperless-ngx/pull/1922))
-   Bump scikit-learn from 1.1.2 to 1.1.3 [@dependabot](https://github.com/dependabot) ([#1903](https://github.com/paperless-ngx/paperless-ngx/pull/1903))
-   Bump angular packages as bundle [@dependabot](https://github.com/dependabot) ([#1910](https://github.com/paperless-ngx/paperless-ngx/pull/1910))
-   Bump ngx-ui-tour-ng-bootstrap from 11.0.0 to 11.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1911](https://github.com/paperless-ngx/paperless-ngx/pull/1911))
-   Bump jest-environment-jsdom from 29.1.2 to 29.2.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1914](https://github.com/paperless-ngx/paperless-ngx/pull/1914))
-   Feature: Add more file name formatting options [@stumpylog](https://github.com/stumpylog) ([#1906](https://github.com/paperless-ngx/paperless-ngx/pull/1906))
-   Bump pillow from 9.2.0 to 9.3.0 [@dependabot](https://github.com/dependabot) ([#1904](https://github.com/paperless-ngx/paperless-ngx/pull/1904))
-   Bump pytest from 7.1.3 to 7.2.0 [@dependabot](https://github.com/dependabot) ([#1902](https://github.com/paperless-ngx/paperless-ngx/pull/1902))
-   Bump tox from 3.26.0 to 3.27.0 [@dependabot](https://github.com/dependabot) ([#1901](https://github.com/paperless-ngx/paperless-ngx/pull/1901))
-   directly use rapidfuzz [@maxbachmann](https://github.com/maxbachmann) ([#1899](https://github.com/paperless-ngx/paperless-ngx/pull/1899))
-   Feature: 1.9.2 UI tweaks [@shamoon](https://github.com/shamoon) ([#1886](https://github.com/paperless-ngx/paperless-ngx/pull/1886))
-   Bump zipp from 3.9.0 to 3.10.0 [@dependabot](https://github.com/dependabot) ([#1860](https://github.com/paperless-ngx/paperless-ngx/pull/1860))
-   Fix: independent control of saved views [@shamoon](https://github.com/shamoon) ([#1868](https://github.com/paperless-ngx/paperless-ngx/pull/1868))
-   Fix: frontend relative date searches [@shamoon](https://github.com/shamoon) ([#1865](https://github.com/paperless-ngx/paperless-ngx/pull/1865))
-   Django error W003 - MariaDB may not allow unique CharFields to have a max_length > 255. [@Sblop](https://github.com/Sblop) ([#1881](https://github.com/paperless-ngx/paperless-ngx/pull/1881))
-   Bump pytest-env from 0.6.2 to 0.8.1 [@dependabot](https://github.com/dependabot) ([#1859](https://github.com/paperless-ngx/paperless-ngx/pull/1859))
-   Fix: Allows configuring barcodes with pdf2image instead of pikepdf [@stumpylog](https://github.com/stumpylog) ([#1857](https://github.com/paperless-ngx/paperless-ngx/pull/1857))
-   Feature: Save pending tasks for frontend [@stumpylog](https://github.com/stumpylog) ([#1816](https://github.com/paperless-ngx/paperless-ngx/pull/1816))
-   Bugfix: Reverts the change around skip_noarchive [@stumpylog](https://github.com/stumpylog) ([#1829](https://github.com/paperless-ngx/paperless-ngx/pull/1829))
-   Bump sphinx from 5.2.3 to 5.3.0 [@dependabot](https://github.com/dependabot) ([#1817](https://github.com/paperless-ngx/paperless-ngx/pull/1817))
-   Fix: missing loadViewConfig breaks loading saved view [@shamoon](https://github.com/shamoon) ([#1792](https://github.com/paperless-ngx/paperless-ngx/pull/1792))
-   Bugfix: Fallback to pdf2image if pikepdf fails [@stumpylog](https://github.com/stumpylog) ([#1745](https://github.com/paperless-ngx/paperless-ngx/pull/1745))
-   Fix: creating new storage path on document edit fails to update menu [@shamoon](https://github.com/shamoon) ([#1777](https://github.com/paperless-ngx/paperless-ngx/pull/1777))
-   Chore: Python library update + test fixes [@stumpylog](https://github.com/stumpylog) ([#1773](https://github.com/paperless-ngx/paperless-ngx/pull/1773))
-   Feature: Improved processing for automatic matching [@stumpylog](https://github.com/stumpylog) ([#1609](https://github.com/paperless-ngx/paperless-ngx/pull/1609))
-   Feature: Transition to celery for background tasks [@stumpylog](https://github.com/stumpylog) ([#1648](https://github.com/paperless-ngx/paperless-ngx/pull/1648))
-   Feature: UI Welcome Tour [@shamoon](https://github.com/shamoon) ([#1644](https://github.com/paperless-ngx/paperless-ngx/pull/1644))
-   Feature: slim sidebar [@shamoon](https://github.com/shamoon) ([#1641](https://github.com/paperless-ngx/paperless-ngx/pull/1641))
-   Bugfix: Files containing barcodes uploaded via web are not consumed after splitting [@stumpylog](https://github.com/stumpylog) ([#1762](https://github.com/paperless-ngx/paperless-ngx/pull/1762))
-   change default matching algo to auto and move to constant [@NiFNi](https://github.com/NiFNi) ([#1754](https://github.com/paperless-ngx/paperless-ngx/pull/1754))
-   Bugfix: Fix email labeling for non-Gmail servers [@stumpylog](https://github.com/stumpylog) ([#1755](https://github.com/paperless-ngx/paperless-ngx/pull/1755))
-   Feature: frontend update checking settings [@shamoon](https://github.com/shamoon) ([#1692](https://github.com/paperless-ngx/paperless-ngx/pull/1692))
-   Fix: allow preview for .csv files [@shamoon](https://github.com/shamoon) ([#1744](https://github.com/paperless-ngx/paperless-ngx/pull/1744))
-   Bump myst-parser from 0.18.0 to 0.18.1 [@dependabot](https://github.com/dependabot) ([#1738](https://github.com/paperless-ngx/paperless-ngx/pull/1738))
-   Bugfix: csv recognition by consumer [@bin101](https://github.com/bin101) ([#1726](https://github.com/paperless-ngx/paperless-ngx/pull/1726))
-   Bugfix: Include document title when a duplicate is detected [@stumpylog](https://github.com/stumpylog) ([#1696](https://github.com/paperless-ngx/paperless-ngx/pull/1696))
-   Bump rxjs from 7.5.6 to 7.5.7 in /src-ui [@dependabot](https://github.com/dependabot) ([#1720](https://github.com/paperless-ngx/paperless-ngx/pull/1720))
-   Bump uuid from 8.3.2 to 9.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1716](https://github.com/paperless-ngx/paperless-ngx/pull/1716))
-   Bump ng2-pdf-viewer from 9.1.0 to 9.1.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1717](https://github.com/paperless-ngx/paperless-ngx/pull/1717))
-   Bump ngx-color from 8.0.2 to 8.0.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#1715](https://github.com/paperless-ngx/paperless-ngx/pull/1715))
-   Bump concurrently from 7.3.0 to 7.4.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1719](https://github.com/paperless-ngx/paperless-ngx/pull/1719))
-   Bump [@<!---->types/node from 18.7.14 to 18.7.23 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.7.14 to 18.7.23 in /src-ui @dependabot) ([#1718](https://github.com/paperless-ngx/paperless-ngx/pull/1718))
-   Bump jest-environment-jsdom from 29.0.1 to 29.1.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1714](https://github.com/paperless-ngx/paperless-ngx/pull/1714))
-   Bump [@<!---->angular/cli @<!---->angular/core @dependabot](https://github.com/<!---->angular/cli @<!---->angular/core @dependabot) ([#1708](https://github.com/paperless-ngx/paperless-ngx/pull/1708))
-   Bump cypress from 10.7.0 to 10.9.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1707](https://github.com/paperless-ngx/paperless-ngx/pull/1707))
-   Bump bootstrap from 5.2.0 to 5.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1710](https://github.com/paperless-ngx/paperless-ngx/pull/1710))
-   Bump typescript from 4.7.4 to 4.8.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#1706](https://github.com/paperless-ngx/paperless-ngx/pull/1706))
-   Bugfix: Set MySql charset [@stumpylog](https://github.com/stumpylog) ([#1687](https://github.com/paperless-ngx/paperless-ngx/pull/1687))

## paperless-ngx 1.9.2

### Bug Fixes

-   Bugfix: Allow PAPERLESS_OCR_CLEAN=none [@shamoon](https://github.com/shamoon) ([#1670](https://github.com/paperless-ngx/paperless-ngx/pull/1670))

### All App Changes

-   Chore: Bumps version numbers to 1.9.2 [@stumpylog](https://github.com/stumpylog) ([#1666](https://github.com/paperless-ngx/paperless-ngx/pull/1666))

## paperless-ngx 1.9.1

### Notes

-   Version 1.9.1 incorrectly displays the version string as 1.9.0

### Bug Fixes

-   Bugfix: Fixes missing OCR mode skip_noarchive [@stumpylog](https://github.com/stumpylog) ([#1645](https://github.com/paperless-ngx/paperless-ngx/pull/1645))
-   Fix reset button padding on small screens [@shamoon](https://github.com/shamoon) ([#1646](https://github.com/paperless-ngx/paperless-ngx/pull/1646))

### Documentation

-   Improve docs re [@janis-ax](https://github.com/janis-ax) ([#1625](https://github.com/paperless-ngx/paperless-ngx/pull/1625))
-   [Documentation] Add v1.9.0 changelog [@github-actions](https://github.com/github-actions) ([#1639](https://github.com/paperless-ngx/paperless-ngx/pull/1639))

### All App Changes

-   Bugfix: Fixes missing OCR mode skip_noarchive [@stumpylog](https://github.com/stumpylog) ([#1645](https://github.com/paperless-ngx/paperless-ngx/pull/1645))
-   Fix reset button padding on small screens [@shamoon](https://github.com/shamoon) ([#1646](https://github.com/paperless-ngx/paperless-ngx/pull/1646))

## paperless-ngx 1.9.0

### Features

-   Feature: Faster, less memory barcode handling [@stumpylog](https://github.com/stumpylog) ([#1594](https://github.com/paperless-ngx/paperless-ngx/pull/1594))
-   Feature: Display django-q process names [@stumpylog](https://github.com/stumpylog) ([#1567](https://github.com/paperless-ngx/paperless-ngx/pull/1567))
-   Feature: Add MariaDB support [@bckelly1](https://github.com/bckelly1) ([#543](https://github.com/paperless-ngx/paperless-ngx/pull/543))
-   Feature: Simplify IMAP login for UTF-8 [@stumpylog](https://github.com/stumpylog) ([#1492](https://github.com/paperless-ngx/paperless-ngx/pull/1492))
-   Feature: Even better re-do of OCR [@stumpylog](https://github.com/stumpylog) ([#1451](https://github.com/paperless-ngx/paperless-ngx/pull/1451))
-   Feature: document comments [@tim-vogel](https://github.com/tim-vogel) ([#1375](https://github.com/paperless-ngx/paperless-ngx/pull/1375))
-   Adding date suggestions to the documents details view [@Eckii24](https://github.com/Eckii24) ([#1367](https://github.com/paperless-ngx/paperless-ngx/pull/1367))
-   Feature: Event driven consumer [@stumpylog](https://github.com/stumpylog) ([#1421](https://github.com/paperless-ngx/paperless-ngx/pull/1421))
-   Feature: Adds storage paths to re-tagger command [@stumpylog](https://github.com/stumpylog) ([#1446](https://github.com/paperless-ngx/paperless-ngx/pull/1446))
-   Feature: Preserve original filename in metadata [@GwynHannay](https://github.com/GwynHannay) ([#1440](https://github.com/paperless-ngx/paperless-ngx/pull/1440))
-   Handle tags for gmail email accounts [@sisao](https://github.com/sisao) ([#1433](https://github.com/paperless-ngx/paperless-ngx/pull/1433))
-   Update redis image [@tribut](https://github.com/tribut) ([#1436](https://github.com/paperless-ngx/paperless-ngx/pull/1436))
-   PAPERLESS_REDIS may be set via docker secrets [@DennisGaida](https://github.com/DennisGaida) ([#1405](https://github.com/paperless-ngx/paperless-ngx/pull/1405))

### Bug Fixes

-   paperless_cmd.sh: use exec to run supervisord [@lemmi](https://github.com/lemmi) ([#1617](https://github.com/paperless-ngx/paperless-ngx/pull/1617))
-   Fix: Double barcode separation creates empty file [@stumpylog](https://github.com/stumpylog) ([#1596](https://github.com/paperless-ngx/paperless-ngx/pull/1596))
-   Fix: Resolve issue with slow classifier [@stumpylog](https://github.com/stumpylog) ([#1576](https://github.com/paperless-ngx/paperless-ngx/pull/1576))
-   Fix document comments not updating on document navigation [@shamoon](https://github.com/shamoon) ([#1566](https://github.com/paperless-ngx/paperless-ngx/pull/1566))
-   Fix: Include storage paths in document exporter [@shamoon](https://github.com/shamoon) ([#1557](https://github.com/paperless-ngx/paperless-ngx/pull/1557))
-   Chore: Cleanup and validate settings [@stumpylog](https://github.com/stumpylog) ([#1551](https://github.com/paperless-ngx/paperless-ngx/pull/1551))
-   Bugfix: Better gunicorn settings for workers [@stumpylog](https://github.com/stumpylog) ([#1500](https://github.com/paperless-ngx/paperless-ngx/pull/1500))
-   Fix actions button in tasks table [@shamoon](https://github.com/shamoon) ([#1488](https://github.com/paperless-ngx/paperless-ngx/pull/1488))
-   Fix: Add missing filter rule types to SavedViewFilterRule model \& fix migrations [@shamoon](https://github.com/shamoon) ([#1463](https://github.com/paperless-ngx/paperless-ngx/pull/1463))
-   Fix paperless.conf.example typo [@qcasey](https://github.com/qcasey) ([#1460](https://github.com/paperless-ngx/paperless-ngx/pull/1460))
-   Bugfix: Fixes the creation of an archive file, even if noarchive was specified [@stumpylog](https://github.com/stumpylog) ([#1442](https://github.com/paperless-ngx/paperless-ngx/pull/1442))
-   Fix: created_date should not be required [@shamoon](https://github.com/shamoon) ([#1412](https://github.com/paperless-ngx/paperless-ngx/pull/1412))
-   Fix: dev backend testing [@stumpylog](https://github.com/stumpylog) ([#1420](https://github.com/paperless-ngx/paperless-ngx/pull/1420))
-   Bugfix: Catch all exceptions during the task signals [@stumpylog](https://github.com/stumpylog) ([#1387](https://github.com/paperless-ngx/paperless-ngx/pull/1387))
-   Fix: saved view page parameter [@shamoon](https://github.com/shamoon) ([#1376](https://github.com/paperless-ngx/paperless-ngx/pull/1376))
-   Fix: Correct browser unsaved changes warning [@shamoon](https://github.com/shamoon) ([#1369](https://github.com/paperless-ngx/paperless-ngx/pull/1369))
-   Fix: correct date pasting with other formats [@shamoon](https://github.com/shamoon) ([#1370](https://github.com/paperless-ngx/paperless-ngx/pull/1370))
-   Bugfix: Allow webserver bind address to be configured [@stumpylog](https://github.com/stumpylog) ([#1358](https://github.com/paperless-ngx/paperless-ngx/pull/1358))
-   Bugfix: Chain exceptions during exception handling [@stumpylog](https://github.com/stumpylog) ([#1354](https://github.com/paperless-ngx/paperless-ngx/pull/1354))
-   Fix: missing tooltip translation \& filter editor wrapping [@shamoon](https://github.com/shamoon) ([#1305](https://github.com/paperless-ngx/paperless-ngx/pull/1305))
-   Bugfix: Interaction between barcode and directories as tags [@stumpylog](https://github.com/stumpylog) ([#1303](https://github.com/paperless-ngx/paperless-ngx/pull/1303))

### Documentation

-   [Beta] Paperless-ngx v1.9.0 Release Candidate [@stumpylog](https://github.com/stumpylog) ([#1560](https://github.com/paperless-ngx/paperless-ngx/pull/1560))
-   docs/configuration: Fix binary variable defaults [@erikarvstedt](https://github.com/erikarvstedt) ([#1528](https://github.com/paperless-ngx/paperless-ngx/pull/1528))
-   Info about installing on subpath [@viktor-c](https://github.com/viktor-c) ([#1350](https://github.com/paperless-ngx/paperless-ngx/pull/1350))
-   Docs: move scanner \& software recs to GH wiki [@shamoon](https://github.com/shamoon) ([#1482](https://github.com/paperless-ngx/paperless-ngx/pull/1482))
-   Docs: Update mobile scanner section [@tooomm](https://github.com/tooomm) ([#1467](https://github.com/paperless-ngx/paperless-ngx/pull/1467))
-   Adding date suggestions to the documents details view [@Eckii24](https://github.com/Eckii24) ([#1367](https://github.com/paperless-ngx/paperless-ngx/pull/1367))
-   docs: scanners: add Brother ads4700w [@ocelotsloth](https://github.com/ocelotsloth) ([#1450](https://github.com/paperless-ngx/paperless-ngx/pull/1450))
-   Feature: Adds storage paths to re-tagger command [@stumpylog](https://github.com/stumpylog) ([#1446](https://github.com/paperless-ngx/paperless-ngx/pull/1446))
-   Changes to Redis documentation [@Zerteax](https://github.com/Zerteax) ([#1441](https://github.com/paperless-ngx/paperless-ngx/pull/1441))
-   Update scanners.rst [@glassbox-sco](https://github.com/glassbox-sco) ([#1430](https://github.com/paperless-ngx/paperless-ngx/pull/1430))
-   Update scanners.rst [@derlucas](https://github.com/derlucas) ([#1415](https://github.com/paperless-ngx/paperless-ngx/pull/1415))
-   Bugfix: Allow webserver bind address to be configured [@stumpylog](https://github.com/stumpylog) ([#1358](https://github.com/paperless-ngx/paperless-ngx/pull/1358))
-   docs: fix small typo [@tooomm](https://github.com/tooomm) ([#1352](https://github.com/paperless-ngx/paperless-ngx/pull/1352))
-   [Documentation] Add v1.8.0 changelog [@github-actions](https://github.com/github-actions) ([#1298](https://github.com/paperless-ngx/paperless-ngx/pull/1298))

### Maintenance

-   [Beta] Paperless-ngx v1.9.0 Release Candidate [@stumpylog](https://github.com/stumpylog) ([#1560](https://github.com/paperless-ngx/paperless-ngx/pull/1560))
-   paperless_cmd.sh: use exec to run supervisord [@lemmi](https://github.com/lemmi) ([#1617](https://github.com/paperless-ngx/paperless-ngx/pull/1617))
-   Chore: Extended container image cleanup [@stumpylog](https://github.com/stumpylog) ([#1556](https://github.com/paperless-ngx/paperless-ngx/pull/1556))
-   Chore: Smaller library images [@stumpylog](https://github.com/stumpylog) ([#1546](https://github.com/paperless-ngx/paperless-ngx/pull/1546))
-   Bump tj-actions/changed-files from 24 to 29.0.2 [@dependabot](https://github.com/dependabot) ([#1493](https://github.com/paperless-ngx/paperless-ngx/pull/1493))
-   Bugfix: Better gunicorn settings for workers [@stumpylog](https://github.com/stumpylog) ([#1500](https://github.com/paperless-ngx/paperless-ngx/pull/1500))
-   [CI] Fix release drafter issues [@qcasey](https://github.com/qcasey) ([#1301](https://github.com/paperless-ngx/paperless-ngx/pull/1301))
-   Fix: dev backend testing [@stumpylog](https://github.com/stumpylog) ([#1420](https://github.com/paperless-ngx/paperless-ngx/pull/1420))
-   Chore: Exclude dependabot PRs from Project, set status to Needs Review [@qcasey](https://github.com/qcasey) ([#1397](https://github.com/paperless-ngx/paperless-ngx/pull/1397))
-   Chore: Add to label PRs based on and title [@qcasey](https://github.com/qcasey) ([#1396](https://github.com/paperless-ngx/paperless-ngx/pull/1396))
-   Chore: use pre-commit in the Ci workflow [@stumpylog](https://github.com/stumpylog) ([#1362](https://github.com/paperless-ngx/paperless-ngx/pull/1362))
-   Chore: Fixes permissions for image tag cleanup [@stumpylog](https://github.com/stumpylog) ([#1315](https://github.com/paperless-ngx/paperless-ngx/pull/1315))
-   Bump leonsteinhaeuser/project-beta-automations from 1.2.1 to 1.3.0 [@dependabot](https://github.com/dependabot) ([#1328](https://github.com/paperless-ngx/paperless-ngx/pull/1328))
-   Bump tj-actions/changed-files from 23.1 to 24 [@dependabot](https://github.com/dependabot) ([#1329](https://github.com/paperless-ngx/paperless-ngx/pull/1329))
-   Feature: Remove requirements.txt and use pipenv everywhere [@stumpylog](https://github.com/stumpylog) ([#1316](https://github.com/paperless-ngx/paperless-ngx/pull/1316))

### Dependencies

<details>
<summary>34 changes</summary>

-   Bump pikepdf from 5.5.0 to 5.6.1 [@dependabot](https://github.com/dependabot) ([#1537](https://github.com/paperless-ngx/paperless-ngx/pull/1537))
-   Bump black from 22.6.0 to 22.8.0 [@dependabot](https://github.com/dependabot) ([#1539](https://github.com/paperless-ngx/paperless-ngx/pull/1539))
-   Bump tqdm from 4.64.0 to 4.64.1 [@dependabot](https://github.com/dependabot) ([#1540](https://github.com/paperless-ngx/paperless-ngx/pull/1540))
-   Bump pytest from 7.1.2 to 7.1.3 [@dependabot](https://github.com/dependabot) ([#1538](https://github.com/paperless-ngx/paperless-ngx/pull/1538))
-   Bump tj-actions/changed-files from 24 to 29.0.2 [@dependabot](https://github.com/dependabot) ([#1493](https://github.com/paperless-ngx/paperless-ngx/pull/1493))
-   Bump angular packages, jest-preset-angular in src-ui [@dependabot](https://github.com/dependabot) ([#1502](https://github.com/paperless-ngx/paperless-ngx/pull/1502))
-   Bump jest-environment-jsdom from 28.1.3 to 29.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1507](https://github.com/paperless-ngx/paperless-ngx/pull/1507))
-   Bump [@<!---->types/node from 18.6.3 to 18.7.14 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.6.3 to 18.7.14 in /src-ui @dependabot) ([#1506](https://github.com/paperless-ngx/paperless-ngx/pull/1506))
-   Bump [@<!---->angular-builders/jest from 14.0.0 to 14.0.1 in /src-ui @dependabot](https://github.com/<!---->angular-builders/jest from 14.0.0 to 14.0.1 in /src-ui @dependabot) ([#1505](https://github.com/paperless-ngx/paperless-ngx/pull/1505))
-   Bump zone.js from 0.11.7 to 0.11.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#1504](https://github.com/paperless-ngx/paperless-ngx/pull/1504))
-   Bump ngx-color from 8.0.1 to 8.0.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1494](https://github.com/paperless-ngx/paperless-ngx/pull/1494))
-   Bump cypress from 10.3.1 to 10.7.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1496](https://github.com/paperless-ngx/paperless-ngx/pull/1496))
-   Bump [@<!---->cypress/schematic from 2.0.0 to 2.1.1 in /src-ui @dependabot](https://github.com/<!---->cypress/schematic from 2.0.0 to 2.1.1 in /src-ui @dependabot) ([#1495](https://github.com/paperless-ngx/paperless-ngx/pull/1495))
-   Bump [@<!---->popperjs/core from 2.11.5 to 2.11.6 in /src-ui @dependabot](https://github.com/<!---->popperjs/core from 2.11.5 to 2.11.6 in /src-ui @dependabot) ([#1498](https://github.com/paperless-ngx/paperless-ngx/pull/1498))
-   Bump sphinx from 5.0.2 to 5.1.1 [@dependabot](https://github.com/dependabot) ([#1297](https://github.com/paperless-ngx/paperless-ngx/pull/1297))
-   Chore: Bump Python dependencies [@stumpylog](https://github.com/stumpylog) ([#1445](https://github.com/paperless-ngx/paperless-ngx/pull/1445))
-   Chore: Update Python deps [@stumpylog](https://github.com/stumpylog) ([#1391](https://github.com/paperless-ngx/paperless-ngx/pull/1391))
-   Bump watchfiles from 0.15.0 to 0.16.1 [@dependabot](https://github.com/dependabot) ([#1285](https://github.com/paperless-ngx/paperless-ngx/pull/1285))
-   Bump leonsteinhaeuser/project-beta-automations from 1.2.1 to 1.3.0 [@dependabot](https://github.com/dependabot) ([#1328](https://github.com/paperless-ngx/paperless-ngx/pull/1328))
-   Bump tj-actions/changed-files from 23.1 to 24 [@dependabot](https://github.com/dependabot) ([#1329](https://github.com/paperless-ngx/paperless-ngx/pull/1329))
-   Bump cypress from 10.3.0 to 10.3.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1342](https://github.com/paperless-ngx/paperless-ngx/pull/1342))
-   Bump ngx-color from 7.3.3 to 8.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1343](https://github.com/paperless-ngx/paperless-ngx/pull/1343))
-   Bump [@<!---->angular/cli from 14.0.4 to 14.1.0 in /src-ui @dependabot](https://github.com/<!---->angular/cli from 14.0.4 to 14.1.0 in /src-ui @dependabot) ([#1330](https://github.com/paperless-ngx/paperless-ngx/pull/1330))
-   Bump [@<!---->types/node from 18.0.0 to 18.6.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.0.0 to 18.6.3 in /src-ui @dependabot) ([#1341](https://github.com/paperless-ngx/paperless-ngx/pull/1341))
-   Bump jest-preset-angular from 12.1.0 to 12.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1340](https://github.com/paperless-ngx/paperless-ngx/pull/1340))
-   Bump concurrently from 7.2.2 to 7.3.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1326](https://github.com/paperless-ngx/paperless-ngx/pull/1326))
-   Bump ng2-pdf-viewer from 9.0.0 to 9.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1337](https://github.com/paperless-ngx/paperless-ngx/pull/1337))
-   Bump jest-environment-jsdom from 28.1.2 to 28.1.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#1336](https://github.com/paperless-ngx/paperless-ngx/pull/1336))
-   Bump ngx-file-drop from 13.0.0 to 14.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1331](https://github.com/paperless-ngx/paperless-ngx/pull/1331))
-   Bump jest and [@<!---->types/jest in /src-ui @dependabot](https://github.com/<!---->types/jest in /src-ui @dependabot) ([#1333](https://github.com/paperless-ngx/paperless-ngx/pull/1333))
-   Bump bootstrap from 5.1.3 to 5.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1327](https://github.com/paperless-ngx/paperless-ngx/pull/1327))
-   Bump typescript from 4.6.4 to 4.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#1324](https://github.com/paperless-ngx/paperless-ngx/pull/1324))
-   Bump ts-node from 10.8.1 to 10.9.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1325](https://github.com/paperless-ngx/paperless-ngx/pull/1325))
-   Bump rxjs from 7.5.5 to 7.5.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#1323](https://github.com/paperless-ngx/paperless-ngx/pull/1323))
</details>

### All App Changes

-   [Beta] Paperless-ngx v1.9.0 Release Candidate [@stumpylog](https://github.com/stumpylog) ([#1560](https://github.com/paperless-ngx/paperless-ngx/pull/1560))
-   Feature: Faster, less memory barcode handling [@stumpylog](https://github.com/stumpylog) ([#1594](https://github.com/paperless-ngx/paperless-ngx/pull/1594))
-   Fix: Consume directory permissions were not updated [@stumpylog](https://github.com/stumpylog) ([#1605](https://github.com/paperless-ngx/paperless-ngx/pull/1605))
-   Fix: Double barcode separation creates empty file [@stumpylog](https://github.com/stumpylog) ([#1596](https://github.com/paperless-ngx/paperless-ngx/pull/1596))
-   Fix: Parsing Tika documents fails with AttributeError [@stumpylog](https://github.com/stumpylog) ([#1591](https://github.com/paperless-ngx/paperless-ngx/pull/1591))
-   Fix: Resolve issue with slow classifier [@stumpylog](https://github.com/stumpylog) ([#1576](https://github.com/paperless-ngx/paperless-ngx/pull/1576))
-   Feature: Display django-q process names [@stumpylog](https://github.com/stumpylog) ([#1567](https://github.com/paperless-ngx/paperless-ngx/pull/1567))
-   Fix document comments not updating on document navigation [@shamoon](https://github.com/shamoon) ([#1566](https://github.com/paperless-ngx/paperless-ngx/pull/1566))
-   Feature: Add MariaDB support [@bckelly1](https://github.com/bckelly1) ([#543](https://github.com/paperless-ngx/paperless-ngx/pull/543))
-   Fix: Include storage paths in document exporter [@shamoon](https://github.com/shamoon) ([#1557](https://github.com/paperless-ngx/paperless-ngx/pull/1557))
-   Chore: Cleanup and validate settings [@stumpylog](https://github.com/stumpylog) ([#1551](https://github.com/paperless-ngx/paperless-ngx/pull/1551))
-   Bump pikepdf from 5.5.0 to 5.6.1 [@dependabot](https://github.com/dependabot) ([#1537](https://github.com/paperless-ngx/paperless-ngx/pull/1537))
-   Bump black from 22.6.0 to 22.8.0 [@dependabot](https://github.com/dependabot) ([#1539](https://github.com/paperless-ngx/paperless-ngx/pull/1539))
-   Bump tqdm from 4.64.0 to 4.64.1 [@dependabot](https://github.com/dependabot) ([#1540](https://github.com/paperless-ngx/paperless-ngx/pull/1540))
-   Bump pytest from 7.1.2 to 7.1.3 [@dependabot](https://github.com/dependabot) ([#1538](https://github.com/paperless-ngx/paperless-ngx/pull/1538))
-   Bump angular packages, jest-preset-angular in src-ui [@dependabot](https://github.com/dependabot) ([#1502](https://github.com/paperless-ngx/paperless-ngx/pull/1502))
-   Bump jest-environment-jsdom from 28.1.3 to 29.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1507](https://github.com/paperless-ngx/paperless-ngx/pull/1507))
-   Bump [@<!---->types/node from 18.6.3 to 18.7.14 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.6.3 to 18.7.14 in /src-ui @dependabot) ([#1506](https://github.com/paperless-ngx/paperless-ngx/pull/1506))
-   Bump [@<!---->angular-builders/jest from 14.0.0 to 14.0.1 in /src-ui @dependabot](https://github.com/<!---->angular-builders/jest from 14.0.0 to 14.0.1 in /src-ui @dependabot) ([#1505](https://github.com/paperless-ngx/paperless-ngx/pull/1505))
-   Bump zone.js from 0.11.7 to 0.11.8 in /src-ui [@dependabot](https://github.com/dependabot) ([#1504](https://github.com/paperless-ngx/paperless-ngx/pull/1504))
-   Bump ngx-color from 8.0.1 to 8.0.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1494](https://github.com/paperless-ngx/paperless-ngx/pull/1494))
-   Bump cypress from 10.3.1 to 10.7.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1496](https://github.com/paperless-ngx/paperless-ngx/pull/1496))
-   Bump [@<!---->cypress/schematic from 2.0.0 to 2.1.1 in /src-ui @dependabot](https://github.com/<!---->cypress/schematic from 2.0.0 to 2.1.1 in /src-ui @dependabot) ([#1495](https://github.com/paperless-ngx/paperless-ngx/pull/1495))
-   Bump [@<!---->popperjs/core from 2.11.5 to 2.11.6 in /src-ui @dependabot](https://github.com/<!---->popperjs/core from 2.11.5 to 2.11.6 in /src-ui @dependabot) ([#1498](https://github.com/paperless-ngx/paperless-ngx/pull/1498))
-   Feature: Simplify IMAP login for UTF-8 [@stumpylog](https://github.com/stumpylog) ([#1492](https://github.com/paperless-ngx/paperless-ngx/pull/1492))
-   Fix actions button in tasks table [@shamoon](https://github.com/shamoon) ([#1488](https://github.com/paperless-ngx/paperless-ngx/pull/1488))
-   Fix: Add missing filter rule types to SavedViewFilterRule model \& fix migrations [@shamoon](https://github.com/shamoon) ([#1463](https://github.com/paperless-ngx/paperless-ngx/pull/1463))
-   Feature: Even better re-do of OCR [@stumpylog](https://github.com/stumpylog) ([#1451](https://github.com/paperless-ngx/paperless-ngx/pull/1451))
-   Feature: document comments [@tim-vogel](https://github.com/tim-vogel) ([#1375](https://github.com/paperless-ngx/paperless-ngx/pull/1375))
-   Adding date suggestions to the documents details view [@Eckii24](https://github.com/Eckii24) ([#1367](https://github.com/paperless-ngx/paperless-ngx/pull/1367))
-   Bump sphinx from 5.0.2 to 5.1.1 [@dependabot](https://github.com/dependabot) ([#1297](https://github.com/paperless-ngx/paperless-ngx/pull/1297))
-   Feature: Event driven consumer [@stumpylog](https://github.com/stumpylog) ([#1421](https://github.com/paperless-ngx/paperless-ngx/pull/1421))
-   Bugfix: Fixes the creation of an archive file, even if noarchive was specified [@stumpylog](https://github.com/stumpylog) ([#1442](https://github.com/paperless-ngx/paperless-ngx/pull/1442))
-   Feature: Adds storage paths to re-tagger command [@stumpylog](https://github.com/stumpylog) ([#1446](https://github.com/paperless-ngx/paperless-ngx/pull/1446))
-   Feature: Preserve original filename in metadata [@GwynHannay](https://github.com/GwynHannay) ([#1440](https://github.com/paperless-ngx/paperless-ngx/pull/1440))
-   Handle tags for gmail email accounts [@sisao](https://github.com/sisao) ([#1433](https://github.com/paperless-ngx/paperless-ngx/pull/1433))
-   Fix: should not be required [@shamoon](https://github.com/shamoon) ([#1412](https://github.com/paperless-ngx/paperless-ngx/pull/1412))
-   Bugfix: Catch all exceptions during the task signals [@stumpylog](https://github.com/stumpylog) ([#1387](https://github.com/paperless-ngx/paperless-ngx/pull/1387))
-   Fix: saved view page parameter [@shamoon](https://github.com/shamoon) ([#1376](https://github.com/paperless-ngx/paperless-ngx/pull/1376))
-   Fix: Correct browser unsaved changes warning [@shamoon](https://github.com/shamoon) ([#1369](https://github.com/paperless-ngx/paperless-ngx/pull/1369))
-   Fix: correct date pasting with other formats [@shamoon](https://github.com/shamoon) ([#1370](https://github.com/paperless-ngx/paperless-ngx/pull/1370))
-   Chore: use pre-commit in the Ci workflow [@stumpylog](https://github.com/stumpylog) ([#1362](https://github.com/paperless-ngx/paperless-ngx/pull/1362))
-   Bugfix: Chain exceptions during exception handling [@stumpylog](https://github.com/stumpylog) ([#1354](https://github.com/paperless-ngx/paperless-ngx/pull/1354))
-   Bump watchfiles from 0.15.0 to 0.16.1 [@dependabot](https://github.com/dependabot) ([#1285](https://github.com/paperless-ngx/paperless-ngx/pull/1285))
-   Bump cypress from 10.3.0 to 10.3.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1342](https://github.com/paperless-ngx/paperless-ngx/pull/1342))
-   Bump ngx-color from 7.3.3 to 8.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1343](https://github.com/paperless-ngx/paperless-ngx/pull/1343))
-   Bump [@<!---->angular/cli from 14.0.4 to 14.1.0 in /src-ui @dependabot](https://github.com/<!---->angular/cli from 14.0.4 to 14.1.0 in /src-ui @dependabot) ([#1330](https://github.com/paperless-ngx/paperless-ngx/pull/1330))
-   Bump [@<!---->types/node from 18.0.0 to 18.6.3 in /src-ui @dependabot](https://github.com/<!---->types/node from 18.0.0 to 18.6.3 in /src-ui @dependabot) ([#1341](https://github.com/paperless-ngx/paperless-ngx/pull/1341))
-   Bump jest-preset-angular from 12.1.0 to 12.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1340](https://github.com/paperless-ngx/paperless-ngx/pull/1340))
-   Bump concurrently from 7.2.2 to 7.3.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1326](https://github.com/paperless-ngx/paperless-ngx/pull/1326))
-   Bump ng2-pdf-viewer from 9.0.0 to 9.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1337](https://github.com/paperless-ngx/paperless-ngx/pull/1337))
-   Bump jest-environment-jsdom from 28.1.2 to 28.1.3 in /src-ui [@dependabot](https://github.com/dependabot) ([#1336](https://github.com/paperless-ngx/paperless-ngx/pull/1336))
-   Bump ngx-file-drop from 13.0.0 to 14.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1331](https://github.com/paperless-ngx/paperless-ngx/pull/1331))
-   Bump jest and [@<!---->types/jest in /src-ui @dependabot](https://github.com/<!---->types/jest in /src-ui @dependabot) ([#1333](https://github.com/paperless-ngx/paperless-ngx/pull/1333))
-   Bump bootstrap from 5.1.3 to 5.2.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1327](https://github.com/paperless-ngx/paperless-ngx/pull/1327))
-   Bump typescript from 4.6.4 to 4.7.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#1324](https://github.com/paperless-ngx/paperless-ngx/pull/1324))
-   Bump ts-node from 10.8.1 to 10.9.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1325](https://github.com/paperless-ngx/paperless-ngx/pull/1325))
-   Bump rxjs from 7.5.5 to 7.5.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#1323](https://github.com/paperless-ngx/paperless-ngx/pull/1323))
-   Fix: missing tooltip translation \& filter editor wrapping [@shamoon](https://github.com/shamoon) ([#1305](https://github.com/paperless-ngx/paperless-ngx/pull/1305))
-   Feature: Remove requirements.txt and use pipenv everywhere [@stumpylog](https://github.com/stumpylog) ([#1316](https://github.com/paperless-ngx/paperless-ngx/pull/1316))
-   Bugfix: Interaction between barcode and directories as tags [@stumpylog](https://github.com/stumpylog) ([#1303](https://github.com/paperless-ngx/paperless-ngx/pull/1303))

## paperless-ngx 1.8.0

### Features

-   Feature use env vars in pre post scripts [@ziprandom](https://github.com/ziprandom) ([#1154](https://github.com/paperless-ngx/paperless-ngx/pull/1154))
-   frontend task queue [@shamoon](https://github.com/shamoon) ([#1020](https://github.com/paperless-ngx/paperless-ngx/pull/1020))
-   Fearless scikit-learn updates [@stumpylog](https://github.com/stumpylog) ([#1082](https://github.com/paperless-ngx/paperless-ngx/pull/1082))
-   Adds support for Docker secrets [@stumpylog](https://github.com/stumpylog) ([#1034](https://github.com/paperless-ngx/paperless-ngx/pull/1034))
-   make frontend timezone un-aware [@shamoon](https://github.com/shamoon) ([#957](https://github.com/paperless-ngx/paperless-ngx/pull/957))
-   Change document thumbnails to WebP [@stumpylog](https://github.com/stumpylog) ([#1127](https://github.com/paperless-ngx/paperless-ngx/pull/1127))
-   Fork django-q to update dependencies [@stumpylog](https://github.com/stumpylog) ([#1014](https://github.com/paperless-ngx/paperless-ngx/pull/1014))
-   Fix: Rework query params logic [@shamoon](https://github.com/shamoon) ([#1000](https://github.com/paperless-ngx/paperless-ngx/pull/1000))
-   Enhancement: show note on language change and offer reload [@shamoon](https://github.com/shamoon) ([#1030](https://github.com/paperless-ngx/paperless-ngx/pull/1030))
-   Include error information when Redis connection fails [@stumpylog](https://github.com/stumpylog) ([#1016](https://github.com/paperless-ngx/paperless-ngx/pull/1016))
-   frontend settings saved to database [@shamoon](https://github.com/shamoon) ([#919](https://github.com/paperless-ngx/paperless-ngx/pull/919))
-   Add "Created" as additional (optional) parameter for post_documents [@eingemaischt](https://github.com/eingemaischt) ([#965](https://github.com/paperless-ngx/paperless-ngx/pull/965))
-   Convert Changelog to markdown, auto-commit future changelogs [@qcasey](https://github.com/qcasey) ([#935](https://github.com/paperless-ngx/paperless-ngx/pull/935))
-   allow all ASN filtering functions [@shamoon](https://github.com/shamoon) ([#920](https://github.com/paperless-ngx/paperless-ngx/pull/920))
-   gunicorn: Allow IPv6 sockets [@vlcty](https://github.com/vlcty) ([#924](https://github.com/paperless-ngx/paperless-ngx/pull/924))
-   initial app loading indicators [@shamoon](https://github.com/shamoon) ([#899](https://github.com/paperless-ngx/paperless-ngx/pull/899))

### Bug Fixes

-   Fix: dropdown selected items not visible again [@shamoon](https://github.com/shamoon) ([#1261](https://github.com/paperless-ngx/paperless-ngx/pull/1261))
-   [CI] Fix automatic changelog generation on release [@qcasey](https://github.com/qcasey) ([#1249](https://github.com/paperless-ngx/paperless-ngx/pull/1249))
-   Fix: Prevent duplicate api calls on text filtering [@shamoon](https://github.com/shamoon) ([#1133](https://github.com/paperless-ngx/paperless-ngx/pull/1133))
-   make frontend timezone un-aware [@shamoon](https://github.com/shamoon) ([#957](https://github.com/paperless-ngx/paperless-ngx/pull/957))
-   Feature / fix quick toggleable filters [@shamoon](https://github.com/shamoon) ([#1122](https://github.com/paperless-ngx/paperless-ngx/pull/1122))
-   Chore: Manually downgrade reportlab (and update everything else) [@stumpylog](https://github.com/stumpylog) ([#1116](https://github.com/paperless-ngx/paperless-ngx/pull/1116))
-   Bugfix: Don't assume default Docker folders [@stumpylog](https://github.com/stumpylog) ([#1088](https://github.com/paperless-ngx/paperless-ngx/pull/1088))
-   Bugfix: Better sanity check messages [@stumpylog](https://github.com/stumpylog) ([#1049](https://github.com/paperless-ngx/paperless-ngx/pull/1049))
-   Fix vertical margins between pages of pdf viewer [@shamoon](https://github.com/shamoon) ([#1081](https://github.com/paperless-ngx/paperless-ngx/pull/1081))
-   Bugfix: Pass debug setting on to django-q [@stumpylog](https://github.com/stumpylog) ([#1058](https://github.com/paperless-ngx/paperless-ngx/pull/1058))
-   Bugfix: Don't assume the document has a title set [@stumpylog](https://github.com/stumpylog) ([#1057](https://github.com/paperless-ngx/paperless-ngx/pull/1057))
-   Bugfix: Corrects the setting of max pixel size for OCR [@stumpylog](https://github.com/stumpylog) ([#1008](https://github.com/paperless-ngx/paperless-ngx/pull/1008))
-   better date pasting [@shamoon](https://github.com/shamoon) ([#1007](https://github.com/paperless-ngx/paperless-ngx/pull/1007))
-   Enhancement: Alphabetize tags by default [@shamoon](https://github.com/shamoon) ([#1017](https://github.com/paperless-ngx/paperless-ngx/pull/1017))
-   Fix: Rework query params logic [@shamoon](https://github.com/shamoon) ([#1000](https://github.com/paperless-ngx/paperless-ngx/pull/1000))
-   Fix: add translation for some un-translated tooltips [@shamoon](https://github.com/shamoon) ([#995](https://github.com/paperless-ngx/paperless-ngx/pull/995))
-   Change npm --no-optional to --omit=optional [@shamoon](https://github.com/shamoon) ([#986](https://github.com/paperless-ngx/paperless-ngx/pull/986))
-   Add `myst-parser` to fix readthedocs [@qcasey](https://github.com/qcasey) ([#982](https://github.com/paperless-ngx/paperless-ngx/pull/982))
-   Fix: Title is changed after switching doc quickly [@shamoon](https://github.com/shamoon) ([#979](https://github.com/paperless-ngx/paperless-ngx/pull/979))
-   Fix: warn when closing a document with unsaved changes due to max open docs [@shamoon](https://github.com/shamoon) ([#956](https://github.com/paperless-ngx/paperless-ngx/pull/956))
-   Bugfix: Adds configurable intoify debounce time [@stumpylog](https://github.com/stumpylog) ([#953](https://github.com/paperless-ngx/paperless-ngx/pull/953))
-   Bugfix: Fixes document filename date off by 1 issue [@stumpylog](https://github.com/stumpylog) ([#942](https://github.com/paperless-ngx/paperless-ngx/pull/942))
-   fixes #<!---->949: change to MIME detection for files [@gador](https://github.com/gador) ([#962](https://github.com/paperless-ngx/paperless-ngx/pull/962))
-   docs: fix some typos [@Berjou](https://github.com/Berjou) ([#948](https://github.com/paperless-ngx/paperless-ngx/pull/948))
-   [Docs] Fix 2 small typos [@tooomm](https://github.com/tooomm) ([#946](https://github.com/paperless-ngx/paperless-ngx/pull/946))
-   [Readme] Fix typo [@tooomm](https://github.com/tooomm) ([#941](https://github.com/paperless-ngx/paperless-ngx/pull/941))
-   Fix: management pages plurals incorrect in other languages [@shamoon](https://github.com/shamoon) ([#939](https://github.com/paperless-ngx/paperless-ngx/pull/939))
-   Fix: v1.7.1 frontend visual fixes [@shamoon](https://github.com/shamoon) ([#933](https://github.com/paperless-ngx/paperless-ngx/pull/933))
-   Fix: unassigned query params ignored [@shamoon](https://github.com/shamoon) ([#930](https://github.com/paperless-ngx/paperless-ngx/pull/930))
-   Fix: allow commas in non-multi rules query params [@shamoon](https://github.com/shamoon) ([#923](https://github.com/paperless-ngx/paperless-ngx/pull/923))
-   Fix: Include version in export for better error messages [@stumpylog](https://github.com/stumpylog) ([#883](https://github.com/paperless-ngx/paperless-ngx/pull/883))
-   Bugfix: Superuser Management Won't Reset Password [@stumpylog](https://github.com/stumpylog) ([#903](https://github.com/paperless-ngx/paperless-ngx/pull/903))
-   Fix Ignore Date Parsing [@stumpylog](https://github.com/stumpylog) ([#721](https://github.com/paperless-ngx/paperless-ngx/pull/721))

### Documentation

-   Feature use env vars in pre post scripts [@ziprandom](https://github.com/ziprandom) ([#1154](https://github.com/paperless-ngx/paperless-ngx/pull/1154))
-   Add `myst-parser` to fix readthedocs [@qcasey](https://github.com/qcasey) ([#982](https://github.com/paperless-ngx/paperless-ngx/pull/982))
-   Add "Created" as additional (optional) parameter for post_documents [@eingemaischt](https://github.com/eingemaischt) ([#965](https://github.com/paperless-ngx/paperless-ngx/pull/965))
-   Bugfix: Adds configurable intoify debounce time [@stumpylog](https://github.com/stumpylog) ([#953](https://github.com/paperless-ngx/paperless-ngx/pull/953))
-   docs: fix some typos [@Berjou](https://github.com/Berjou) ([#948](https://github.com/paperless-ngx/paperless-ngx/pull/948))
-   [Docs] Fix 2 small typos [@tooomm](https://github.com/tooomm) ([#946](https://github.com/paperless-ngx/paperless-ngx/pull/946))
-   Convert Changelog to markdown, auto-commit future changelogs [@qcasey](https://github.com/qcasey) ([#935](https://github.com/paperless-ngx/paperless-ngx/pull/935))
-   [Readme] Fix typo [@tooomm](https://github.com/tooomm) ([#941](https://github.com/paperless-ngx/paperless-ngx/pull/941))

### Maintenance

-   Adds support for Docker secrets [@stumpylog](https://github.com/stumpylog) ([#1034](https://github.com/paperless-ngx/paperless-ngx/pull/1034))
-   Bugfix: Don't assume default Docker folders [@stumpylog](https://github.com/stumpylog) ([#1088](https://github.com/paperless-ngx/paperless-ngx/pull/1088))
-   Include error information when Redis connection fails [@stumpylog](https://github.com/stumpylog) ([#1016](https://github.com/paperless-ngx/paperless-ngx/pull/1016))
-   Fix: add translation for some un-translated tooltips [@shamoon](https://github.com/shamoon) ([#995](https://github.com/paperless-ngx/paperless-ngx/pull/995))
-   gunicorn: Allow IPv6 sockets [@vlcty](https://github.com/vlcty) ([#924](https://github.com/paperless-ngx/paperless-ngx/pull/924))

### Dependencies

<details>
<summary>34 changes</summary>

-   Fearless scikit-learn updates [@stumpylog](https://github.com/stumpylog) ([#1082](https://github.com/paperless-ngx/paperless-ngx/pull/1082))
-   Bump pillow from 9.1.1 to 9.2.0 [@dependabot](https://github.com/dependabot) ([#1193](https://github.com/paperless-ngx/paperless-ngx/pull/1193))
-   Bump watchdog from 2.1.8 to 2.1.9 [@dependabot](https://github.com/dependabot) ([#1132](https://github.com/paperless-ngx/paperless-ngx/pull/1132))
-   Bump scikit-learn from 1.0.2 to 1.1.1 [@dependabot](https://github.com/dependabot) ([#992](https://github.com/paperless-ngx/paperless-ngx/pull/992))
-   Bump setuptools from 62.3.3 to 62.6.0 [@dependabot](https://github.com/dependabot) ([#1150](https://github.com/paperless-ngx/paperless-ngx/pull/1150))
-   Bump django-filter from 21.1 to 22.1 [@dependabot](https://github.com/dependabot) ([#1191](https://github.com/paperless-ngx/paperless-ngx/pull/1191))
-   Bump actions/setup-python from 3 to 4 [@dependabot](https://github.com/dependabot) ([#1176](https://github.com/paperless-ngx/paperless-ngx/pull/1176))
-   Bump sphinx from 4.5.0 to 5.0.2 [@dependabot](https://github.com/dependabot) ([#1151](https://github.com/paperless-ngx/paperless-ngx/pull/1151))
-   Bump docker/metadata-action from 3 to 4 [@dependabot](https://github.com/dependabot) ([#1178](https://github.com/paperless-ngx/paperless-ngx/pull/1178))
-   Bump tj-actions/changed-files from 22.1 to 23.1 [@dependabot](https://github.com/dependabot) ([#1179](https://github.com/paperless-ngx/paperless-ngx/pull/1179))
-   Bump @<!---->angular/cli from 13.3.7 to 14.0.4 in /src-ui [@dependabot](https://github.com/dependabot) ([#1177](https://github.com/paperless-ngx/paperless-ngx/pull/1177))
-   Bump cypress from 10.0.1 to 10.3.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1187](https://github.com/paperless-ngx/paperless-ngx/pull/1187))
-   Bump zone.js from 0.11.5 to 0.11.6 in /src-ui [@dependabot](https://github.com/dependabot) ([#1185](https://github.com/paperless-ngx/paperless-ngx/pull/1185))
-   Bump ts-node from 10.8.0 to 10.8.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1184](https://github.com/paperless-ngx/paperless-ngx/pull/1184))
-   Bump jest-environment-jsdom from 28.1.0 to 28.1.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1175](https://github.com/paperless-ngx/paperless-ngx/pull/1175))
-   Bump @<!---->types/node from 17.0.38 to 18.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1183](https://github.com/paperless-ngx/paperless-ngx/pull/1183))
-   Bump concurrently from 7.2.1 to 7.2.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1181](https://github.com/paperless-ngx/paperless-ngx/pull/1181))
-   Bump jest-preset-angular from 12.0.1 to 12.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1182](https://github.com/paperless-ngx/paperless-ngx/pull/1182))
-   Bump jest and @<!---->types/jest in /src-ui [@dependabot](https://github.com/dependabot) ([#1180](https://github.com/paperless-ngx/paperless-ngx/pull/1180))
-   Bump whitenoise from 6.1.0 to 6.2.0 [@dependabot](https://github.com/dependabot) ([#1103](https://github.com/paperless-ngx/paperless-ngx/pull/1103))
-   Bump cypress from 9.6.1 to 10.0.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1083](https://github.com/paperless-ngx/paperless-ngx/pull/1083))
-   Bump docker/setup-qemu-action from 1 to 2 [@dependabot](https://github.com/dependabot) ([#1065](https://github.com/paperless-ngx/paperless-ngx/pull/1065))
-   Bump docker/setup-buildx-action from 1 to 2 [@dependabot](https://github.com/dependabot) ([#1064](https://github.com/paperless-ngx/paperless-ngx/pull/1064))
-   Bump docker/build-push-action from 2 to 3 [@dependabot](https://github.com/dependabot) ([#1063](https://github.com/paperless-ngx/paperless-ngx/pull/1063))
-   Bump @<!---->cypress/schematic from 1.7.0 to 2.0.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1075](https://github.com/paperless-ngx/paperless-ngx/pull/1075))
-   Bump tj-actions/changed-files from 19 to 22.1 [@dependabot](https://github.com/dependabot) ([#1062](https://github.com/paperless-ngx/paperless-ngx/pull/1062))
-   Bump concurrently from 7.1.0 to 7.2.1 in /src-ui [@dependabot](https://github.com/dependabot) ([#1073](https://github.com/paperless-ngx/paperless-ngx/pull/1073))
-   Bump @<!---->types/jest from 27.4.1 to 27.5.2 in /src-ui [@dependabot](https://github.com/dependabot) ([#1074](https://github.com/paperless-ngx/paperless-ngx/pull/1074))
-   Bump ts-node from 10.7.0 to 10.8.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1070](https://github.com/paperless-ngx/paperless-ngx/pull/1070))
-   Bump jest from 28.0.3 to 28.1.0 in /src-ui [@dependabot](https://github.com/dependabot) ([#1071](https://github.com/paperless-ngx/paperless-ngx/pull/1071))
-   Chore: npm package updates 22-06-01 [@shamoon](https://github.com/shamoon) ([#1069](https://github.com/paperless-ngx/paperless-ngx/pull/1069))
-   Bump docker/login-action from 1 to 2 [@dependabot](https://github.com/dependabot) ([#1061](https://github.com/paperless-ngx/paperless-ngx/pull/1061))
-   Chore: Manually update dependencies [@stumpylog](https://github.com/stumpylog) ([#1013](https://github.com/paperless-ngx/paperless-ngx/pull/1013))
-   Chore: Manually update all Python dependencies [@stumpylog](https://github.com/stumpylog) ([#973](https://github.com/paperless-ngx/paperless-ngx/pull/973))
</details>

## paperless-ngx 1.7.1

### Features

-   (chore) Runs pyupgrade to Python 3.8+ [@stumpylog](https://github.com/stumpylog) ([#890](https://github.com/paperless-ngx/paperless-ngx/pull/890))
-   Dockerfile Organization \& Enhancements [@stumpylog](https://github.com/stumpylog) ([#888](https://github.com/paperless-ngx/paperless-ngx/pull/888))
-   mobile friendlier manage pages [@shamoon](https://github.com/shamoon) ([#873](https://github.com/paperless-ngx/paperless-ngx/pull/873))
-   Use semver for release process [@stumpylog](https://github.com/stumpylog) ([#851](https://github.com/paperless-ngx/paperless-ngx/pull/851))
-   Enable Docker Hub push [@stumpylog](https://github.com/stumpylog) ([#828](https://github.com/paperless-ngx/paperless-ngx/pull/828))
-   Feature barcode tiff support [@gador](https://github.com/gador) ([#766](https://github.com/paperless-ngx/paperless-ngx/pull/766))
-   Updates GHA workflow to rebuild intermediate images on changes [@stumpylog](https://github.com/stumpylog) ([#820](https://github.com/paperless-ngx/paperless-ngx/pull/820))
-   Adds simple Python to wait for Redis broker to be ready [@stumpylog](https://github.com/stumpylog) ([#788](https://github.com/paperless-ngx/paperless-ngx/pull/788))
-   Update GHA workflow to build all Docker images [@stumpylog](https://github.com/stumpylog) ([#761](https://github.com/paperless-ngx/paperless-ngx/pull/761))

### Bug Fixes

-   Feature / fix saved view \& sort field query params [@shamoon](https://github.com/shamoon) ([#881](https://github.com/paperless-ngx/paperless-ngx/pull/881))
-   Mobile friendlier manage pages [@shamoon](https://github.com/shamoon) ([#873](https://github.com/paperless-ngx/paperless-ngx/pull/873))
-   Add timeout to healthcheck [@shamoon](https://github.com/shamoon) ([#880](https://github.com/paperless-ngx/paperless-ngx/pull/880))
-   Always accept yyyy-mm-dd date inputs [@shamoon](https://github.com/shamoon) ([#864](https://github.com/paperless-ngx/paperless-ngx/pull/864))
-   Fix local Docker image building [@stumpylog](https://github.com/stumpylog) ([#849](https://github.com/paperless-ngx/paperless-ngx/pull/849))
-   Fix: show errors on invalid date input [@shamoon](https://github.com/shamoon) ([#862](https://github.com/paperless-ngx/paperless-ngx/pull/862))
-   Fix: Older dates do not display on frontend [@shamoon](https://github.com/shamoon) ([#852](https://github.com/paperless-ngx/paperless-ngx/pull/852))
-   Fixes IMAP UTF8 Authentication [@stumpylog](https://github.com/stumpylog) ([#725](https://github.com/paperless-ngx/paperless-ngx/pull/725))
-   Fix password field remains visible [@shamoon](https://github.com/shamoon) ([#840](https://github.com/paperless-ngx/paperless-ngx/pull/840))
-   Fixes Pillow build for armv7 [@stumpylog](https://github.com/stumpylog) ([#815](https://github.com/paperless-ngx/paperless-ngx/pull/815))
-   Update frontend localization source file [@shamoon](https://github.com/shamoon) ([#814](https://github.com/paperless-ngx/paperless-ngx/pull/814))
-   Fix install script extra OCR languages format [@stumpylog](https://github.com/stumpylog) ([#777](https://github.com/paperless-ngx/paperless-ngx/pull/777))

### Documentation

-   Use semver for release process [@stumpylog](https://github.com/stumpylog) ([#851](https://github.com/paperless-ngx/paperless-ngx/pull/851))
-   Deployment: Consolidate tika compose files [@qcasey](https://github.com/qcasey) ([#866](https://github.com/paperless-ngx/paperless-ngx/pull/866))
-   Fix local Docker image building [@stumpylog](https://github.com/stumpylog) ([#849](https://github.com/paperless-ngx/paperless-ngx/pull/849))

### Maintenance

-   Dockerfile Organization \& Enhancements [@stumpylog](https://github.com/stumpylog) ([#888](https://github.com/paperless-ngx/paperless-ngx/pull/888))
-   Add timeout to healthcheck [@shamoon](https://github.com/shamoon) ([#880](https://github.com/paperless-ngx/paperless-ngx/pull/880))
-   Use semver for release process [@stumpylog](https://github.com/stumpylog) ([#851](https://github.com/paperless-ngx/paperless-ngx/pull/851))
-   Deployment: Consolidate tika compose files [@qcasey](https://github.com/qcasey) ([#866](https://github.com/paperless-ngx/paperless-ngx/pull/866))
-   Fixes Pillow build for armv7 [@stumpylog](https://github.com/stumpylog) ([#815](https://github.com/paperless-ngx/paperless-ngx/pull/815))
-   Update frontend localization source file [@shamoon](https://github.com/shamoon) ([#814](https://github.com/paperless-ngx/paperless-ngx/pull/814))
-   Fix install script extra OCR languages format [@stumpylog](https://github.com/stumpylog) ([#777](https://github.com/paperless-ngx/paperless-ngx/pull/777))
-   Adds simple Python to wait for Redis broker to be ready [@stumpylog](https://github.com/stumpylog) ([#788](https://github.com/paperless-ngx/paperless-ngx/pull/788))

### Dependencies

<details>
<summary>15 changes</summary>

-   Bump tj-actions/changed-files from 18.7 to 19 @dependabot ([#830](https://github.com/paperless-ngx/paperless-ngx/pull/830))
-   Bump asgiref from 3.5.0 to 3.5.1 @dependabot ([#867](https://github.com/paperless-ngx/paperless-ngx/pull/867))
-   Bump jest from 27.5.1 to 28.0.3 in /src-ui @dependabot ([#860](https://github.com/paperless-ngx/paperless-ngx/pull/860))
-   Bump @<!---->ng-bootstrap/ng-bootstrap from 12.1.0 to 12.1.1 in /src-ui @dependabot ([#861](https://github.com/paperless-ngx/paperless-ngx/pull/861))
-   Bump @<!---->types/node from 17.0.27 to 17.0.29 in /src-ui @dependabot ([#833](https://github.com/paperless-ngx/paperless-ngx/pull/833))
-   Bump @<!---->ng-bootstrap/ng-bootstrap from 12.0.2 to 12.1.0 in /src-ui @dependabot ([#834](https://github.com/paperless-ngx/paperless-ngx/pull/834))
-   Bump pytest from 7.1.1 to 7.1.2 @dependabot ([#806](https://github.com/paperless-ngx/paperless-ngx/pull/806))
-   Bump github/codeql-action from 1 to 2 @dependabot ([#792](https://github.com/paperless-ngx/paperless-ngx/pull/792))
-   Bump imap-tools from 0.53.0 to 0.54.0 @dependabot ([#758](https://github.com/paperless-ngx/paperless-ngx/pull/758))
-   Bump ocrmypdf from 13.4.2 to 13.4.3 @dependabot ([#757](https://github.com/paperless-ngx/paperless-ngx/pull/757))
-   Bump importlib-resources from 5.6.0 to 5.7.1 @dependabot ([#756](https://github.com/paperless-ngx/paperless-ngx/pull/756))
-   Bump tox from 3.24.5 to 3.25.0 @dependabot ([#692](https://github.com/paperless-ngx/paperless-ngx/pull/692))
-   Bump cypress from 9.5.3 to 9.6.0 in /src-ui @dependabot ([#800](https://github.com/paperless-ngx/paperless-ngx/pull/800))
-   Bump angular \& tools to 13.3.4 or 13.3.3 [@shamoon](https://github.com/shamoon) ([#799](https://github.com/paperless-ngx/paperless-ngx/pull/799))
-   Bump concurrently from 7.0.0 to 7.1.0 in /src-ui @dependabot ([#797](https://github.com/paperless-ngx/paperless-ngx/pull/797))
</details>

## paperless-ngx 1.7.0

### Breaking Changes

-   `PAPERLESS_URL` is now required when using a reverse proxy. See
    [#674](https://github.com/paperless-ngx/paperless-ngx/pull/674).

### Features

-   Allow setting more than one tag in mail rules
    [@jonasc](https://github.com/jonasc) ([#270](https://github.com/paperless-ngx/paperless-ngx/pull/270))
-   Global drag'n'drop [@shamoon](https://github.com/shamoon)
    ([#283](https://github.com/paperless-ngx/paperless-ngx/pull/283))
-   Fix: download buttons should disable while waiting
    [@shamoon](https://github.com/shamoon) ([#630](https://github.com/paperless-ngx/paperless-ngx/pull/630))
-   Update checker [@shamoon](https://github.com/shamoon) ([#591](https://github.com/paperless-ngx/paperless-ngx/pull/591))
-   Show prompt on password-protected pdfs
    [@shamoon](https://github.com/shamoon) ([#564](https://github.com/paperless-ngx/paperless-ngx/pull/564))
-   Filtering query params aka browser navigation for filtering
    [@shamoon](https://github.com/shamoon) ([#540](https://github.com/paperless-ngx/paperless-ngx/pull/540))
-   Clickable tags in dashboard widgets
    [@shamoon](https://github.com/shamoon) ([#515](https://github.com/paperless-ngx/paperless-ngx/pull/515))
-   Add bottom pagination [@shamoon](https://github.com/shamoon)
    ([#372](https://github.com/paperless-ngx/paperless-ngx/pull/372))
-   Feature barcode splitter [@gador](https://github.com/gador)
    ([#532](https://github.com/paperless-ngx/paperless-ngx/pull/532))
-   App loading screen [@shamoon](https://github.com/shamoon) ([#298](https://github.com/paperless-ngx/paperless-ngx/pull/298))
-   Use progress bar for delayed buttons
    [@shamoon](https://github.com/shamoon) ([#415](https://github.com/paperless-ngx/paperless-ngx/pull/415))
-   Add minimum length for documents text filter
    [@shamoon](https://github.com/shamoon) ([#401](https://github.com/paperless-ngx/paperless-ngx/pull/401))
-   Added nav buttons in the document detail view
    [@GruberViktor](https://github.com/gruberviktor) ([#273](https://github.com/paperless-ngx/paperless-ngx/pull/273))
-   Improve date keyboard input [@shamoon](https://github.com/shamoon)
    ([#253](https://github.com/paperless-ngx/paperless-ngx/pull/253))
-   Color theming [@shamoon](https://github.com/shamoon) ([#243](https://github.com/paperless-ngx/paperless-ngx/pull/243))
-   Parse dates when entered without separators
    [@GruberViktor](https://github.com/gruberviktor) ([#250](https://github.com/paperless-ngx/paperless-ngx/pull/250))

### Bug Fixes

-   Add "localhost" to ALLOWED_HOSTS
    [@gador](https://github.com/gador) ([#700](https://github.com/paperless-ngx/paperless-ngx/pull/700))
-   Fix: scanners table [@qcasey](https://github.com/qcasey) ([#690](https://github.com/paperless-ngx/paperless-ngx/pull/690))
-   Adds wait for file before consuming
    [@stumpylog](https://github.com/stumpylog) ([#483](https://github.com/paperless-ngx/paperless-ngx/pull/483))
-   Fix: frontend document editing erases time data
    [@shamoon](https://github.com/shamoon) ([#654](https://github.com/paperless-ngx/paperless-ngx/pull/654))
-   Increase length of SavedViewFilterRule
    [@stumpylog](https://github.com/stumpylog) ([#612](https://github.com/paperless-ngx/paperless-ngx/pull/612))
-   Fixes attachment filename matching during mail fetching
    [@stumpylog](https://github.com/stumpylog) ([#680](https://github.com/paperless-ngx/paperless-ngx/pull/680))
-   Add `PAPERLESS_URL` env variable & CSRF var
    [@shamoon](https://github.com/shamoon) ([#674](https://github.com/paperless-ngx/paperless-ngx/discussions/674))
-   Fix: download buttons should disable while waiting
    [@shamoon](https://github.com/shamoon) ([#630](https://github.com/paperless-ngx/paperless-ngx/pull/630))
-   Fixes downloaded filename, add more consumer ignore settings
    [@stumpylog](https://github.com/stumpylog) ([#599](https://github.com/paperless-ngx/paperless-ngx/pull/599))
-   FIX BUG: case-sensitive matching was not possible
    [@danielBreitlauch](https://github.com/danielbreitlauch) ([#594](https://github.com/paperless-ngx/paperless-ngx/pull/594))
-   Uses shutil.move instead of rename
    [@gador](https://github.com/gador) ([#617](https://github.com/paperless-ngx/paperless-ngx/pull/617))
-   Fix npm deps 01.02.22 2 [@shamoon](https://github.com/shamoon)
    ([#610](https://github.com/paperless-ngx/paperless-ngx/discussions/610))
-   Fix npm dependencies 01.02.22
    [@shamoon](https://github.com/shamoon) ([#600](https://github.com/paperless-ngx/paperless-ngx/pull/600))
-   Fix issue 416: implement `PAPERLESS_OCR_MAX_IMAGE_PIXELS`
    [@hacker-h](https://github.com/hacker-h) ([#441](https://github.com/paperless-ngx/paperless-ngx/pull/441))
-   Fix: exclude cypress from build in Dockerfile
    [@FrankStrieter](https://github.com/FrankStrieter) ([#526](https://github.com/paperless-ngx/paperless-ngx/pull/526))
-   Corrections to pass pre-commit hooks
    [@schnuffle](https://github.com/schnuffle) ([#454](https://github.com/paperless-ngx/paperless-ngx/pull/454))
-   Fix 311 unable to click checkboxes in document list
    [@shamoon](https://github.com/shamoon) ([#313](https://github.com/paperless-ngx/paperless-ngx/pull/313))
-   Fix imap tools bug [@stumpylog](https://github.com/stumpylog)
    ([#393](https://github.com/paperless-ngx/paperless-ngx/pull/393))
-   Fix filterable dropdown buttons aren't translated
    [@shamoon](https://github.com/shamoon) ([#366](https://github.com/paperless-ngx/paperless-ngx/pull/366))
-   Fix 224: "Auto-detected date is day before receipt date"
    [@a17t](https://github.com/a17t) ([#246](https://github.com/paperless-ngx/paperless-ngx/pull/246))
-   Fix minor sphinx errors [@shamoon](https://github.com/shamoon)
    ([#322](https://github.com/paperless-ngx/paperless-ngx/pull/322))
-   Fix page links hidden [@shamoon](https://github.com/shamoon)
    ([#314](https://github.com/paperless-ngx/paperless-ngx/pull/314))
-   Fix: Include excluded items in dropdown count
    [@shamoon](https://github.com/shamoon) ([#263](https://github.com/paperless-ngx/paperless-ngx/pull/263))

### Translation

-   [@miku323](https://github.com/miku323) contributed to Slovenian
    translation
-   [@FaintGhost](https://github.com/FaintGhost) contributed to Chinese
    Simplified translation
-   [@DarkoBG79](https://github.com/DarkoBG79) contributed to Serbian
    translation
-   [Kemal Secer](https://crowdin.com/profile/kemal.secer) contributed
    to Turkish translation
-   [@Prominence](https://github.com/Prominence) contributed to
    Belarusian translation

### Documentation

-   Fix: scanners table [@qcasey](https://github.com/qcasey) ([#690](https://github.com/paperless-ngx/paperless-ngx/pull/690))
-   Add `PAPERLESS_URL` env variable & CSRF var
    [@shamoon](https://github.com/shamoon) ([#674](https://github.com/paperless-ngx/paperless-ngx/pull/674))
-   Fixes downloaded filename, add more consumer ignore settings
    [@stumpylog](https://github.com/stumpylog) ([#599](https://github.com/paperless-ngx/paperless-ngx/pull/599))
-   Fix issue 416: implement `PAPERLESS_OCR_MAX_IMAGE_PIXELS`
    [@hacker-h](https://github.com/hacker-h) ([#441](https://github.com/paperless-ngx/paperless-ngx/pull/441))
-   Fix minor sphinx errors [@shamoon](https://github.com/shamoon)
    ([#322](https://github.com/paperless-ngx/paperless-ngx/pull/322))

### Maintenance

-   Add `PAPERLESS_URL` env variable & CSRF var
    [@shamoon](https://github.com/shamoon) ([#674](https://github.com/paperless-ngx/paperless-ngx/pull/674))
-   Chore: Implement release-drafter action for Changelogs
    [@qcasey](https://github.com/qcasey) ([#669](https://github.com/paperless-ngx/paperless-ngx/pull/669))
-   Chore: Add CODEOWNERS [@qcasey](https://github.com/qcasey) ([#667](https://github.com/paperless-ngx/paperless-ngx/pull/667))
-   Support docker-compose v2 in install
    [@stumpylog](https://github.com/stumpylog) ([#611](https://github.com/paperless-ngx/paperless-ngx/pull/611))
-   Add Belarusian localization [@shamoon](https://github.com/shamoon)
    ([#588](https://github.com/paperless-ngx/paperless-ngx/pull/588))
-   Add Turkish localization [@shamoon](https://github.com/shamoon)
    ([#536](https://github.com/paperless-ngx/paperless-ngx/pull/536))
-   Add Serbian localization [@shamoon](https://github.com/shamoon)
    ([#504](https://github.com/paperless-ngx/paperless-ngx/pull/504))
-   Create PULL_REQUEST_TEMPLATE.md
    [@shamoon](https://github.com/shamoon) ([#304](https://github.com/paperless-ngx/paperless-ngx/pull/304))
-   Add Chinese localization [@shamoon](https://github.com/shamoon)
    ([#247](https://github.com/paperless-ngx/paperless-ngx/pull/247))
-   Add Slovenian language for frontend
    [@shamoon](https://github.com/shamoon) ([#315](https://github.com/paperless-ngx/paperless-ngx/pull/315))

## paperless-ngx 1.6.0

This is the first release of the revived paperless-ngx project 🎉. Thank
you to everyone on the paperless-ngx team for your initiative and
excellent teamwork!

Version 1.6.0 merges several pending PRs from jonaswinkler's repo and
includes new feature updates and bug fixes. Major backend and UI changes
include:

-   Updated docs, scripts, CI, and containers to paperless-ngx.
-   Updated Python and Angular dependencies.
-   Dropped support for Python 3.7.
-   Dropped support for Ansible playbooks (thanks
    [@slankes](https://github.com/slankes) [#109](https://github.com/paperless-ngx/paperless-ngx/pull/109)). If someone would
    like to continue supporting them, please see our [ansible
    repo](https://github.com/paperless-ngx/paperless-ngx-ansible).
-   Python code is now required to use Black formatting (thanks
    [@kpj](https://github.com/kpj) [#168](https://github.com/paperless-ngx/paperless-ngx/pull/168)).
-   [@tribut](https://github.com/tribut) added support for a custom SSO
    logout redirect ([jonaswinkler\#1258](https://github.com/jonaswinkler/paperless-ng/pull/1258)). See
    `PAPERLESS_LOGOUT_REDIRECT_URL`.
-   [@shamoon](https://github.com/shamoon) added a loading indicator
    when document list is reloading ([jonaswinkler\#1297](https://github.com/jonaswinkler/paperless-ng/pull/1297)).
-   [@shamoon](https://github.com/shamoon) improved the PDF viewer on
    mobile ([#2](https://github.com/paperless-ngx/paperless-ngx/pull/2)).
-   [@shamoon](https://github.com/shamoon) added 'any' / 'all' and
    'not' filtering with tags ([#10](https://github.com/paperless-ngx/paperless-ngx/pull/10)).
-   [@shamoon](https://github.com/shamoon) added warnings for unsaved
    changes, with smart edit buttons ([#13](https://github.com/paperless-ngx/paperless-ngx/pull/13)).
-   [@benjaminfrank](https://github.com/benjaminfrank) enabled a
    non-root access to port 80 via systemd ([#18](https://github.com/paperless-ngx/paperless-ngx/pull/18)).
-   [@tribut](https://github.com/tribut) added simple "delete to
    trash" functionality ([#24](https://github.com/paperless-ngx/paperless-ngx/pull/24)). See `PAPERLESS_TRASH_DIR`.
-   [@amenk](https://github.com/amenk) fixed the search box overlay
    menu on mobile ([#32](https://github.com/paperless-ngx/paperless-ngx/pull/32)).
-   [@dblitt](https://github.com/dblitt) updated the login form to not
    auto-capitalize usernames ([#36](https://github.com/paperless-ngx/paperless-ngx/pull/36)).
-   [@evilsidekick293](https://github.com/evilsidekick293) made the
    worker timeout configurable ([#37](https://github.com/paperless-ngx/paperless-ngx/pull/37)). See `PAPERLESS_WORKER_TIMEOUT`.
-   [@Nicarim](https://github.com/Nicarim) fixed downloads of UTF-8
    formatted documents in Firefox ([#56](https://github.com/paperless-ngx/paperless-ngx/pull/56)).
-   [@mweimerskirch](https://github.com/mweimerskirch) sorted the
    language dropdown by locale ([#78](https://github.com/paperless-ngx/paperless-ngx/issues/78)).
-   [@mweimerskirch](https://github.com/mweimerskirch) enabled the
    Czech ([#83](https://github.com/paperless-ngx/paperless-ngx/pull/83)) and Danish ([#84](https://github.com/paperless-ngx/paperless-ngx/pull/84)) translations.
-   [@cschmatzler](https://github.com/cschmatzler) enabled specifying
    the webserver port ([#124](https://github.com/paperless-ngx/paperless-ngx/pull/124)). See `PAPERLESS_PORT`.
-   [@muellermartin](https://github.com/muellermartin) fixed an error
    when uploading transparent PNGs ([#133](https://github.com/paperless-ngx/paperless-ngx/pull/133)).
-   [@shamoon](https://github.com/shamoon) created a slick new logo
    ([#165](https://github.com/paperless-ngx/paperless-ngx/pull/165)).
-   [@tim-vogel](https://github.com/tim-vogel) fixed exports missing
    groups ([#193](https://github.com/paperless-ngx/paperless-ngx/pull/193)).

Known issues:

-   1.6.0 included a malformed package-lock.json, as a result users who
    want to build the docker image themselves need to change line 6 of
    the `Dockerfile` to
    `RUN npm update npm -g && npm install --legacy-peer-deps`.

Thank you to the following people for their documentation updates,
fixes, and comprehensive testing:

[@m0veax](https://github.com/m0veax),
[@a17t](https://github.com/a17t),
[@fignew](https://github.com/fignew),
[@muued](https://github.com/muued),
[@bauerj](https://github.com/bauerj),
[@isigmund](https://github.com/isigmund),
[@denilsonsa](https://github.com/denilsonsa),
[@mweimerskirch](https://github.com/mweimerskirch),
[@alexander-bauer](https://github.com/alexander-bauer),
[@apeltzer](https://github.com/apeltzer),
[@tribut](https://github.com/tribut),
[@yschroeder](https://github.com/yschroeder),
[@gador](https://github.com/gador),
[@sAksham-Ar](https://github.com/sAksham-Ar),
[@sbrunner](https://github.com/sbrunner),
[@philpagel](https://github.com/philpagel),
[@davemachado](https://github.com/davemachado),
[@2600box](https://github.com/2600box),
[@qcasey](https://github.com/qcasey),
[@Nicarim](https://github.com/Nicarim),
[@kpj](https://github.com/kpj), [@filcuk](https://github.com/filcuk),
[@Timoms](https://github.com/Timoms),
[@mattlamb99](https://github.com/mattlamb99),
[@padraigkitterick](https://github.com/padraigkitterick),
[@ajkavanagh](https://github.com/ajkavanagh),
[@Tooa](https://github.com/Tooa),
[@Unkn0wnCat](https://github.com/Unkn0wnCat),
[@pewter77](https://github.com/pewter77),
[@stumpylog](https://github.com/stumpylog),
[@Toxix](https://github.com/Toxix),
[@azapater](https://github.com/azapater),
[@jschpp](https://github.com/jschpp)

Another big thanks to the people who have contributed translations:

-   Michel Weimerskirch (michel_weimerskirch) suggested 31 translations
    into French and Luxembourgish.
-   jo.vandeginste suggested 21 translations into Dutch.
-   Lars Sørensen (Lrss) suggested 486 translations into Danish.
-   Alex (Sky-Dragon) voted for 46 translations in German.
-   Yannic Schröder (yschroeder) suggested 14 translations into German.
-   David Morais Ferreira (DavidMoraisFerreira) voted for 10
    translations in Portuguese and Luxembourgish.
-   David Morais Ferreira (DavidMoraisFerreira) suggested 88
    translations into French, German, Portuguese, Portuguese, Brazilian
    and Luxembourgish.
-   汪泠沣 (wlfcss) suggested 13 translations into Chinese Traditional.
-   Lars Sørensen (Lrss) suggested 167 translations into Danish.
-   Philmo67 suggested 11 translations into French.

## Paperless-ng

### paperless-ng 1.5.0

Support for Python 3.6 was dropped.

-   Updated python dependencies.
-   Base image of the docker image changed from Debian Buster to Debian
    Bullseye due to its recent release.
-   The docker image now uses python 3.9.
-   Added the Luxembourgish locale. Thanks for translating!
-   [Daniel Albers](https://github.com/AlD) added support for making the
    files and folders ignored by the paperless consume folder scanner
    configurable. See `PAPERLESS_CONSUMER_IGNORE_PATTERNS`.

### paperless-ng 1.4.5

This is a maintenance release.

-   Updated Python and Angular dependencies.
-   Changed the algorithm that changes permissions during startup. This
    is still fast, and will hopefully cause less issues.
-   Fixed an issue that would sometimes cause paperless to write an
    incomplete classification model file to disk.
-   Fixed an issue with the OCRmyPDF parser that would always try to
    extract text with PDFminer even from non-PDF files.

### paperless-ng 1.4.4

-   Drastically decreased the startup time of the docker container. The
    startup script adjusts file permissions of all data only if changes
    are required.
-   Paperless mail: Added ability to specify the character set for each
    server.
-   Document consumption: Ignore Mac OS specific files such as
    `.DS_STORE` and `._XXXXX.pdf`.
-   Fixed an issue with the automatic matching algorithm that prevents
    paperless from consuming new files.
-   Updated translations.

### paperless-ng 1.4.3

-   Additions and changes
    -   Added Swedish locale.
    -   [Stéphane Brunner](https://github.com/sbrunner) added an option
        to disable the progress bars of all management commands.
    -   [Jo Vandeginste](https://github.com/jovandeginste) added support
        for RTF documents to the Apache TIKA parser.
    -   [Michael Shamoon](https://github.com/shamoon) added dark mode
        for the login and logout pages.
    -   [Alexander Menk](https://github.com/amenk) added additional
        stylesheets for printing. You can now print any page of
        paperless and the print result will hide the page header,
        sidebar, and action buttons.
    -   Added support for sorting when using full text search.
-   Fixes
    -   [puuu](https://github.com/puuu) fixed
        `PAPERLESS_FORCE_SCRIPT_NAME`. You can now host paperless on sub
        paths such as `https://localhost:8000/paperless/`.
    -   Fixed an issue with the document consumer crashing on certain
        documents due to issues with pdfminer.six. This library is used
        for PDF text extraction.

### paperless-ng 1.4.2

-   Fixed an issue with `sudo` that caused paperless to not start on
    many Raspberry Pi devices. Thank you
    [WhiteHatTux](https://github.com/WhiteHatTux)!

### paperless-ng 1.4.1

-   Added Polish locale.
-   Changed some parts of the Dockerfile to hopefully restore
    functionality on certain ARM devices.
-   Updated python dependencies.
-   [Michael Shamoon](https://github.com/shamoon) added a sticky filter
    / bulk edit bar.
-   [sbrl](https://github.com/sbrl) changed the docker-entrypoint.sh
    script to increase compatibility with NFS shares.
-   [Chris Nagy](https://github.com/what-name) added support for
    creating a super user by passing `PAPERLESS_ADMIN_USER` and
    `PAPERLESS_ADMIN_PASSWORD` as environment variables to the docker
    container.

### paperless-ng 1.4.0

-   Docker images now use tesseract 4.1.1, which should fix a series of
    issues with OCR.
-   The full text search now displays results using the default document
    list. This enables selection, filtering and bulk edit on search
    results.
-   Changes
    -   Firefox only: Highlight search query in PDF previews.
    -   New URL pattern for accessing documents by ASN directly
        (<http://><paperless>/asn/123)
    -   Added logging when executing pre\* and post-consume scripts.
    -   Better error logging during document consumption.
    -   Updated python dependencies.
    -   Automatically inserts typed text when opening "Create new"
        dialogs on the document details page.
-   Fixes
    -   Fixed an issue with null characters in the document content.

!!! note

    The changed to the full text searching require you to reindex your
    documents. _The docker image does this automatically, you don't need to
    do anything._ To do this, execute the `document_index reindex`
    management command (see [Managing the document search index](administration.md#index)).

### paperless-ng 1.3.2

-   Added translation into Portuguese.
-   Changes
    -   The exporter now exports user accounts, mail accounts, mail
        rules and saved views as well.
-   Fixes
    -   Minor layout issues with document cards and the log viewer.
    -   Fixed an issue with any/all/exact matching when characters used
        in regular expressions were used for the match.

### paperless-ng 1.3.1

-   Added translation into Spanish and Russian.
-   Other changes
    -   ISO-8601 date format will now always show years with 4 digits.
    -   Added the ability to search for a document with a specific ASN.
    -   The document cards now display ASN, types and dates in a more
        organized way.
    -   Added document previews when hovering over the preview button.
-   Fixes
    -   The startup check for write permissions now works properly on
        NFS shares.
    -   Fixed an issue with the search results score indicator.
    -   Paperless was unable to generate thumbnails for encrypted PDF
        files and failed. Paperless will now generate a default
        thumbnail for these files.
    -   Fixed `AUTO_LOGIN_USERNAME`: Unable to perform POST/PUT/DELETE
        requests and unable to receive WebSocket messages.

### paperless-ng 1.3.0

This release contains new database migrations.

-   Changes
    -   The REST API is versioned from this point onwards. This will
        allow me to make changes without breaking existing clients. See
        the documentation about [API versioning](api.md#api-versioning) for details.
    -   Added a color picker for tag colors.
    -   Added the ability to use the filter for searching the document
        content as well.
    -   Added translations into Italian and Romanian. Thank you!
    -   Close individual documents from the sidebar. Thanks to [Michael
        Shamoon](https://github.com/shamoon).
    -   [BolkoSchreiber](https://github.com/BolkoSchreiber) added an
        option to disable/enable thumbnail inversion in dark mode.
    -   [Simon Taddiken](https://github.com/skuzzle) added the ability
        to customize the header used for remote user authentication with
        SSO applications.
-   Bug fixes
    -   Fixed an issue with the auto matching algorithm when more than
        256 tags were used.

### paperless-ng 1.2.1

-   [Rodrigo Avelino](https://github.com/rodavelino) translated
    Paperless into Portuguese (Brazil)!
-   The date input fields now respect the currently selected date
    format.
-   Added a fancy icon when adding paperless to the home screen on iOS
    devices. Thanks to [Joel Nordell](https://github.com/joelnordell).
-   When using regular expression matching, the regular expression is
    now validated before saving the tag/correspondent/type.
-   Regression fix: Dates on the front end did not respect date locale
    settings in some cases.

### paperless-ng 1.2.0

-   Changes to the OCRmyPDF integration
    -   Added support for deskewing and automatic rotation of
        incorrectly rotated pages. This is enabled by default, see
        [OCR settings](configuration.md#ocr).
    -   Better support for encrypted files.
    -   Better support for various other PDF files: Paperless will now
        attempt to force OCR with safe options when OCR fails with the
        configured options.
    -   Added an explicit option to skip cleaning with `unpaper`.
-   Download multiple selected documents as a zip archive.
-   The document list now remembers the current page.
-   Improved responsiveness when switching between saved views and the
    document list.
-   Increased the default wait time when observing files in the
    consumption folder with polling from 1 to 5 seconds. This will
    decrease the likelihood of paperless consuming partially written
    files.
-   Fixed a crash of the document archiver management command when
    trying to process documents with unknown mime types.
-   Paperless no longer depends on `libpoppler-cpp-dev`.

### paperless-ng 1.1.4

-   Added English (GB) locale.
-   Added ISO-8601 date display option.

### paperless-ng 1.1.3

-   Added a docker-specific configuration option to adjust the number of
    worker processes of the web server. See
    [Docker options](configuration.md#docker).
-   Some more memory usage optimizations.
-   Don't show inbox statistics if no inbox tag is defined.

### paperless-ng 1.1.2

-   Always show top left corner of thumbnails, even for extra wide
    documents.
-   Added a management command for executing the sanity checker
    directly. See [management utilities](administration.md#sanity-checker).
-   The weekly sanity check now reports messages in the log files.
-   Fixed an issue with the metadata tab not reporting anything in case
    of missing files.
-   Reverted a change from 1.1.0 that caused huge memory usage due to
    redis caching.
-   Some memory usage optimizations.

### paperless-ng 1.1.1

This release contains new database migrations.

-   Fixed a bug in the sanity checker that would cause it to display "x
    not in list" errors instead of actual issues.
-   Fixed a bug with filename generation for archive filenames that
    would cause the archive files of two documents to overlap.
    -   This happened when `PAPERLESS_FILENAME_FORMAT` is used and the
        filenames of two or more documents are the same, except for the
        file extension.
    -   Paperless will now store the archive filename in the database as
        well instead of deriving it from the original filename, and use
        the same logic for detecting and avoiding filename clashes
        that's also used for original filenames.
    -   The migrations will repair any missing archive files. If you're
        using tika, ensure that tika is running while performing the
        migration. Docker-compose will take care of that.
-   Fixed a bug with thumbnail regeneration when TIKA integration was
    used.
-   Added ASN as a placeholder field to the filename format.
-   The docker image now comes with built-in shortcuts for most
    management commands. These are now the recommended way to execute
    management commands, since these also ensure that they're always
    executed as the paperless user and you're less likely to run into
    permission issues. See
    [management commands](administration.md#management-commands).

### paperless-ng 1.1.0

-   Document processing status

    -   Paperless now shows the status of processing documents on the
        dashboard in real time.
    -   Status notifications when
        -   New documents are detected in the consumption folder, in
            mails, uploaded on the front end, or added with one of the
            mobile apps.
        -   Documents are successfully added to paperless.
        -   Document consumption failed (with error messages)
    -   Configuration options to enable/disable individual
        notifications.

-   Live updates to document lists and saved views when new documents
    are added.

    !!! tip

    For status notifications and live updates to work, paperless now
    requires an [ASGI](https://asgi.readthedocs.io/en/latest/)-enabled
    web server. The docker images uses `gunicorn` and an ASGI-enabled
    worker called [uvicorn](https://www.uvicorn.org/), and there is no
    need to configure anything.

    For bare metal installations, changes are required for the
    notifications to work. Adapt the service
    `paperless-webserver.service` to use the supplied `gunicorn.conf.py`
    configuration file and adapt the reference to the ASGI application
    as follows:

    ```
    ExecStart=/opt/paperless/.local/bin/gunicorn -c /opt/paperless/gunicorn.conf.py paperless.asgi:application
    ```

    Paperless will continue to work with WSGI, but you will not get any
    status notifications.

    Apache `mod_wsgi` users, see
    [this note](faq.md#how-do-i-get-websocket-support-with-apache-mod_wsgi).

-   Paperless now offers suggestions for tags, correspondents and types
    on the document detail page.

-   Added an interactive easy install script that automatically
    downloads, configures and starts paperless with docker.

-   Official support for Python 3.9.

-   Other changes and fixes

    -   Adjusted the default parallelization settings to run more than
        one task in parallel on systems with 4 or less cores. This
        addresses issues with paperless not consuming any new files when
        other tasks are running.
    -   Fixed a rare race condition that would cause paperless to
        process incompletely written files when using the upload on the
        dashboard.
    -   The document classifier no longer issues warnings and errors
        when auto matching is not used at all.
    -   Better icon for document previews.
    -   Better info section in the side bar.
    -   Paperless no longer logs to the database. Instead, logs are
        written to rotating log files. This solves many "database is
        locked" issues on Raspberry Pi, especially when SQLite is used.
    -   By default, log files are written to `PAPERLESS_DATA_DIR/log/`.
        Logging settings can be adjusted with `PAPERLESS_LOGGING_DIR`,
        `PAPERLESS_LOGROTATE_MAX_SIZE` and
        `PAPERLESS_LOGROTATE_MAX_BACKUPS`.

### paperless-ng 1.0.0

Nothing special about this release, but since there are relatively few
bug reports coming in, I think that this is reasonably stable.

-   Document export
    -   The document exporter has been rewritten to support updating an
        already existing export in place. This enables incremental
        backups with `rsync`.
    -   The document exporter supports naming exported files according
        to `PAPERLESS_FILENAME_FORMAT`.
    -   The document exporter locks the media directory and the database
        during execution to ensure that the resulting export is
        consistent.
    -   See the [updated documentation](administration.md#exporter) for more details.
-   Other changes and additions
    -   Added a language selector to the settings.
    -   Added date format options to the settings.
    -   Range selection with shift clicking is now possible in the
        document list.
    -   Filtering correspondent, type and tag management pages by name.
    -   Focus "Name" field in dialogs by default.

### paperless-ng 0.9.14

Starting with this version, releases are getting built automatically.
This release also comes with changes on how to install and update
paperless.

-   Paperless now uses GitHub Actions to make releases and build docker
    images.
    -   Docker images are available for amd64, armhf, and aarch64.
    -   When you pull an image from Docker Hub, Docker will
        automatically select the correct image for you.
-   Changes to docker installations and updates
    -   The `-dockerfiles.tar.xz` release archive is gone. Instead,
        simply grab the docker files from `/docker/compose` in the
        repository if you wish to install paperless by pulling from the
        hub.
    -   The docker compose files in `/docker/compose` were changed to
        always use the `latest` version automatically. In order to do
        further updates, simply do a `docker-compose pull`. The
        documentation has been updated.
    -   The docker compose files were changed to restart paperless on
        system boot only if it was running before shutdown.
    -   Documentation of the docker-compose files about what they do.
-   Changes to bare metal installations and updates
    -   The release archive is built exactly like before. However, the
        release now comes with already compiled translation messages and
        collected static files. Therefore, the update steps
        `compilemessages` and `collectstatic` are now obsolete.
-   Other changes
    -   A new configuration option `PAPERLESS_IGNORE_DATES` was added by
        [jayme-github](http://github.com/jayme-github). This can be used
        to instruct paperless to ignore certain dates (such as your date
        of birth) when guessing the date from the document content. This
        was actually introduced in 0.9.12, I just forgot to mention it
        in the changelog.
    -   The filter drop downs now display selected entries on top of all
        other entries.
    -   The PostgreSQL client now supports setting an explicit `sslmode`
        to force encryption of the connection to PostgreSQL.
    -   The docker images now come with `jbig2enc`, which is a lossless
        image encoder for PDF documents and decreases the size of
        certain PDF/A documents.
    -   When using any of the manual matching algorithms, paperless now
        logs messages about when and why these matching algorithms
        matched.
    -   The default settings for parallelization in paperless were
        adjusted to always leave one CPU core free.
    -   Added an option to the frontend to choose which method to use
        for displaying PDF documents.
-   Fixes
    -   An issue with the tika parser not picking up files from the
        consumption directory was fixed.
    -   A couple changes to the dark mode and fixes to several other
        layout issues.
    -   An issue with the drop downs for correspondents, tags and types
        not properly supporting filtering with special characters was
        fixed.
    -   Fixed an issue with filenames of downloaded files: Dates where
        off by one day due to timezone issues.
    -   Searching will continue to work even when the index returns
        non-existing documents. This resulted in "Document does not
        exist" errors before. Instead, a warning is logged, indicating
        the issue.
    -   An issue with the consumer crashing when invalid regular
        expression were used was fixed.

### paperless-ng 0.9.13

-   Fixed an issue with Paperless not starting due to the new Tika
    integration when `USERMAP_UID` and `USERMAP_GID` was used in the
    `docker-compose.env` file.

### paperless-ng 0.9.12

-   Paperless localization
    -   Thanks to the combined efforts of many users, Paperless is now
        available in English, Dutch, French and German.
-   Thanks to [Jo Vandeginste](https://github.com/jovandeginste),
    Paperless has optional support for Office documents such as .docx,
    .doc, .odt and more.
    -   See the [Tika settings](configuration.md#tika) on how to enable this
        feature. This feature requires two additional services (one for
        parsing Office documents and metadata extraction and another for
        converting Office documents to PDF), and is therefore not enabled
        on default installations.
    -   As with all other documents, paperless converts Office documents
        to PDF and stores both the original as well as the archived PDF.
-   Dark mode
    -   Thanks to [Michael Shamoon](https://github.com/shamoon),
        paperless now has a dark mode. Configuration is available in the
        settings.
-   Other changes and additions
    -   The PDF viewer now uses a local copy of some dependencies
        instead of fetching them from the internet. Thanks to
        [slorenz](https://github.com/sisao).
    -   Revamped search bar styling thanks to [Michael
        Shamoon](https://github.com/shamoon).
    -   Sorting in the document list by clicking on table headers.
    -   A button was added to the document detail page that assigns a
        new ASN to a document.
    -   Form field validation: When providing invalid input in a form
        (such as a duplicate ASN or no name), paperless now has visual
        indicators and clearer error messages about what's wrong.
    -   Paperless disables buttons with network actions (such as save
        and delete) when a network action is active. This indicates that
        something is happening and prevents double clicking.
    -   When using "Save & next", the title field is focussed
        automatically to better support keyboard editing.
    -   E-Mail: Added filter rule parameters to allow inline attachments
        (watch out for mails with inlined images!) and attachment
        filename filters with wildcards.
    -   Support for remote user authentication thanks to [Michael
        Shamoon](https://github.com/shamoon). This is useful for hiding
        Paperless behind single sign on applications such as
        [authelia](https://www.authelia.com/).
    -   "Clear filters" has been renamed to "Reset filters" and now
        correctly restores the default filters on saved views. Thanks to
        [Michael Shamoon](https://github.com/shamoon)
-   Fixes
    -   Paperless was unable to save views when "Not assigned" was
        chosen in one of the filter dropdowns.
    -   Clearer error messages when pre and post consumption scripts do
        not exist.
    -   The post consumption script is executed later in the consumption
        process. Before the change, an ID was passed to the script
        referring to a document that did not yet exist in the database.

### paperless-ng 0.9.11

-   Fixed an issue with the docker image not starting at all due to a
    configuration change of the web server.

### paperless-ng 0.9.10

-   Bulk editing
    -   Thanks to [Michael Shamoon](https://github.com/shamoon), we've
        got a new interface for the bulk editor.
    -   There are some configuration options in the settings to alter
        the behavior.
-   Other changes and additions
    -   Thanks to [zjean](https://github.com/zjean), paperless now
        publishes a webmanifest, which is useful for adding the
        application to home screens on mobile devices.
    -   The Paperless-ng logo now navigates to the dashboard.
    -   Filter for documents that don't have any correspondents, types
        or tags assigned.
    -   Tags, types and correspondents are now sorted case insensitive.
    -   Lots of preparation work for localization support.
-   Fixes
    -   Added missing dependencies for Raspberry Pi builds.
    -   Fixed an issue with plain text file consumption: Thumbnail
        generation failed due to missing fonts.
    -   An issue with the search index reporting missing documents after
        bulk deletes was fixed.
    -   Issue with the tag selector not clearing input correctly.
    -   The consumer used to stop working when encountering an
        incomplete classifier model file.

!!! note

    The bulk delete operations did not update the search index. Therefore,
    documents that you deleted remained in the index and caused the search
    to return messages about missing documents when searching. Further bulk
    operations will properly update the index.

    However, this change is not retroactive: If you used the delete method
    of the bulk editor, you need to reindex your search index by
    [running the management command `document_index` with the argument `reindex`](administration.md#index).

### paperless-ng 0.9.9

Christmas release!

-   Bulk editing
    -   Paperless now supports bulk editing.
    -   The following operations are available: Add and remove
        correspondents, tags, document types from selected documents, as
        well as mass-deleting documents.
    -   We've got a more fancy UI in the works that makes these
        features more accessible, but that's not quite ready yet.
-   Searching
    -   Paperless now supports searching for similar documents ("More
        like this") both from the document detail page as well as from
        individual search results.
    -   A search score indicates how well a document matches the search
        query, or how similar a document is to a given reference
        document.
-   Other additions and changes
    -   Clarification in the UI that the fields "Match" and "Is
        insensitive" are not relevant for the Auto matching algorithm.
    -   New select interface for tags, types and correspondents allows
        filtering. This also improves tag selection. Thanks again to
        [Michael Shamoon](https://github.com/shamoon)!
    -   Page navigation controls for the document viewer, thanks to
        [Michael Shamoon](https://github.com/shamoon).
    -   Layout changes to the small cards document list.
    -   The dashboard now displays the username (or full name if
        specified in the admin) on the dashboard.
-   Fixes
    -   An error that caused the document importer to crash was fixed.
    -   An issue with changes not being possible when
        `PAPERLESS_COOKIE_PREFIX` is used was fixed.
    -   The date selection filters now allow manual entry of dates.
-   Feature Removal
    -   Most of the guesswork features have been removed. Paperless no
        longer tries to extract correspondents and tags from file names.

### paperless-ng 0.9.8

This release addresses two severe issues with the previous release.

-   The delete buttons for document types, correspondents and tags were
    not working.
-   The document section in the admin was causing internal server errors
    (500).

### paperless-ng 0.9.7

-   Front end
    -   Thanks to the hard work of [Michael
        Shamoon](https://github.com/shamoon), paperless now comes with a
        much more streamlined UI for filtering documents.
    -   [Michael Shamoon](https://github.com/shamoon) replaced the
        document preview with another component. This should fix
        compatibility with Safari browsers.
    -   Added buttons to the management pages to quickly show all
        documents with one specific tag, correspondent, or title.
    -   Paperless now stores your saved views on the server and
        associates them with your user account. This means that you can
        access your views on multiple devices and have separate views
        for different users. You will have to recreate your views.
    -   The GitHub and documentation links now open in new tabs/windows.
        Thanks to [rYR79435](https://github.com/rYR79435).
    -   Paperless now generates default saved view names when saving
        views with certain filter rules.
    -   Added a small version indicator to the front end.
-   Other additions and changes
    -   The new filename format field `{tag_list}` inserts a list of
        tags into the filename, separated by comma.
    -   The `document_retagger` no longer removes inbox tags or tags
        without matching rules.
    -   The new configuration option `PAPERLESS_COOKIE_PREFIX` allows
        you to run multiple instances of paperless on different ports.
        This option enables you to be logged in into multiple instances
        by specifying different cookie names for each instance.
-   Fixes
    -   Sometimes paperless would assign dates in the future to newly
        consumed documents.
    -   The filename format fields `{created_month}` and `{created_day}`
        now use a leading zero for single digit values.
    -   The filename format field `{tags}` can no longer be used without
        arguments.
    -   Paperless was not able to consume many images (especially images
        from mobile scanners) due to missing DPI information. Paperless
        now assumes A4 paper size for PDF generation if no DPI
        information is present.
    -   Documents with empty titles could not be opened from the table
        view due to the link being empty.
    -   Fixed an issue with filenames containing special characters such
        as `:` not being accepted for upload.
    -   Fixed issues with thumbnail generation for plain text files.

### paperless-ng 0.9.6

This release focusses primarily on many small issues with the UI.

-   Front end
    -   Paperless now has proper window titles.
    -   Fixed an issue with the small cards when more than 7 tags were
        used.
    -   Navigation of the "Show all" links adjusted. They navigate to
        the saved view now, if available in the sidebar.
    -   Some indication on the document lists that a filter is active
        was added.
    -   There's a new filter to filter for documents that do _not_ have
        a certain tag.
    -   The file upload box now shows upload progress.
    -   The document edit page was reorganized.
    -   The document edit page shows various information about a
        document.
    -   An issue with the height of the preview was fixed.
    -   Table issues with too long document titles fixed.
-   API
    -   The API now serves file names with documents.
    -   The API now serves various metadata about documents.
    -   API documentation updated.
-   Other
    -   Fixed an issue with the docker image when a non-standard
        PostgreSQL port was used.
    -   The docker image was trying check for installed languages before
        actually installing them.
    -   `FILENAME_FORMAT` placeholder for document types.
    -   The filename formatter is now less restrictive with file names
        and tries to conserve the original correspondents, types and
        titles as much as possible.
    -   The filename formatter does not include the document ID in
        filenames anymore. It will rather append `_01`, `_02`, etc when
        it detects duplicate filenames.

!!! note

The changes to the filename format will apply to newly added documents
and changed documents. If you want all files to reflect these changes,
execute the `document_renamer` management command.

### paperless-ng 0.9.5

This release concludes the big changes I wanted to get rolled into
paperless. The next releases before 1.0 will focus on fixing issues,
primarily.

-   OCR
    -   Paperless now uses
        [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF) to perform OCR
        on documents. It still uses tesseract under the hood, but the
        PDF parser of Paperless has changed considerably and will behave
        different for some documents.
    -   OCRmyPDF creates archived PDF/A documents with embedded text
        that can be selected in the front end.
    -   Paperless stores archived versions of documents alongside with
        the originals. The originals can be accessed on the document
        edit page. If available, a dropdown menu will appear next to the
        download button.
    -   Many of the configuration options regarding OCR have changed.
        See [OCR settings](configuration.md#ocr) for details.
    -   Paperless no longer guesses the language of your documents. It
        always uses the language that you specified with
        `PAPERLESS_OCR_LANGUAGE`. Be sure to set this to the language
        the majority of your documents are in. Multiple languages can be
        specified, but that requires more CPU time.
    -   The management command [`document_archiver`](administration.md#archiver)
        can be used to create archived versions for already existing documents.
-   Tags from consumption folder.
    -   Thanks to [jayme-github](https://github.com/jayme-github),
        paperless now consumes files from sub folders in the consumption
        folder and is able to assign tags based on the sub folders a
        document was found in. This can be configured with
        `PAPERLESS_CONSUMER_RECURSIVE` and
        `PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS`.
-   API
    -   The API now offers token authentication.
    -   The endpoint for uploading documents now supports specifying
        custom titles, correspondents, tags and types. This can be used
        by clients to override the default behavior of paperless. See
        [POSTing documents](api.md#file-uploads).
    -   The document endpoint of API now serves documents in this form:
        -   correspondents, document types and tags are referenced by
            their ID in the fields `correspondent`, `document_type` and
            `tags`. The `*_id` versions are gone. These fields are
            read/write.
        -   paperless does not serve nested tags, correspondents or
            types anymore.
-   Front end
    -   Paperless does some basic caching of correspondents, tags and
        types and will only request them from the server when necessary
        or when entirely reloading the page.
    -   Document list fetching is about 10%-30% faster now, especially
        when lots of tags/correspondents are present.
    -   Some minor improvements to the front end, such as document count
        in the document list, better highlighting of the current page,
        and improvements to the filter behavior.
-   Fixes:
    -   A bug with the generation of filenames for files with
        unsupported types caused the exporter and document saving to
        crash.
    -   Mail handling no longer exits entirely when encountering errors.
        It will skip the account/rule/message on which the error
        occurred.
    -   Assigning correspondents from mail sender names failed for very
        long names. Paperless no longer assigns correspondents in these
        cases.

### paperless-ng 0.9.4

-   Searching:
    -   Paperless now supports searching by tags, types and dates and
        correspondents. In order to have this applied to your existing
        documents, you need to perform a `document_index reindex`
        management command (see [document search index](administration.md#index))
        that adds the data to the search index. You only need to do this
        once, since the schema of the search index changed. Paperless
        keeps the index updated after that whenever something changes.
    -   Paperless now has spelling corrections ("Did you mean") for
        miss-typed queries.
    -   The documentation contains
        [information about the query syntax](usage.md#basic-usage_searching).
-   Front end:
    -   Clickable tags, correspondents and types allow quick filtering
        for related documents.
    -   Saved views are now editable.
    -   Preview documents directly in the browser.
    -   Navigation from the dashboard to saved views.
-   Fixes:
    -   A severe error when trying to use post consume scripts.
    -   An error in the consumer that cause invalid messages of missing
        files to show up in the log.
-   The documentation now contains information about bare metal installs
    and a section about how to setup the development environment.

### paperless-ng 0.9.3

-   Setting `PAPERLESS_AUTO_LOGIN_USERNAME` replaces
    `PAPERLESS_DISABLE_LOGIN`. You have to specify your username.
-   Added a simple sanity checker that checks your documents for missing
    or orphaned files, files with wrong checksums, inaccessible files,
    and documents with empty content.
-   It is no longer possible to encrypt your documents. For the time
    being, paperless will continue to operate with already encrypted
    documents.
-   Fixes:
    -   Paperless now uses inotify again, since the watchdog was causing
        issues which I was not aware of.
    -   Issue with the automatic classifier not working with only one
        tag.
    -   A couple issues with the search index being opened to eagerly.
-   Added lots of tests for various parts of the application.

### paperless-ng 0.9.2

-   Major changes to the front end (colors, logo, shadows, layout of the
    cards, better mobile support)
-   Paperless now uses mime types and libmagic detection to determine if
    a file type is supported and which parser to use. Removes all file
    type checks that where present in MANY different places in
    paperless.
-   Mail consumer now correctly consumes documents even when their
    content type was not set correctly. (i.e. PDF documents with content
    type `application/octet-stream`)
-   Basic sorting of mail rules added
-   Much better admin for mail rule editing.
-   Docker entrypoint script awaits the database server if it is
    configured.
-   Disabled editing of logs.
-   New setting `PAPERLESS_OCR_PAGES` limits the tesseract parser to the
    first n pages of scanned documents.
-   Fixed a bug where tasks with too long task names would not show up
    in the admin.

### paperless-ng 0.9.1

-   Moved documentation of the settings to the actual documentation.
-   Updated release script to force the user to choose between SQLite
    and PostgreSQL. This avoids confusion when upgrading from paperless.

### paperless-ng 0.9.0

-   **Deprecated:** GnuPG. [See this note on the state of GnuPG in paperless-ng.](administration.md#encryption)
    This features will most likely be removed in future versions.
-   **Added:** New frontend. Features:
    -   Single page application: It's much more responsive than the
        django admin pages.
    -   Dashboard. Shows recently scanned documents, or todo notes, or
        other documents at wish. Allows uploading of documents. Shows
        basic statistics.
    -   Better document list with multiple display options.
    -   Full text search with result highlighting, auto completion and
        scoring based on the query. It uses a document search index in
        the background.
    -   Saveable filters.
    -   Better log viewer.
-   **Added:** Document types. Assign these to documents just as
    correspondents. They may be used in the future to perform automatic
    operations on documents depending on the type.
-   **Added:** Inbox tags. Define an inbox tag and it will automatically
    be assigned to any new document scanned into the system.
-   **Added:** Automatic matching. A new matching algorithm that
    automatically assigns tags, document types and correspondents to
    your documents. It uses a neural network trained on your data.
-   **Added:** Archive serial numbers. Assign these to quickly find
    documents stored in physical binders.
-   **Added:** Enabled the internal user management of django. This
    isn't really a multi user solution, however, it allows more than
    one user to access the website and set some basic permissions /
    renew passwords.
-   **Modified \[breaking\]:** All new mail consumer with customizable
    filters, actions and multiple account support. Replaces the old mail
    consumer. The new mail consumer needs different configuration but
    can be configured to act exactly like the old consumer.
-   **Modified:** Changes to the consumer:
    -   Now uses the excellent watchdog library that should make sure
        files are discovered no matter what the platform is.
    -   The consumer now uses a task scheduler to run consumption
        processes in parallel. This means that consuming many documents
        should be much faster on systems with many cores.
    -   Concurrency is controlled with the new settings
        `PAPERLESS_TASK_WORKERS` and `PAPERLESS_THREADS_PER_WORKER`. See
        TODO for details on concurrency.
    -   The consumer no longer blocks the database for extended periods
        of time.
    -   An issue with tesseract running multiple threads per page and
        slowing down the consumer was fixed.
-   **Modified \[breaking\]:** REST Api changes:
    -   New filters added, other filters removed (case sensitive
        filters, slug filters)
    -   Endpoints for thumbnails, previews and downloads replace the old
        `/fetch/` urls. Redirects are in place.
    -   Endpoint for document uploads replaces the old `/push` url.
        Redirects are in place.
    -   Foreign key relationships are now served as IDs, not as urls.
-   **Modified \[breaking\]:** PostgreSQL:
    -   If `PAPERLESS_DBHOST` is specified in the settings, paperless
        uses PostgreSQL instead of SQLite. Username, database and
        password all default to `paperless` if not specified.
-   **Modified \[breaking\]:** document_retagger management command
    rework. See [Document retagger](administration.md#retagger) for
    details. Replaces `document_correspondents` management command.
-   **Removed \[breaking\]:** Reminders.
-   **Removed:** All customizations made to the django admin pages.
-   **Removed \[breaking\]:** The docker image no longer supports SSL.
    If you want to expose paperless to the internet, hide paperless
    behind a proxy server that handles SSL requests.
-   **Internal changes:** Mostly code cleanup, including:
    -   Rework of the code of the tesseract parser. This is now a lot
        cleaner.
    -   Rework of the filename handling code. It was a mess.
    -   Fixed some issues with the document exporter not exporting all
        documents when encountering duplicate filenames.
    -   Added a task scheduler that takes care of checking mail,
        training the classifier, maintaining the document search index
        and consuming documents.
    -   Updated dependencies. Now uses Pipenv all around.
    -   Updated Dockerfile and docker-compose. Now uses `supervisord` to
        run everything paperless-related in a single container.
-   **Settings:**
    -   `PAPERLESS_FORGIVING_OCR` is now default and gone. Reason: Even
        if `langdetect` fails to detect a language, tesseract still does
        a very good job at ocr'ing a document with the default
        language. Certain language specifics such as umlauts may not get
        picked up properly.
    -   `PAPERLESS_DEBUG` defaults to `false`.
    -   The presence of `PAPERLESS_DBHOST` now determines whether to use
        PostgreSQL or SQLite.
    -   `PAPERLESS_OCR_THREADS` is gone and replaced with
        `PAPERLESS_TASK_WORKERS` and `PAPERLESS_THREADS_PER_WORKER`.
        Refer to the config example for details.
    -   `PAPERLESS_OPTIMIZE_THUMBNAILS` allows you to disable or enable
        thumbnail optimization. This is useful on less powerful devices.
-   Many more small changes here and there. The usual stuff.

## Paperless

### 2.7.0

-   [syntonym](https://github.com/syntonym) submitted a pull request to
    catch IMAP connection errors
    [#475](https://github.com/the-paperless-project/paperless/pull/475).
-   [Stéphane Brunner](https://github.com/sbrunner) added `psycopg2` to
    the Pipfile
    [#489](https://github.com/the-paperless-project/paperless/pull/489).
    He also fixed a syntax error in `docker-compose.yml.example`
    [#488](https://github.com/the-paperless-project/paperless/pull/488)
    and added [DjangoQL](https://github.com/ivelum/djangoql), which
    allows a litany of handy search functionality
    [#492](https://github.com/the-paperless-project/paperless/pull/492).
-   [CkuT](https://github.com/CkuT) and
    [JOKer](https://github.com/MasterofJOKers) hacked out a simple, but
    super-helpful optimisation to how the thumbnails are served up,
    improving performance considerably
    [#481](https://github.com/the-paperless-project/paperless/pull/481).
-   [tsia](https://github.com/tsia) added a few fields to the tags REST
    API.
    [#483](https://github.com/the-paperless-project/paperless/pull/483).
-   [Brian Cribbs](https://github.com/cribbstechnolog) improved the
    documentation to help people using Paperless over NFS
    [#484](https://github.com/the-paperless-project/paperless/pull/484).
-   [Brendan M. Sleight](https://github.com/bmsleight) updated the
    documentation to include a note for setting the `DEBUG` value. The
    `paperless.conf.example` file was also updated to mirror the project
    defaults.

### 2.6.1

-   We now have a logo, complete with a favicon :-)
-   Removed some problematic tests.
-   Fix the docker-compose example config to include a shared consume
    volume so that using the push API will work for users of the Docker
    install. Thanks to [Colin Frei](https://github.com/colinfrei) for
    fixing this in
    [#466](https://github.com/the-paperless-project/paperless/pull/466).
-   [khrise](https://github.com/khrise) submitted a pull request to
    include the `added` property to the REST API
    [#471](https://github.com/the-paperless-project/paperless/pull/471).

### 2.6.0

-   Allow an infinite number of logs to be deleted. Thanks to
    [Ulli](https://github.com/Ulli2k) for noting the problem in
    [#433](https://github.com/the-paperless-project/paperless/issues/433).
-   Fix the `RecentCorrespondentsFilter` correspondents filter that was
    added in 2.4 to play nice with the defaults. Thanks to
    [tsia](https://github.com/tsia) and
    [Sblop](https://github.com/Sblop) who pointed this out.
    [#423](https://github.com/the-paperless-project/paperless/issues/423).
-   Updated dependencies to include (among other things) a security
    patch to requests.
-   Fix text in sample data for tests so that the language guesser stops
    thinking that everything is in Catalan because we had _Lorem ipsum_
    in there.
-   Tweaked the gunicorn sample command to use filesystem paths instead
    of Python paths.
    [#441](https://github.com/the-paperless-project/paperless/pull/441)
-   Added pretty colour boxes next to the hex values in the Tags
    section, thanks to a pull request from [Joshua
    Taillon](https://github.com/jat255)
    [#442](https://github.com/the-paperless-project/paperless/pull/442).
-   Added a `.editorconfig` file to better specify coding style.
-   [Joshua Taillon](https://github.com/jat255) also added some logic to
    tie Paperless' date guessing logic into how it parses file names on
    import.
    [#440](https://github.com/the-paperless-project/paperless/pull/440)

### 2.5.0

-   **New dependency**: Paperless now optimises thumbnail generation
    with [optipng](https://optipng.sourceforge.net/), so you'll need to
    install that somewhere in your PATH or declare its location in
    `PAPERLESS_OPTIPNG_BINARY`. The Docker image has already been
    updated on the Docker Hub, so you just need to pull the latest one
    from there if you're a Docker user.
-   "Login free" instances of Paperless were breaking whenever you
    tried to edit objects in the admin: adding/deleting tags or
    correspondents, or even fixing spelling. This was due to the "user
    hack" we were applying to sessions that weren't using a login, as
    that hack user didn't have a valid id. The fix was to attribute the
    first user id in the system to this hack user.
    [#394](https://github.com/the-paperless-project/paperless/issues/394)
-   A problem in how we handle slug values on Tags and Correspondents
    required a few changes to how we handle this field
    [#393](https://github.com/the-paperless-project/paperless/issues/393):
    1.  Slugs are no longer editable. They're derived from the name of
        the tag or correspondent at save time, so if you wanna change
        the slug, you have to change the name, and even then you're
        restricted to the rules of the `slugify()` function. The slug
        value is still visible in the admin though.
    2.  I've added a migration to go over all existing tags &
        correspondents and rewrite the `.slug` values to ones conforming
        to the `slugify()` rules.
    3.  The consumption process now uses the same rules as `.save()` in
        determining a slug and using that to check for an existing
        tag/correspondent.
-   An annoying bug in the date capture code was causing some bogus
    dates to be attached to documents, which in turn busted the UI.
    Thanks to [Andrew Peng](https://github.com/pengc99) for reporting
    this.
    [#414](https://github.com/the-paperless-project/paperless/issues/414).
-   A bug in the Dockerfile meant that Tesseract language files weren't
    being installed correctly. [euri10](https://github.com/euri10) was
    quick to provide a fix:
    [#406](https://github.com/the-paperless-project/paperless/issues/406),
    [#413](https://github.com/the-paperless-project/paperless/pull/413).
-   Document consumption is now wrapped in a transaction as per an old
    ticket
    [#262](https://github.com/the-paperless-project/paperless/issues/262).
-   The `get_date()` functionality of the parsers has been consolidated
    onto the `DocumentParser` class since much of that code was
    redundant anyway.

### 2.4.0

-   A new set of actions are now available thanks to
    [jonaswinkler](https://github.com/jonaswinkler)'s very first pull
    request! You can now do nifty things like tag documents in bulk, or
    set correspondents in bulk.
    [#405](https://github.com/the-paperless-project/paperless/pull/405)
-   The import/export system is now a little smarter. By default,
    documents are tagged as `unencrypted`, since exports are by their
    nature unencrypted. It's now in the import step that we decide the
    storage type. This allows you to export from an encrypted system and
    import into an unencrypted one, or vice-versa.
-   The migration history has been slightly modified to accommodate
    PostgreSQL users. Additionally, you can now tell paperless to use
    PostgreSQL simply by declaring `PAPERLESS_DBUSER` in your
    environment. This will attempt to connect to your Postgres database
    without a password unless you also set `PAPERLESS_DBPASS`.
-   A bug was found in the REST API filter system that was the result of
    an update of django-filter some time ago. This has now been patched
    in
    [#412](https://github.com/the-paperless-project/paperless/issues/412).
    Thanks to [thepill](https://github.com/thepill) for spotting it!

### 2.3.0

-   Support for consuming plain text & markdown documents was added by
    [Joshua Taillon](https://github.com/jat255)! This was a
    long-requested feature, and it's addition is likely to be greatly
    appreciated by the community:
    [#395](https://github.com/the-paperless-project/paperless/pull/395)
    Thanks also to [David Martin](https://github.com/ddddavidmartin) for
    his assistance on the issue.
-   [dubit0](https://github.com/dubit0) found & fixed a bug that
    prevented management commands from running before we had an
    operational database:
    [#396](https://github.com/the-paperless-project/paperless/pull/396)
-   Joshua also added a simple update to the thumbnail generation
    process to improve performance:
    [#399](https://github.com/the-paperless-project/paperless/pull/399)
-   As his last bit of effort on this release, Joshua also added some
    code to allow you to view the documents inline rather than download
    them as an attachment.
    [#400](https://github.com/the-paperless-project/paperless/pull/400)
-   Finally, [ahyear](https://github.com/ahyear) found a slip in the
    Docker documentation and patched it.
    [#401](https://github.com/the-paperless-project/paperless/pull/401)

### 2.2.1

-   [Kyle Lucy](https://github.com/kmlucy) reported a bug quickly after
    the release of 2.2.0 where we broke the `DISABLE_LOGIN` feature:
    [#392](https://github.com/the-paperless-project/paperless/issues/392).

### 2.2.0

-   Thanks to [dadosch](https://github.com/dadosch), [Wolfgang
    Mader](https://github.com/wmader), and [Tim
    Brooks](https://github.com/brookst) this is the first version of
    Paperless that supports Django 2.0! As a result of their hard work,
    you can now also run Paperless on Python 3.7 as well:
    [#386](https://github.com/the-paperless-project/paperless/issues/386)
    &
    [#390](https://github.com/the-paperless-project/paperless/pull/390).
-   [Stéphane Brunner](https://github.com/sbrunner) added a few lines of
    code that made tagging interface a lot easier on those of us with
    lots of different tags:
    [#391](https://github.com/the-paperless-project/paperless/pull/391).
-   [Kilian Koeltzsch](https://github.com/kiliankoe) noticed a bug in
    how we capture & automatically create tags, so that's fixed now
    too:
    [#384](https://github.com/the-paperless-project/paperless/issues/384).
-   [erikarvstedt](https://github.com/erikarvstedt) tweaked the
    behaviour of the test suite to be better behaved for packaging
    environments:
    [#383](https://github.com/the-paperless-project/paperless/pull/383).
-   [Lukasz Soluch](https://github.com/LukaszSolo) added CORS support to
    make building a new Javascript-based front-end cleaner & easier:
    [#387](https://github.com/the-paperless-project/paperless/pull/387).

### 2.1.0

-   [Enno Lohmeier](https://github.com/elohmeier) added three simple
    features that make Paperless a lot more user (and developer)
    friendly:
    1.  There's a new search box on the front page:
        [#374](https://github.com/the-paperless-project/paperless/pull/374).
    2.  The correspondents & tags pages now have a column showing the
        number of relevant documents:
        [#375](https://github.com/the-paperless-project/paperless/pull/375).
    3.  The Dockerfile has been tweaked to build faster for those of us
        who are doing active development on Paperless using the Docker
        environment:
        [#376](https://github.com/the-paperless-project/paperless/pull/376).
-   You now also have the ability to customise the interface to your
    heart's content by creating a file called `overrides.css` and/or
    `overrides.js` in the root of your media directory. Thanks to [Mark
    McFate](https://github.com/SummittDweller) for this idea:
    [#371](https://github.com/the-paperless-project/paperless/issues/371)

### 2.0.0

This is a big release as we've changed a core-functionality of
Paperless: we no longer encrypt files with GPG by default.

The reasons for this are many, but it boils down to that the encryption
wasn't really all that useful, as files on-disk were still accessible
so long as you had the key, and the key was most typically stored in the
config file. In other words, your files are only as safe as the
`paperless` user is. In addition to that, _the contents of the documents
were never encrypted_, so important numbers etc. were always accessible
simply by querying the database. Still, it was better than nothing, but
the consensus from users appears to be that it was more an annoyance
than anything else, so this feature is now turned off unless you
explicitly set a passphrase in your config file.

### Migrating from 1.x

Encryption isn't gone, it's just off for new users. So long as you
have `PAPERLESS_PASSPHRASE` set in your config or your environment,
Paperless should continue to operate as it always has. If however, you
want to drop encryption too, you only need to do two things:

1.  Run
    `./manage.py migrate && ./manage.py change_storage_type gpg unencrypted`.
    This will go through your entire database and Decrypt All The
    Things.
2.  Remove `PAPERLESS_PASSPHRASE` from your `paperless.conf` file, or
    simply stop declaring it in your environment.

Special thanks to [erikarvstedt](https://github.com/erikarvstedt),
[matthewmoto](https://github.com/matthewmoto), and
[mcronce](https://github.com/mcronce) who did the bulk of the work on
this big change.

### 1.4.0

-   [Quentin Dawans](https://github.com/ovv) has refactored the document
    consumer to allow for some command-line options. Notably, you can
    now direct it to consume from a particular `--directory`, limit the
    `--loop-time`, set the time between mail server checks with
    `--mail-delta` or just run it as a one-off with `--one-shot`. See
    [#305](https://github.com/the-paperless-project/paperless/issues/305)
    &
    [#313](https://github.com/the-paperless-project/paperless/pull/313)
    for more information.
-   Refactor the use of travis/tox/pytest/coverage into two files:
    `.travis.yml` and `setup.cfg`.
-   Start generating requirements.txt from a Pipfile. I'll probably
    switch over to just using pipenv in the future.
-   All for a alternative FreeBSD-friendly location for
    `paperless.conf`. Thanks to [Martin
    Arendtsen](https://github.com/Arendtsen) who provided this
    ([#322](https://github.com/the-paperless-project/paperless/pull/322)).
-   Document consumption events are now logged in the Django admin
    events log. Thanks to [CkuT](https://github.com/CkuT) for doing the
    legwork on this one and to [Quentin Dawans](https://github.com/ovv)
    & [David Martin](https://github.com/ddddavidmartin) for helping to
    coordinate & work out how the feature would be developed.
-   [erikarvstedt](https://github.com/erikarvstedt) contributed a pull
    request
    ([#328](https://github.com/the-paperless-project/paperless/pull/328))
    to add `--noreload` to the default server start process. This helps
    reduce the load imposed by the running webservice.
-   Through some discussion on
    [#253](https://github.com/the-paperless-project/paperless/issues/253)
    and
    [#323](https://github.com/the-paperless-project/paperless/issues/323),
    we've removed a few of the hardcoded URL values to make it easier
    for people to host Paperless on a subdirectory. Thanks to [Quentin
    Dawans](https://github.com/ovv) and [Kyle
    Lucy](https://github.com/kmlucy) for helping to work this out.
-   The clickable area for documents on the listing page has been
    increased to a more predictable space thanks to a glorious hack from
    [erikarvstedt](https://github.com/erikarvstedt) in
    [#344](https://github.com/the-paperless-project/paperless/pull/344).
-   [Strubbl](https://github.com/strubbl) noticed an annoying bug in the
    bash script wrapping the Docker entrypoint and fixed it with some
    very creating Bash skills:
    [#352](https://github.com/the-paperless-project/paperless/pull/352).
-   You can now use the search field to find documents by tag thanks to
    [thinkjk](https://github.com/thinkjk)'s _first ever issue_:
    [#354](https://github.com/the-paperless-project/paperless/issues/354).
-   Inotify is now being used to detect additions to the consume
    directory thanks to some excellent work from
    [erikarvstedt](https://github.com/erikarvstedt) on
    [#351](https://github.com/the-paperless-project/paperless/pull/351)

### 1.3.0

-   You can now run Paperless without a login, though you'll still have
    to create at least one user. This is thanks to a pull-request from
    [matthewmoto](https://github.com/matthewmoto):
    [#295](https://github.com/the-paperless-project/paperless/pull/295).
    Note that logins are still required by default, and that you need to
    disable them by setting `PAPERLESS_DISABLE_LOGIN="true"` in your
    environment or in `/etc/paperless.conf`.
-   Fix for
    [#303](https://github.com/the-paperless-project/paperless/issues/303)
    where sketchily-formatted documents could cause the consumer to
    break and insert half-records into the database breaking all sorts
    of things. We now capture the return codes of both `convert` and
    `unpaper` and fail-out nicely.
-   Fix for additional date types thanks to input from
    [Isaac](https://github.com/isaacsando) and code from
    [BastianPoe](https://github.com/BastianPoe)
    ([#301](https://github.com/the-paperless-project/paperless/issues/301)).
-   Fix for running migrations in the Docker container
    ([#299](https://github.com/the-paperless-project/paperless/issues/299)).
    Thanks to [Georgi Todorov](https://github.com/TeraHz) for the fix
    ([#300](https://github.com/the-paperless-project/paperless/pull/300))
    and to [Pit](https://github.com/pitkley) for the review.
-   Fix for Docker cases where the issuing user is not UID 1000. This
    was a collaborative fix between [Jeffrey
    Portman](https://github.com/ChromoX) and
    [Pit](https://github.com/pitkley) in
    [#311](https://github.com/the-paperless-project/paperless/pull/311)
    and
    [#312](https://github.com/the-paperless-project/paperless/pull/312)
    to fix
    [#306](https://github.com/the-paperless-project/paperless/issues/306).
-   Patch the historical migrations to support MySQL's um,
    _interesting_ way of handing indexes
    ([#308](https://github.com/the-paperless-project/paperless/issues/308)).
    Thanks to [Simon Taddiken](https://github.com/skuzzle) for reporting
    the problem and helping me find where to fix it.

### 1.2.0

-   New Docker image, now based on Alpine, thanks to the efforts of
    [addadi](https://github.com/addadi) and
    [Pit](https://github.com/pitkley). This new image is dramatically
    smaller than the Debian-based one, and it also has [a new home on
    Docker Hub](https://hub.docker.com/r/danielquinn/paperless/). A
    proper thank-you to [Pit](https://github.com/pitkley) for hosting
    the image on his Docker account all this time, but after some
    discussion, we decided the image needed a more _official-looking_
    home.
-   [BastianPoe](https://github.com/BastianPoe) has added the
    long-awaited feature to automatically skip the OCR step when the PDF
    already contains text. This can be overridden by setting
    `PAPERLESS_OCR_ALWAYS=YES` either in your `paperless.conf` or in the
    environment. Note that this also means that Paperless now requires
    `libpoppler-cpp-dev` to be installed. **Important**: You'll need to
    run `pip install -r requirements.txt` after the usual `git pull` to
    properly update.
-   [BastianPoe](https://github.com/BastianPoe) has also contributed a
    monumental amount of work
    ([#291](https://github.com/the-paperless-project/paperless/pull/291))
    to solving
    [#158](https://github.com/the-paperless-project/paperless/issues/158):
    setting the document creation date based on finding a date in the
    document text.

### 1.1.0

-   Fix for
    [#283](https://github.com/the-paperless-project/paperless/issues/283),
    a redirect bug which broke interactions with paperless-desktop.
    Thanks to [chris-aeviator](https://github.com/chris-aeviator) for
    reporting it.
-   Addition of an optional new financial year filter, courtesy of
    [David Martin](https://github.com/ddddavidmartin)
    [#256](https://github.com/the-paperless-project/paperless/pull/256)
-   Fixed a typo in how thumbnails were named in exports
    [#285](https://github.com/the-paperless-project/paperless/pull/285),
    courtesy of [Dan Panzarella](https://github.com/pzl)

### 1.0.0

-   Upgrade to Django 1.11. **You'll need to run \`\`pip install -r
    requirements.txt\`\` after the usual \`\`git pull\`\` to properly
    update**.
-   Replace the templatetag-based hack we had for document listing in
    favour of a slightly less ugly solution in the form of another
    template tag with less copypasta.
-   Support for multi-word-matches for auto-tagging thanks to an
    excellent patch from [ishirav](https://github.com/ishirav)
    [#277](https://github.com/the-paperless-project/paperless/pull/277).
-   Fixed a CSS bug reported by [Stefan Hagen](https://github.com/xkpd3)
    that caused an overlapping of the text and checkboxes under some
    resolutions
    [#272](https://github.com/the-paperless-project/paperless/issues/272).
-   Patched the Docker config to force the serving of static files.
    Credit for this one goes to [dev-rke](https://github.com/dev-rke)
    via
    [#248](https://github.com/the-paperless-project/paperless/issues/248).
-   Fix file permissions during Docker start up thanks to
    [Pit](https://github.com/pitkley) on
    [#268](https://github.com/the-paperless-project/paperless/pull/268).
-   Date fields in the admin are now expressed as HTML5 date fields
    thanks to [Lukas Winkler](https://github.com/Findus23)'s issue
    [#278](https://github.com/the-paperless-project/paperless/issues/248)

### 0.8.0

-   Paperless can now run in a subdirectory on a host (`/paperless`),
    rather than always running in the root (`/`) thanks to
    [maphy-psd](https://github.com/maphy-psd)'s work on
    [#255](https://github.com/the-paperless-project/paperless/pull/255).

### 0.7.0

-   **Potentially breaking change**: As per
    [#235](https://github.com/the-paperless-project/paperless/issues/235),
    Paperless will no longer automatically delete documents attached to
    correspondents when those correspondents are themselves deleted.
    This was Django's default behaviour, but didn't make much sense in
    Paperless' case. Thanks to [Thomas
    Brueggemann](https://github.com/thomasbrueggemann) and [David
    Martin](https://github.com/ddddavidmartin) for their input on this
    one.
-   Fix for
    [#232](https://github.com/the-paperless-project/paperless/issues/232)
    wherein Paperless wasn't recognising `.tif` files properly. Thanks
    to [ayounggun](https://github.com/ayounggun) for reporting this one
    and to [Kusti Skytén](https://github.com/kskyten) for posting the
    correct solution in the GitHub issue.

### 0.6.0

-   Abandon the shared-secret trick we were using for the POST API in
    favour of BasicAuth or Django session.
-   Fix the POST API so it actually works.
    [#236](https://github.com/the-paperless-project/paperless/issues/236)
-   **Breaking change**: We've dropped the use of
    `PAPERLESS_SHARED_SECRET` as it was being used both for the API (now
    replaced with a normal auth) and form email polling. Now that we're
    only using it for email, this variable has been renamed to
    `PAPERLESS_EMAIL_SECRET`. The old value will still work for a while,
    but you should change your config if you've been using the email
    polling feature. Thanks to [Joshua
    Gilman](https://github.com/jmgilman) for all the help with this
    feature.

### 0.5.0

-   Support for fuzzy matching in the auto-tagger & auto-correspondent
    systems thanks to [Jake Gysland](https://github.com/jgysland)'s
    patch
    [#220](https://github.com/the-paperless-project/paperless/pull/220).
-   Modified the Dockerfile to prepare an export directory
    ([#212](https://github.com/the-paperless-project/paperless/pull/212)).
    Thanks to combined efforts from [Pit](https://github.com/pitkley)
    and [Strubbl](https://github.com/strubbl) in working out the kinks
    on this one.
-   Updated the import/export scripts to include support for thumbnails.
    Big thanks to [CkuT](https://github.com/CkuT) for finding this
    shortcoming and doing the work to get it fixed in
    [#224](https://github.com/the-paperless-project/paperless/pull/224).
-   All of the following changes are thanks to [David
    Martin](https://github.com/ddddavidmartin): \* Bumped the dependency on pyocr to 0.4.7 so new users can make use
    of Tesseract 4 if they so prefer
    ([#226](https://github.com/the-paperless-project/paperless/pull/226)).
    -   Fixed a number of issues with the automated mail handler
        ([#227](https://github.com/the-paperless-project/paperless/pull/227),
        [#228](https://github.com/the-paperless-project/paperless/pull/228))
    -   Amended the documentation for better handling of systemd service
        files
        ([#229](https://github.com/the-paperless-project/paperless/pull/229))
    -   Amended the Django Admin configuration to have nice headers
        ([#230](https://github.com/the-paperless-project/paperless/pull/230))

### 0.4.1

-   Fix for
    [#206](https://github.com/the-paperless-project/paperless/issues/206)
    wherein the pluggable parser didn't recognise files with all-caps
    suffixes like `.PDF`

### 0.4.0

-   Introducing reminders. See
    [#199](https://github.com/the-paperless-project/paperless/issues/199)
    for more information, but the short explanation is that you can now
    attach simple notes & times to documents which are made available
    via the API. Currently, the default API (basically just the Django
    admin) doesn't really make use of this, but [Thomas
    Brueggemann](https://github.com/thomasbrueggemann) over at
    [Paperless
    Desktop](https://github.com/thomasbrueggemann/paperless-desktop) has
    said that he would like to make use of this feature in his project.

### 0.3.6

-   Fix for
    [#200](https://github.com/the-paperless-project/paperless/issues/200)
    (!!) where the API wasn't configured to allow updating the
    correspondent or the tags for a document.
-   The `content` field is now optional, to allow for the edge case of a
    purely graphical document.
-   You can no longer add documents via the admin. This never worked in
    the first place, so all I've done here is remove the link to the
    broken form.
-   The consumer code has been heavily refactored to support a pluggable
    interface. Install a paperless consumer via pip and tell paperless
    about it with an environment variable, and you're good to go.
    Proper documentation is on its way.

### 0.3.5

-   A serious facelift for the documents listing page wherein we drop
    the tabular layout in favour of a tiled interface.
-   Users can now configure the number of items per page.
-   Fix for
    [#171](https://github.com/the-paperless-project/paperless/issues/171):
    Allow users to specify their own `SECRET_KEY` value.
-   Moved the dotenv loading to the top of settings.py
-   Fix for
    [#112](https://github.com/the-paperless-project/paperless/issues/112):
    Added checks for binaries required for document consumption.

### 0.3.4

-   Removal of django-suit due to a licensing conflict I bumped into in
    0.3.3. Note that you _can_ use Django Suit with Paperless, but only
    in a non-profit situation as their free license prohibits for-profit
    use. As a result, I can't bundle Suit with Paperless without
    conflicting with the GPL. Further development will be done against
    the stock Django admin.
-   I shrunk the thumbnails a little 'cause they were too big for me,
    even on my high-DPI monitor.
-   BasicAuth support for document and thumbnail downloads, as well as
    the Push API thanks to \@thomasbrueggemann. See
    [#179](https://github.com/the-paperless-project/paperless/pull/179).

### 0.3.3

-   Thumbnails in the UI and a Django-suit -based face-lift courtesy of
    \@ekw!
-   Timezone, items per page, and default language are now all
    configurable, also thanks to \@ekw.

### 0.3.2

-   Fix for
    [#172](https://github.com/the-paperless-project/paperless/issues/172):
    defaulting ALLOWED_HOSTS to `["*"]` and allowing the user to set
    her own value via `PAPERLESS_ALLOWED_HOSTS` should the need arise.

### 0.3.1

-   Added a default value for `CONVERT_BINARY`

### 0.3.0

-   Updated to using django-filter 1.x
-   Added some system checks so new users aren't confused by
    misconfigurations.
-   Consumer loop time is now configurable for systems with slow writes.
    Just set `PAPERLESS_CONSUMER_LOOP_TIME` to a number of seconds. The
    default is 10.
-   As per
    [#44](https://github.com/the-paperless-project/paperless/issues/44),
    we've removed support for `PAPERLESS_CONVERT`, `PAPERLESS_CONSUME`,
    and `PAPERLESS_SECRET`. Please use `PAPERLESS_CONVERT_BINARY`,
    `PAPERLESS_CONSUMPTION_DIR`, and `PAPERLESS_SHARED_SECRET`
    respectively instead.

### 0.2.0

-   [#150](https://github.com/the-paperless-project/paperless/pull/150):
    The media root is now a variable you can set in `paperless.conf`.
-   [#148](https://github.com/the-paperless-project/paperless/pull/148):
    The database location (sqlite) is now a variable you can set in
    `paperless.conf`.
-   [#146](https://github.com/the-paperless-project/paperless/issues/146):
    Fixed a bug that allowed unauthorised access to the `/fetch` URL.
-   [#131](https://github.com/the-paperless-project/paperless/issues/131):
    Document files are now automatically removed from disk when they're
    deleted in Paperless.
-   [#121](https://github.com/the-paperless-project/paperless/issues/121):
    Fixed a bug where Paperless wasn't setting document creation time
    based on the file naming scheme.
-   [#81](https://github.com/the-paperless-project/paperless/issues/81):
    Added a hook to run an arbitrary script after every document is
    consumed.
-   [#98](https://github.com/the-paperless-project/paperless/issues/98):
    Added optional environment variables for ImageMagick so that it
    doesn't explode when handling Very Large Documents or when it's
    just running on a low-memory system. Thanks to [Florian
    Harr](https://github.com/evils) for his help on this one.
-   [#89](https://github.com/the-paperless-project/paperless/issues/89)
    Ported the auto-tagging code to correspondents as well. Thanks to
    [Justin Snyman](https://github.com/stringlytyped) for the pointers
    in the issue queue.
-   Added support for guessing the date from the file name along with
    the correspondent, title, and tags. Thanks to [Tikitu de
    Jager](https://github.com/tikitu) for his pull request that I took
    forever to merge and to [Pit](https://github.com/pitkley) for his
    efforts on the regex front.
-   [#94](https://github.com/the-paperless-project/paperless/issues/94):
    Restored support for changing the created date in the UI. Thanks to
    [Martin Honermeyer](https://github.com/djmaze) and [Tim
    White](https://github.com/timwhite) for working with me on this.

### 0.1.1

-   Potentially **Breaking Change**: All references to "sender" in the
    code have been renamed to "correspondent" to better reflect the
    nature of the property (one could quite reasonably scan a document
    before sending it to someone.)
-   [#67](https://github.com/the-paperless-project/paperless/issues/67):
    Rewrote the document exporter and added a new importer that allows
    for full metadata retention without depending on the file name and
    modification time. A big thanks to [Tikitu de
    Jager](https://github.com/tikitu),
    [Pit](https://github.com/pitkley), [Florian
    Jung](https://github.com/the01), and [Christopher
    Luu](https://github.com/nuudles) for their code snippets and
    contributing conversation that lead to this change.
-   [#20](https://github.com/the-paperless-project/paperless/issues/20):
    Added _unpaper_ support to help in cleaning up the scanned image
    before it's OCR'd. Thanks to [Pit](https://github.com/pitkley) for
    this one.
-   [#71](https://github.com/the-paperless-project/paperless/issues/71)
    Added (encrypted) thumbnails in anticipation of a proper UI.
-   [#68](https://github.com/the-paperless-project/paperless/issues/68):
    Added support for using a proper config file at
    `/etc/paperless.conf` and modified the systemd unit files to use it.
-   Refactored the Vagrant installation process to use environment
    variables rather than asking the user to modify `settings.py`.
-   [#44](https://github.com/the-paperless-project/paperless/issues/44):
    Harmonise environment variable names with constant names.
-   [#60](https://github.com/the-paperless-project/paperless/issues/60):
    Setup logging to actually use the Python native logging framework.
-   [#53](https://github.com/the-paperless-project/paperless/issues/53):
    Fixed an annoying bug that caused `.jpeg` and `.JPG` images to be
    imported but made unavailable.

### 0.1.0

-   Docker support! Big thanks to [Wayne
    Werner](https://github.com/waynew), [Brian
    Conn](https://github.com/TheConnMan), and [Tikitu de
    Jager](https://github.com/tikitu) for this one, and especially to
    [Pit](https://github.com/pitkley) who spearheadded this effort.
-   A simple REST API is in place, but it should be considered unstable.
-   Cleaned up the consumer to use temporary directories instead of a
    single scratch space. (Thanks [Pit](https://github.com/pitkley))
-   Improved the efficiency of the consumer by parsing pages more
    intelligently and introducing a threaded OCR process (thanks again
    [Pit](https://github.com/pitkley)).
-   [#45](https://github.com/the-paperless-project/paperless/issues/45):
    Cleaned up the logic for tag matching. Reported by
    [darkmatter](https://github.com/darkmatter).
-   [#47](https://github.com/the-paperless-project/paperless/issues/47):
    Auto-rotate landscape documents. Reported by
    [Paul](https://github.com/polo2ro) and fixed by
    [Pit](https://github.com/pitkley).
-   [#48](https://github.com/the-paperless-project/paperless/issues/48):
    Matching algorithms should do so on a word boundary
    ([darkmatter](https://github.com/darkmatter))
-   [#54](https://github.com/the-paperless-project/paperless/issues/54):
    Documented the re-tagger ([zedster](https://github.com/zedster))
-   [#57](https://github.com/the-paperless-project/paperless/issues/57):
    Make sure file is preserved on import failure
    ([darkmatter](https://github.com/darkmatter))
-   Added tox with pep8 checking

### 0.0.6

-   Added support for parallel OCR (significant work from
    [Pit](https://github.com/pitkley))
-   Sped up the language detection (significant work from
    [Pit](https://github.com/pitkley))
-   Added simple logging

### 0.0.5

-   Added support for image files as documents (png, jpg, gif, tiff)
-   Added a crude means of HTTP POST for document imports
-   Added IMAP mail support
-   Added a re-tagging utility
-   Documentation for the above as well as data migration

### 0.0.4

-   Added automated tagging basted on keyword matching
-   Cleaned up the document listing page
-   Removed `User` and `Group` from the admin
-   Added `pytz` to the list of requirements

### 0.0.3

-   Added basic tagging

### 0.0.2

-   Added language detection
-   Added datestamps to `document_exporter`.
-   Changed `settings.TESSERACT_LANGUAGE` to `settings.OCR_LANGUAGE`.

### 0.0.1

-   Initial release
