import { DOCUMENT } from '@angular/common'
import { HttpClient } from '@angular/common/http'
import {
  Inject,
  Injectable,
  LOCALE_ID,
  Renderer2,
  RendererFactory2,
  RendererStyleFlags2,
} from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service'
import { first, Observable, tap } from 'rxjs'
import {
  BRIGHTNESS,
  estimateBrightnessForColor,
  hexToHsl,
} from 'src/app/utils/color'
import { environment } from 'src/environments/environment'
import {
  PaperlessUiSettings,
  SETTINGS,
  SETTINGS_KEYS,
} from '../data/paperless-uisettings'
import { ToastService } from './toast.service'

export interface LanguageOption {
  code: string
  name: string
  englishName?: string

  /**
   * A date format string for use by the date selectors. MUST contain 'yyyy', 'mm' and 'dd'.
   */
  dateInputFormat?: string
}

@Injectable({
  providedIn: 'root',
})
export class SettingsService {
  private renderer: Renderer2
  protected baseUrl: string = environment.apiBaseUrl + 'ui_settings/'

  private settings: Object = {}

  public displayName: string

  constructor(
    rendererFactory: RendererFactory2,
    @Inject(DOCUMENT) private document,
    private cookieService: CookieService,
    private meta: Meta,
    @Inject(LOCALE_ID) private localeId: string,
    protected http: HttpClient,
    private toastService: ToastService
  ) {
    this.renderer = rendererFactory.createRenderer(null, null)
  }

  // this is called by the app initializer in app.module
  public initializeSettings(): Observable<PaperlessUiSettings> {
    return this.http.get<PaperlessUiSettings>(this.baseUrl).pipe(
      first(),
      tap((uisettings) => {
        Object.assign(this.settings, uisettings.settings)
        this.maybeMigrateSettings()
        // to update lang cookie
        if (this.settings['language']?.length)
          this.setLanguage(this.settings['language'])
        this.displayName = uisettings.display_name.trim()
      })
    )
  }

  public updateAppearanceSettings(
    darkModeUseSystem = null,
    darkModeEnabled = null,
    themeColor = null
  ): void {
    darkModeUseSystem ??= this.get(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM)
    darkModeEnabled ??= this.get(SETTINGS_KEYS.DARK_MODE_ENABLED)
    themeColor ??= this.get(SETTINGS_KEYS.THEME_COLOR)

    if (darkModeUseSystem) {
      this.renderer.addClass(this.document.body, 'color-scheme-system')
      this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    } else {
      this.renderer.removeClass(this.document.body, 'color-scheme-system')
      darkModeEnabled
        ? this.renderer.addClass(this.document.body, 'color-scheme-dark')
        : this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    }

    // remove these in case they were there
    this.renderer.removeClass(this.document.body, 'primary-dark')
    this.renderer.removeClass(this.document.body, 'primary-light')

    if (themeColor) {
      const hsl = hexToHsl(themeColor)
      const bgBrightnessEstimate = estimateBrightnessForColor(themeColor)

      if (bgBrightnessEstimate == BRIGHTNESS.DARK) {
        this.renderer.addClass(this.document.body, 'primary-dark')
        this.renderer.removeClass(this.document.body, 'primary-light')
      } else {
        this.renderer.addClass(this.document.body, 'primary-light')
        this.renderer.removeClass(this.document.body, 'primary-dark')
      }
      this.renderer.setStyle(
        document.body,
        '--pngx-primary',
        `${+hsl.h * 360},${hsl.s * 100}%`,
        RendererStyleFlags2.DashCase
      )
      this.renderer.setStyle(
        document.body,
        '--pngx-primary-lightness',
        `${hsl.l * 100}%`,
        RendererStyleFlags2.DashCase
      )
    } else {
      this.renderer.removeStyle(
        document.body,
        '--pngx-primary',
        RendererStyleFlags2.DashCase
      )
      this.renderer.removeStyle(
        document.body,
        '--pngx-primary-lightness',
        RendererStyleFlags2.DashCase
      )
    }
  }

