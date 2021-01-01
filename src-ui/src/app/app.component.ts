import { Component } from '@angular/core';
import { SettingsService } from './services/settings.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {

  constructor (private settings: SettingsService) {
    let anyWindow = (window as any)
    anyWindow.pdfWorkerSrc = '/assets/js/pdf.worker.min.js';
    this.settings.updateDarkModeSettings()
  }

}
