import { Component, OnInit } from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent {
  constructor(
    public savedViewService: SavedViewService,
    public settingsService: SettingsService
  ) {}

  get subtitle() {
    if (this.settingsService.displayName) {
      return $localize`Hello ${this.settingsService.displayName}, welcome to Paperless-ngx!`
    } else {
      return $localize`Welcome to Paperless-ngx!`
    }
  }
}