  getLanguageOptions(): LanguageOption[] {
    const languages = [
      {
        code: 'en-us',
        name: $localize`English (US)`,
        englishName: 'English (US)',
        dateInputFormat: 'mm/dd/yyyy',
      },
      {
        code: 'be-by',
        name: $localize`Belarusian`,
        englishName: 'Belarusian',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'cs-cz',
        name: $localize`Czech`,
        englishName: 'Czech',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'da-dk',
        name: $localize`Danish`,
        englishName: 'Danish',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'de-de',
        name: $localize`German`,
        englishName: 'German',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'en-gb',
        name: $localize`English (GB)`,
        englishName: 'English (GB)',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'es-es',
        name: $localize`Spanish`,
        englishName: 'Spanish',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'fr-fr',
        name: $localize`French`,
        englishName: 'French',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'it-it',
        name: $localize`Italian`,
        englishName: 'Italian',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'lb-lu',
        name: $localize`Luxembourgish`,
        englishName: 'Luxembourgish',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'nl-nl',
        name: $localize`Dutch`,
        englishName: 'Dutch',
        dateInputFormat: 'dd-mm-yyyy',
      },
      {
        code: 'pl-pl',
        name: $localize`Polish`,
        englishName: 'Polish',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'pt-br',
        name: $localize`Portuguese (Brazil)`,
        englishName: 'Portuguese (Brazil)',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'pt-pt',
        name: $localize`Portuguese`,
        englishName: 'Portuguese',
        dateInputFormat: 'dd/mm/yyyy',
      },
      {
        code: 'ro-ro',
        name: $localize`Romanian`,
        englishName: 'Romanian',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'ru-ru',
        name: $localize`Russian`,
        englishName: 'Russian',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'sl-si',
        name: $localize`Slovenian`,
        englishName: 'Slovenian',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'sr-cs',
        name: $localize`Serbian`,
        englishName: 'Serbian',
        dateInputFormat: 'dd.mm.yyyy',
      },
      {
        code: 'sv-se',
        name: $localize`Swedish`,
        englishName: 'Swedish',
        dateInputFormat: 'yyyy-mm-dd',
      },
      {
        code: 'tr-tr',
        name: $localize`Turkish`,
        englishName: 'Turkish',
        dateInputFormat: 'yyyy-mm-dd',
      },
      {
        code: 'zh-cn',
        name: $localize`Chinese Simplified`,
        englishName: 'Chinese Simplified',
        dateInputFormat: 'yyyy-mm-dd',
      },
    ]

    // Sort languages by localized name at runtime
    languages.sort((a, b) => {
      return a.name < b.name ? -1 : 1
    })

    return languages
  }

  getDateLocaleOptions(): LanguageOption[] {
    let isoOption: LanguageOption = {
      code: 'iso-8601',
      name: $localize`ISO 8601`,
      dateInputFormat: 'yyyy-mm-dd',
    }
    return [isoOption].concat(this.getLanguageOptions())
  }

  private getLanguageCookieName() {
    let prefix = ''
    if (this.meta.getTag('name=cookie_prefix')) {
      prefix = this.meta.getTag('name=cookie_prefix').content
    }
    return `${prefix || ''}django_language`
  }

  getLanguage(): string {
    return this.get(SETTINGS_KEYS.LANGUAGE)
  }

  setLanguage(language: string) {
    this.set(SETTINGS_KEYS.LANGUAGE, language)
    if (language?.length) {
      // for Django
      this.cookieService.set(this.getLanguageCookieName(), language)
    } else {
      this.cookieService.delete(this.getLanguageCookieName())
    }
  }

  getLocalizedDateInputFormat(): string {
    let dateLocale =
      this.get(SETTINGS_KEYS.DATE_LOCALE) ||
      this.getLanguage() ||
      this.localeId.toLowerCase()
    return (
      this.getDateLocaleOptions().find((o) => o.code == dateLocale)
        ?.dateInputFormat || 'yyyy-mm-dd'
    )
  }

  get(key: string): any {
    let setting = SETTINGS.find((s) => s.key == key)

    if (!setting) {
      return null
    }

    let value = null
    // parse key:key:key into nested object
    const keys = key.replace('general-settings:', '').split(':')
    let settingObj = this.settings
    keys.forEach((keyPart, index) => {
      keyPart = keyPart.replace(/-/g, '_')
      if (!settingObj.hasOwnProperty(keyPart)) return
      if (index == keys.length - 1) value = settingObj[keyPart]
      else settingObj = settingObj[keyPart]
    })

    if (value != null) {
      switch (setting.type) {
        case 'boolean':
          return JSON.parse(value)
        case 'number':
          return +value
        case 'string':
          return value
        default:
          return value
      }
    } else {
      return setting.default
    }
  }

  set(key: string, value: any) {
    // parse key:key:key into nested object
    let settingObj = this.settings
    const keys = key.replace('general-settings:', '').split(':')
    keys.forEach((keyPart, index) => {
      keyPart = keyPart.replace(/-/g, '_')
      if (!settingObj.hasOwnProperty(keyPart)) settingObj[keyPart] = {}
      if (index == keys.length - 1) settingObj[keyPart] = value
      else settingObj = settingObj[keyPart]
    })
  }

  storeSettings(): Observable<any> {
    return this.http.post(this.baseUrl, { settings: this.settings })
  }

  maybeMigrateSettings() {
    if (
      !this.settings.hasOwnProperty('documentListSize') &&
      localStorage.getItem(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)
    ) {
      // lets migrate
      const successMessage = $localize`Successfully completed one-time migratration of settings to the database!`
      const errorMessage = $localize`Unable to migrate settings to the database, please try saving manually.`

      try {
        for (const setting in SETTINGS_KEYS) {
          const key = SETTINGS_KEYS[setting]
          const value = localStorage.getItem(key)
          this.set(key, value)
        }
        this.set(
          SETTINGS_KEYS.LANGUAGE,
          this.cookieService.get(this.getLanguageCookieName())
        )
      } catch (error) {
        this.toastService.showError(errorMessage)
        console.log(error)
      }

      this.storeSettings()
        .pipe(first())
        .subscribe({
          next: () => {
            this.updateAppearanceSettings()
            this.toastService.showInfo(successMessage)
          },
          error: (e) => {
            this.toastService.showError(errorMessage)
            console.log(e)
          },
        })
    }
  }
}
