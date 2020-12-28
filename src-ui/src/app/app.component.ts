import { Component } from '@angular/core';
import { AppViewService } from './services/app-view.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {

  constructor (appViewService: AppViewService) {
    appViewService.updateDarkModeSettings()
  }


}
