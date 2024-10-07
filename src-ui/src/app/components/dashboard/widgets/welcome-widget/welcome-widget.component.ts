import { Component, EventEmitter, Output } from '@angular/core'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { SettingsService } from '../../../../services/settings.service'
import { environment } from '../../../../../environments/environment'

@Component({
  selector: 'pngx-welcome-widget',
  templateUrl: './welcome-widget.component.html',
  styleUrls: ['./welcome-widget.component.scss'],
})
export class WelcomeWidgetComponent {
  constructor(public readonly tourService: TourService, public settingsService: SettingsService) {
  }

  @Output()
  dismiss: EventEmitter<boolean> = new EventEmitter()
   get subtitle() {
    if (this.settingsService.displayName) {
      return $localize`Hello ${this.settingsService.displayName}, welcome to ${environment.appTitle}`
    } else {
      return $localize`Welcome to ${environment.appTitle}`
    }
  }
}
