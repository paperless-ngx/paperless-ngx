import { Component, Input } from '@angular/core'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-logo',
  templateUrl: './logo.component.html',
  styleUrls: ['./logo.component.scss'],
})
export class LogoComponent {
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

  constructor(private settingsService: SettingsService) {}

  getClasses() {
    return ['logo'].concat(this.extra_classes).join(' ')
  }
}
