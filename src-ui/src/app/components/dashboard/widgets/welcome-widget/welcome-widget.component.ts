import { Component, EventEmitter, Output } from '@angular/core'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'

@Component({
  selector: 'pngx-welcome-widget',
  templateUrl: './welcome-widget.component.html',
  styleUrls: ['./welcome-widget.component.scss'],
})
export class WelcomeWidgetComponent {
  constructor(public readonly tourService: TourService) {}

  @Output()
  dismiss: EventEmitter<boolean> = new EventEmitter()
}
