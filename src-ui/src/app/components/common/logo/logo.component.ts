import { Component, Input, inject } from '@angular/core'
import { DOCUMENT } from '@angular/common'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-logo',
  templateUrl: './logo.component.html',
  styleUrls: ['./logo.component.scss'],
})
export class LogoComponent {
  private settingsService = inject(SettingsService)
  private document = inject(DOCUMENT)

  @Input()
  extra_classes: string

  @Input()
  height = '6em'

  get customLogo(): string {
    return this.settingsService.get(SETTINGS_KEYS.APP_LOGO)?.length
      ? environment.apiBaseUrl.replace(
          /\/api\/$/,
          this.settingsService.get(SETTINGS_KEYS.APP_LOGO)
        )
      : null
  }

  get colorScheme(): 'dark' | 'light' {
    const theme = this.document.documentElement.getAttribute('data-bs-theme')
    if (theme === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
    }
    return theme === 'dark' ? 'dark' : 'light'
  }

  getClasses() {
    return ['logo'].concat(this.extra_classes).join(' ')
  }
}
