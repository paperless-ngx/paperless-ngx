import { Component } from '@angular/core'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent extends ComponentWithPermissions {
  constructor(
    public settingsService: SettingsService,
    public savedViewService: SavedViewService
  ) {
    super()
  }

  get subtitle() {
    if (this.settingsService.displayName) {
      return $localize`Hello ${this.settingsService.displayName}, welcome to Paperless-ngx`
    } else {
      return $localize`Welcome to Paperless-ngx`
    }
  }
}
