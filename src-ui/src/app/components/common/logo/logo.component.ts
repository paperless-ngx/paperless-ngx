import { Component, Input, inject, signal } from '@angular/core'
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
  private extraClassesSignal = signal<string>(undefined)
  private heightSignal = signal('6em')

  @Input()
  get extra_classes(): string {
    return this.extraClassesSignal()
  }

  set extra_classes(extraClasses: string) {
    this.extraClassesSignal.set(extraClasses)
  }

  @Input()
  get height(): string {
    return this.heightSignal()
  }

  set height(height: string) {
    this.heightSignal.set(height)
  }

  get customLogo(): string {
    return this.settingsService.get(SETTINGS_KEYS.APP_LOGO)?.length
      ? environment.apiBaseUrl.replace(
          /\/api\/$/,
          this.settingsService.get(SETTINGS_KEYS.APP_LOGO)
        )
      : null
  }

  getClasses() {
    return ['logo'].concat(this.extra_classes).join(' ')
  }
}
