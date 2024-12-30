import { Component, EventEmitter, Output } from '@angular/core'
import { NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'

@Component({
  selector: 'pngx-welcome-widget',
  templateUrl: './welcome-widget.component.html',
  styleUrls: ['./welcome-widget.component.scss'],
  imports: [NgbAlertModule],
})
export class WelcomeWidgetComponent {
  constructor(public readonly tourService: TourService) {}

  @Output()
  dismiss: EventEmitter<boolean> = new EventEmitter()
}
