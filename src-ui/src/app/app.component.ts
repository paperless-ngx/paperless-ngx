import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {

  constructor () {
    (window as any).pdfWorkerSrc = '/assets/js/pdf.worker.min.js';
  }


}
